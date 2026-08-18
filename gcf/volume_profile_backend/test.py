import datetime
import pytz
import yfinance as yf

NUM_BINS = 150
VALUE_AREA_PCT = 0.70
INTERVAL = "1h"

ny_tz = pytz.timezone("America/New_York")
symbol = "SLV"
now = datetime.datetime.now(ny_tz)
today = now.date()


def bin_bars(bars, bin_width):
    highs = bars["High"].to_numpy().flatten()
    lows = bars["Low"].to_numpy().flatten()
    vols = bars["Volume"].to_numpy().flatten()

    hist = {}
    for high, low, vol in zip(highs, lows, vols):
        if vol <= 0:
            continue
        lo_idx = round(float(low) / bin_width)
        hi_idx = round(float(high) / bin_width)
        if hi_idx < lo_idx:
            lo_idx, hi_idx = hi_idx, lo_idx
        n = hi_idx - lo_idx + 1
        per_bin = float(vol) / n
        for idx in range(lo_idx, hi_idx + 1):
            key = round(idx * bin_width, 2)
            hist[key] = hist.get(key, 0) + per_bin
    return hist


def compute_vp(hist, value_area_pct=VALUE_AREA_PCT):
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


def run(label, start_date, interval=INTERVAL):
    bars = yf.download(
        symbol,
        start=start_date,
        end=today + datetime.timedelta(days=1),
        interval=interval,
        prepost=False,
        progress=False,
        multi_level_index=False,
    )
    if bars is None or bars.empty:
        print(f"{label:35s} -> no data")
        return
    bars = bars.dropna(subset=["High", "Low", "Close", "Volume"])
    if bars.empty:
        print(f"{label:35s} -> no usable bars")
        return

    bin_width = max(0.01, round(float(bars["High"].max() - bars["Low"].min()) / NUM_BINS, 2))
    hist = bin_bars(bars, bin_width)
    if not hist:
        print(f"{label:35s} -> empty histogram")
        return
    vp = compute_vp(hist)

    print(
        f"{label:35s} -> VAL=${vp['val']:.2f}  POC=${vp['poc']:.2f}  VAH=${vp['vah']:.2f}"
        f"   ({start_date} -> {today}, {len(bars)} bars)"
    )


print(f"SLV volume profile across different windows (as of {now.strftime('%Y-%m-%d %H:%M %Z')})")
print("=" * 90)

run("Month-to-date (current setup)", today.replace(day=1))
run("Trailing 30 calendar days", today - datetime.timedelta(days=30))
run("Trailing 14 calendar days", today - datetime.timedelta(days=14))
run("Trailing 10 calendar days", today - datetime.timedelta(days=10))
run("Trailing 7 calendar days", today - datetime.timedelta(days=7))
run("Trailing 5 calendar days", today - datetime.timedelta(days=5))
run("Trailing 3 calendar days", today - datetime.timedelta(days=3))
run("Today only", today)