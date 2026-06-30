import os
import pytz
import datetime
import firebase_admin
from firebase_admin import auth, firestore
import smtplib
import yfinance as yf
from email.mime.text import MIMEText

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()
ny_tz = pytz.timezone('America/New_York')

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

PCT_THRESHOLD = 130

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

def get_volume_and_price_data(symbols):
    try:
        data = yf.download(symbols, period="7d", group_by='ticker', threads=True)
        stock_data = {}

        for symbol in symbols:
            try:
                vol_data = data[symbol]['Volume']
                close_data = data[symbol]['Close']

                if len(vol_data) < 6 or len(close_data) < 2:
                    continue

                volumes = [
                    int(vol_data.iloc[-1]),
                    int(vol_data.iloc[-2]),
                ]

                prices = [
                    float(close_data.iloc[-1]),
                    float(close_data.iloc[-2]),
                ]

                ma5_yesterday = float(vol_data.iloc[-6:-1].mean())

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


def send_alert_email(email, alert_symbols, stock_data):
    if not alert_symbols:
        return

    pct_threshold = PCT_THRESHOLD

    today = datetime.datetime.now(ny_tz).date()
    current_date = today.strftime("%m/%d/%Y")
    today_name = today.strftime("%A")

    html_body = f"""
    <html>
      <body>
        <p>These <b>{len(alert_symbols)}</b> symbols exhibit unusual trading activity, exceeding {pct_threshold}% of the 5-day average volume:</p>
        <br>
    """

    for symbol in alert_symbols:
        data = stock_data.get(symbol)
        if not data:
            continue

        vols = data['volumes']
        ma5 = data['ma5_yesterday']
        price_change = data['price_change_today']
        price_change_pct = data['price_change_pct_today']

        price_color = "green" if price_change >= 0 else "red"
        price_sign = "+" if price_change >= 0 else "-"

        html_body += f"""
        <p><b>{symbol}</b>: <span style="color: {price_color};">{price_sign}${abs(price_change):.2f} <b>({price_sign}{abs(price_change_pct):.1f}%)</b></span></p>
        <ul>
          <li>Current Volume: {vols[0]:,}</li>
          <li>5-Day Avg Volume: {int(ma5):,}</li>
          <li>Volume Ratio vs 5D MA: {(100 * vols[0] / ma5):.1f}%</li>
        </ul>
        """

    html_body += """
        <br>
        <p>Vigila Team</p>
      </body>
    </html>
    """

    msg = MIMEText(html_body, 'html')
    msg['Subject'] = f"{today_name}'s Volume Alert - {current_date}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)


def check_volume_alerts(request):
    # Step 1: Check if today is an open market session
    today_str = get_market_session_today()
    if not today_str:
        print("Today is not an open market session. Terminating.")
        return "Not a market session today", 200

    # Step 2: Collect all active volume_alerts docs across all users
    alerts_query = db.collection_group("volume_alerts").where("isActive", "==", True).stream()

    all_symbols = set()
    user_alert_docs = {}

    alerts_processed = 0
    for doc in alerts_query:
        data = doc.to_dict()
        symbol = data.get("symbol")
        if not symbol:
            continue

        user_ref = doc.reference.parent.parent
        if not user_ref:
            continue
        uid = user_ref.id

        all_symbols.add(symbol)
        user_alert_docs.setdefault(uid, []).append(
            (doc.reference, symbol, data.get("lastAlertTimestamp"))
        )
        alerts_processed += 1

    if not all_symbols:
        return f"Processed {alerts_processed} alerts", 200

    # Step 3: Batch fetch all stock data
    stock_data = get_volume_and_price_data(list(all_symbols))

    # Step 4: Process each user
    updates_batch = db.batch()

    for uid, alert_docs in user_alert_docs.items():
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
        except Exception as e:
            print(f"Failed to fetch user {uid}: {e}")
            continue

        should_alert = False
        alert_symbols = []
        symbols_to_mark = []

        for doc_ref, symbol, last_alert_timestamp in alert_docs:
            data = stock_data.get(symbol)
            if not data or len(data.get('volumes', [])) < 2:
                continue

            vols = data['volumes']
            ma5_yesterday = data['ma5_yesterday']
            today_vol = vols[0]

            if ma5_yesterday == 0:
                continue

            ratio = (today_vol / ma5_yesterday) * 100
            print(f"[{symbol}] ratio={ratio:.1f}% (threshold={PCT_THRESHOLD}%)")

            if ratio >= PCT_THRESHOLD:
                alert_symbols.append(symbol)

                last_alert_date_str = None
                if last_alert_timestamp is not None:
                    last_alert_date_str = last_alert_timestamp.astimezone(ny_tz).strftime("%Y-%m-%d")

                if last_alert_date_str != today_str:
                    should_alert = True
                    symbols_to_mark.append(doc_ref)
                    print(f"[{symbol}] Volume spike confirmed, last_alert_date={last_alert_date_str}, will alert")
                else:
                    print(f"[{symbol}] Volume spike detected but already alerted today ({last_alert_date_str}), skipping")

        if alert_symbols and should_alert:
            print(f"Sending email to {email} for symbols: {alert_symbols}")
            send_alert_email(email, alert_symbols, stock_data)
            for doc_ref in symbols_to_mark:
                updates_batch.update(doc_ref, {
                    "lastAlertTimestamp": firestore.SERVER_TIMESTAMP,
                })

    updates_batch.commit()

    return f"Processed {alerts_processed} alerts", 200