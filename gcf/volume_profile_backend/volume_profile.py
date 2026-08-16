import calendar
import datetime
import pytz
import yfinance as yf
import pandas_market_calendars as mcal
from firebase_admin import firestore

db = firestore.client()
ny_tz = pytz.timezone('America/New_York')
nyse = mcal.get_calendar('NYSE')

MAX_MONTHS_TO_KEEP = 2                 # months subcollection: keep only the N most recent docs
NUM_BINS = 150                        # price bins spanning the initial 15-day reference range
VALUE_AREA_PCT = 0.86                 # standard 86% value area
MIN_TRADING_DAYS_FOR_CURRENT_MONTH = 15
INTRADAY_INTERVAL = "1h"

# volume_profile_cache/{symbol}                    <- lastPrice/updatedAt fields, set in main.py
# volume_profile_cache/{symbol}/months/{YYYY-MM}    <- cumulative month-base histogram
CACHE_ROOT = "volume_profile_cache"


def _symbol_doc(symbol):
    return db.collection(CACHE_ROOT).document(symbol)


def _month_doc(symbol, year, month):
    return _symbol_doc(symbol).collection("months").document(f"{year}-{month:02d}")


def _prune_old_months(symbol, keep=MAX_MONTHS_TO_KEEP):
    months_ref = _symbol_doc(symbol).collection("months")
    doc_ids = sorted((doc.id for doc in months_ref.list_documents()), reverse=True)

    for stale_id in doc_ids[keep:]:
        months_ref.document(stale_id).delete()
        print(f"[{symbol}] Pruned stale month cache {stale_id}")


def _serialize_bins(bins):
    return {f"{k:.2f}": v for k, v in bins.items()}


def _deserialize_bins(raw_bins):
    return {float(k): v for k, v in raw_bins.items()}


def _bin_price(price, bin_width):
    return round(round(float(price) / bin_width) * bin_width, 2)


def fetch_today_bars(symbols):
    """
    One batched yfinance call for today's intraday bars across every
    symbol, mirroring the group_by='ticker' pattern check_volume_alerts
    already uses. Pass the result into build_volume_profile_and_price for
    each symbol instead of letting each one download individually.
    Returns the raw multi-ticker DataFrame, or None on failure.
    """
    today = datetime.datetime.now(ny_tz).date()
    end = today + datetime.timedelta(days=1)
    try:
        return yf.download(
            list(symbols), start=today, end=end,
            interval=INTRADAY_INTERVAL, prepost=True,
            group_by='ticker', threads=True, progress=False,
        )
    except Exception as e:
        print(f"Failed to batch-download today's bars: {e}")
        return None


def _extract_symbol_bars(batched_bars, symbol):
    """Slices one symbol's OHLCV out of a group_by='ticker' batched download."""
    if batched_bars is None:
        return None
    try:
        bars = batched_bars[symbol].dropna(subset=["Close", "Volume"])
    except (KeyError, TypeError):
        return None
    return bars if not bars.empty else None


def _download_range(symbol, start_date, end_date):
    """
    Downloads hourly bars for a single symbol over [start_date, end_date]
    inclusive, including pre/post market so after-hours volume isn't
    dropped. Used for month-base building/extension, where each symbol
    can need a different date range. Returns the raw DataFrame (may be
    empty), or None on failure.
    """
    end = end_date + datetime.timedelta(days=1)
    try:
        return yf.download(
            symbol, start=start_date, end=end,
            interval=INTRADAY_INTERVAL, prepost=True, progress=False,
        )
    except Exception as e:
        print(f"[{symbol}] Failed to download bars for {start_date}..{end_date}: {e}")
        return None


def _bin_bars(bars, bin_width):
    """Bins a bars DataFrame into per-day {price_bin: volume} shards, keyed by date string."""
    closes = bars["Close"].to_numpy().flatten()
    vols = bars["Volume"].to_numpy().flatten()
    bar_dates = bars.index.date

    shards_by_day = {}
    for price, vol, bar_date in zip(closes, vols, bar_dates):
        if vol <= 0:
            continue
        day_shard = shards_by_day.setdefault(bar_date.strftime("%Y-%m-%d"), {})
        bin_key = _bin_price(price, bin_width)
        day_shard[bin_key] = day_shard.get(bin_key, 0) + int(vol)

    return shards_by_day


def _merge_shards(shards):
    merged = {}
    for shard in shards:
        if not shard:
            continue
        for bin_key, vol in shard.items():
            merged[bin_key] = merged.get(bin_key, 0) + vol
    return merged


def _save_month_base(doc_ref, bins, bin_width, covered_through):
    doc_ref.set({
        "bins": _serialize_bins(bins),
        "binWidth": bin_width,
        "coveredThroughDate": covered_through,
        "cachedAt": firestore.SERVER_TIMESTAMP,
    })


def _trading_days_in_month(year, month, before_date=None):
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month, calendar.monthrange(year, month)[1])
    days = list(nyse.schedule(start_date=start, end_date=end).index.date)
    return [d for d in days if before_date is None or d < before_date]


