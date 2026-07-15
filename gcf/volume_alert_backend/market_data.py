import pytz
import datetime
import yfinance as yf
import pandas_market_calendars as mcal

ny_tz = pytz.timezone('America/New_York')
nyse = mcal.get_calendar('NYSE')

def get_market_session_today():
    """
    Returns today_str as a "YYYY-MM-DD" string.
    Returns None if today is not an open market session.
    """
    today = datetime.datetime.now(ny_tz).date()
    schedule = nyse.schedule(start_date=today, end_date=today)
    
    if schedule.empty:
        return None

    return today.strftime("%Y-%m-%d")

def get_last_market_session():
    """
    Returns yesterday_str as a "YYYY-MM-DD" string, the most recently closed
    trading session strictly before today. Works regardless of what time of
    day this is called, since it explicitly excludes today's date rather
    than assuming positionally which row is "yesterday".
    Returns None if it can't be determined.
    """
    today = datetime.datetime.now(ny_tz).date()
    end_date = today - datetime.timedelta(days=1)
    start_lookback = today - datetime.timedelta(days=15)
    
    schedule = nyse.schedule(start_date=start_lookback, end_date=end_date)
    open_days = schedule.index.date
    
    if len(open_days) == 0:
        return None

    return open_days[-1].strftime("%Y-%m-%d")

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

                if idx is None:
                    print(f"[{symbol}] WARNING: no bar found for {target_date} in yfinance download (data gap or delay)")
                    continue

                if idx < 5:
                    print(f"[{symbol}] Skipping {target_date}: only {idx} prior bars available (need 5 for MA)")
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