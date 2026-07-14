import pytz
import datetime
import yfinance as yf

ny_tz = pytz.timezone('America/New_York')

def get_market_session_today():
    """
    Returns today_str as a "YYYY-MM-DD" string.
    Returns None if today is not an open market session.
    """
    today = datetime.datetime.now(ny_tz).date()
    spy = yf.download("SPY", period="10d", interval="1d", progress=False)
    open_days = spy.index.date

    if len(open_days) < 2 or open_days[-1] != today:
        return None

    today_str = today.strftime("%Y-%m-%d")
    return today_str

def get_last_market_session():
    """
    Returns yesterday_str as a "YYYY-MM-DD" string, the most recently closed
    trading session strictly before today. Works regardless of what time of
    day this is called, since it explicitly excludes today's date rather
    than assuming positionally which row is "yesterday".
    Returns None if it can't be determined.
    """
    today = datetime.datetime.now(ny_tz).date()
    spy = yf.download("SPY", period="10d", interval="1d", progress=False)
    open_days = spy.index.date

    if len(open_days) < 2:
        return None

    yesterday_session = open_days[-1]
    if yesterday_session == today:
        yesterday_session = open_days[-2]

    return yesterday_session.strftime("%Y-%m-%d")

def get_volume_and_price_data_for_date(symbols, target_date):
    """
    Same shape as get_volume_and_price_data, but looks up target_date by its
    actual calendar date within the download instead of assuming it's the
    most recent row. Needed because this can run any time of day, so
    "today's" bar may already exist in the download by then.
    """
    try:
        data = yf.download(symbols, period="15d", group_by='ticker', threads=True)
        stock_data = {}

        for symbol in symbols:
            try:
                vol_data = data[symbol]['Volume']
                close_data = data[symbol]['Close']
                bar_dates = vol_data.index.date

                idx = None
                for i, d in enumerate(bar_dates):
                    if d == target_date:
                        idx = i
                        break

                if idx is None or idx < 5:
                    continue

                volumes = [
                    int(vol_data.iloc[idx]),
                    int(vol_data.iloc[idx - 1]),
                ]

                prices = [
                    float(close_data.iloc[idx]),
                    float(close_data.iloc[idx - 1]),
                ]

                ma5_yesterday = float(vol_data.iloc[idx - 5:idx].mean())

                price_change_today = prices[0] - prices[1]
                price_change_pct_today = (price_change_today / prices[1]) * 100

                stock_data[symbol] = {
                    'volumes': volumes,
                    'ma5_yesterday': ma5_yesterday,
                    'prices': prices,
                    'price_change_today': price_change_today,
                    'price_change_pct_today': price_change_pct_today
                }
            except Exception as e:
                print(f"Failed to process {symbol}: {e}")
                continue

        return stock_data
    except Exception as e:
        print(f"Failed to download stock data: {e}")
        return {}