def _prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _get_or_build_month_base(symbol, year, month, days_so_far):
    """
    Cached, cumulatively-extending VP covering every CLOSED trading day of
    the month so far: day 1 through the most recent day in `days_so_far`
    (which excludes today for the current month, or is the full month for
    a completed prior month).

    First call each month builds an initial base from the first
    MIN_TRADING_DAYS_FOR_CURRENT_MONTH days and fixes bin_width from that
    range. Every call after that compares the doc's stored
    coveredThroughDate to the latest day in `days_so_far`; if a new day has
    closed since, it's fetched, binned with the SAME stored bin_width (so
    it aligns with the existing grid), merged in, and coveredThroughDate is
    advanced. Same-day repeat calls see no new closed day and are a no-op.

    Returns (merged_hist, bin_width) or (None, None).
    """
    doc_ref = _month_doc(symbol, year, month)
    doc = doc_ref.get()

    if not doc.exists:
        init_days = days_so_far[:MIN_TRADING_DAYS_FOR_CURRENT_MONTH]
        if len(init_days) < MIN_TRADING_DAYS_FOR_CURRENT_MONTH:
            return None, None

        bars = _download_range(symbol, init_days[0], init_days[-1])
        if bars is None or bars.empty:
            print(f"[{symbol}] No bars available to build initial base for {year}-{month:02d}")
            return None, None

        closes = bars["Close"].to_numpy().flatten()
        bin_width = max(0.01, round(float(closes.max() - closes.min()) / NUM_BINS, 2))

        shards_by_day = _bin_bars(bars, bin_width)

        base_bins = _merge_shards(shards_by_day.values())
        covered_through = init_days[-1].strftime("%Y-%m-%d")
        _save_month_base(doc_ref, base_bins, bin_width, covered_through)
        _prune_old_months(symbol)
    else:
        data = doc.to_dict()
        base_bins = _deserialize_bins(data.get("bins", {}))
        bin_width = data.get("binWidth")
        covered_through = data.get("coveredThroughDate")

    if not days_so_far:
        return base_bins, bin_width

    latest_closed_str = days_so_far[-1].strftime("%Y-%m-%d")
    if covered_through != latest_closed_str:
        missing_days = [d for d in days_so_far if d.strftime("%Y-%m-%d") > covered_through]
        if missing_days:
            bars = _download_range(symbol, missing_days[0], missing_days[-1])
            if bars is not None and not bars.empty:
                shards_by_day = _bin_bars(bars, bin_width)
                base_bins = _merge_shards([base_bins] + list(shards_by_day.values()))
            else:
                print(f"[{symbol}] No bars returned for missing days {missing_days[0]}..{missing_days[-1]}")

        covered_through = latest_closed_str
        _save_month_base(doc_ref, base_bins, bin_width, covered_through)

    return base_bins, bin_width


def _shard_from_bars(bars, date, bin_width):
    """
    Bins a single day's already-fetched bars using `bin_width` inherited
    from the reference base, so bins align with the cached grid. Takes
    pre-fetched bars (e.g. one symbol's slice of a batched download)
    rather than downloading anything itself. Returns (shard, last_price)
    or (None, None).
    """
    if bars is None or bars.empty:
        return None, None

    closes = bars["Close"].to_numpy().flatten()
    if len(closes) == 0:
        return None, None
    last_price = float(closes[-1])

    shards_by_day = _bin_bars(bars, bin_width)
    return shards_by_day.get(date.strftime("%Y-%m-%d")), last_price


def _compute_poc_and_value_area(hist, value_area_pct=VALUE_AREA_PCT):
    bins = sorted(hist.keys())
    poc_idx, poc = max(enumerate(bins), key=lambda iv: hist[iv[1]])
    target = sum(hist.values()) * value_area_pct

    included = {poc_idx}
    acc = hist[poc]
    lo, hi = poc_idx - 1, poc_idx + 1

    while acc < target and (lo >= 0 or hi < len(bins)):
        vol_lo = hist[bins[lo]] if lo >= 0 else -1
        vol_hi = hist[bins[hi]] if hi < len(bins) else -1
        if vol_hi >= vol_lo:
            included.add(hi)
            acc += hist[bins[hi]]
            hi += 1
        else:
            included.add(lo)
            acc += hist[bins[lo]]
            lo -= 1

    return {"poc": poc, "val": bins[min(included)], "vah": bins[max(included)]}


def build_volume_profile_and_price(symbol, today_bars=None):
    """
    Returns (vp, current_price) where vp is {"poc", "val", "vah"}, using
    whichever month (current or previous) is the valid reference per the
    ">=15 trading days" rule. `today_bars` should be the raw batched
    download from fetch_today_bars() covering every symbol — this
    function slices out its own symbol's data internally. Pass None to
    skip today's price/shard entirely (e.g. testing off-hours).
    Returns None if there isn't enough data to compute anything at all.
    """
    today = datetime.datetime.now(ny_tz).date()
    this_month_days = _trading_days_in_month(today.year, today.month, before_date=today)
    symbol_today_bars = _extract_symbol_bars(today_bars, symbol)

    if len(this_month_days) >= MIN_TRADING_DAYS_FOR_CURRENT_MONTH:
        base, bin_width = _get_or_build_month_base(symbol, today.year, today.month, this_month_days)
        if base is None:
            return None
        today_shard, current_price = _shard_from_bars(symbol_today_bars, today, bin_width)
        merged = _merge_shards([base, today_shard])
    else:
        py, pm = _prev_month(today.year, today.month)
        merged, bin_width = _get_or_build_month_base(symbol, py, pm, _trading_days_in_month(py, pm))
        if merged is None:
            return None
        # Today's live price is still needed for comparison even though
        # it isn't merged into last month's already-complete reference VP.
        _, current_price = _shard_from_bars(symbol_today_bars, today, bin_width)

    if not merged:
        print(f"[{symbol}] No volume profile data available")
        return None

    return _compute_poc_and_value_area(merged), current_price