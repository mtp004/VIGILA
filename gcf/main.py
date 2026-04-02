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


def get_last_two_market_sessions():
    """
    Returns (today_str, last_session_str) as "YYYY-MM-DD" strings.
    Returns (None, None) if today is not an open market session.
    """
    today = datetime.datetime.now(ny_tz).date()
    spy = yf.download("SPY", period="10d", interval="1d", progress=False)
    open_days = spy.index.date

    if len(open_days) < 2 or open_days[-1] != today:
        return None, None

    today_str = today.strftime("%Y-%m-%d")
    last_session_str = open_days[-2].strftime("%Y-%m-%d")
    return today_str, last_session_str


def sync_timestamp_structure(user_uid, today_str):
    user_doc_ref = db.collection('users').document(user_uid)
    user_doc = user_doc_ref.get()
    if not user_doc.exists:
        return {}

    data = user_doc.to_dict()
    timestamps = (
        data.get('indicators', {})
            .get('Volume', {})
            .get('cached', {})
            .get('timestamps', {})
    )

    updates = {}
    for date_key in list(timestamps.keys()):
        if date_key != today_str:
            updates[f'indicators.Volume.cached.timestamps.{date_key}'] = firestore.DELETE_FIELD

    if today_str not in timestamps:
        updates[f'indicators.Volume.cached.timestamps.{today_str}'] = {}

    if updates:
        user_doc_ref.update(updates)

    return timestamps.get(today_str, {})


def save_alerted_timestamps(user_uid, symbols, today_str, timestamp):
    """
    Write triggered alert timestamps into indicators.Volume.cached.timestamps.<today>
    """
    user_doc_ref = db.collection('users').document(user_uid)
    updates = {
        f'indicators.Volume.cached.timestamps.{today_str}.{symbol}': timestamp
        for symbol in symbols
    }
    try:
        user_doc_ref.update(updates)
    except Exception as e:
        print(f"Save failed: {e}")


def get_volume_and_price_data(symbols):
    try:
        data = yf.download(symbols, period="3d", group_by='ticker', threads=True)
        stock_data = {}

        for symbol in symbols:
            try:
                vol_data = data[symbol]['Volume']
                close_data = data[symbol]['Close']

                if len(vol_data) < 3 or len(close_data) < 3:
                    continue

                volumes = [
                    int(vol_data.iloc[-1]),
                    int(vol_data.iloc[-2]),
                    int(vol_data.iloc[-3])
                ]

                prices = [
                    float(close_data.iloc[-1]),
                    float(close_data.iloc[-2]),
                    float(close_data.iloc[-3])
                ]

                price_change_today = prices[0] - prices[1]
                price_change_pct_today = (price_change_today / prices[1]) * 100

                stock_data[symbol] = {
                    'volumes': volumes,
                    'prices': prices,
                    'price_change_today': price_change_today,
                    'price_change_pct_today': price_change_pct_today
                }
            except:
                continue

        return stock_data
    except:
        return {}


def send_alert_email(email, user_uid, alert_symbols, yesterday_alert_symbols, stock_data, today_str, last_session_str):
    if not alert_symbols and not yesterday_alert_symbols:
        return

    today = datetime.date.today()
    current_date = today.strftime("%m/%d/%Y")
    today_name = today.strftime("%A")
    last_session_name = datetime.datetime.strptime(last_session_str, "%Y-%m-%d").strftime("%A")

    html_body = f"""
    <html>
      <body>
        <p>These <b>{len(alert_symbols)}</b> symbols exhibit unusual trading activity, exceeding 125% of previous session volume:</p>
        <br>
    """

    for symbol in alert_symbols:
        data = stock_data.get(symbol)
        if not data:
            continue

        vols = data['volumes']
        price_change = data['price_change_today']
        price_change_pct = data['price_change_pct_today']

        price_color = "green" if price_change >= 0 else "red"
        price_sign = "+" if price_change >= 0 else "-"

        html_body += f"""
        <p><b>{symbol}</b>: <span style="color: {price_color};">{price_sign}${abs(price_change):.2f} <b>({price_sign}{abs(price_change_pct):.1f}%)</b></span></p>
        <ul>
          <li>Current Volume: {vols[0]:,}</li>
          <li>Previous Volume: {vols[1]:,}</li>
          <li>Volume Ratio: {(100 * vols[0] / vols[1]):.1f}%</li>
        </ul>
        """

    if yesterday_alert_symbols:
        html_body += f"""
        <hr>
        <p><b>{last_session_name}'s Alert</b> - These <b>{len(yesterday_alert_symbols)}</b> symbols previously exceeded 125% of the session before's volume:</p>
        <br>
        """

        for symbol in yesterday_alert_symbols:
            data = stock_data.get(symbol)
            if not data or len(data.get('volumes', [])) < 3:
                continue

            vols = data['volumes']

            html_body += f"""
            <p><b>{symbol}</b>:</p>
            <ul>
              <li>Previous Volume: {vols[1]:,}</li>
              <li>Day Before Volume: {vols[2]:,}</li>
              <li>Volume Ratio: {(100 * vols[1] / vols[2]):.1f}%</li>
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

    alert_timestamp = datetime.datetime.now(ny_tz)
    save_alerted_timestamps(user_uid, alert_symbols, today_str, alert_timestamp)


def check_volume_alerts(request):
    # Step 1: Check if today is an open market session
    today_str, last_session_str = get_last_two_market_sessions()
    if not today_str:
        print("Today is not an open market session. Terminating.")
        return "Not a market session today", 200

    users_processed = 0
    vol_ratio_threshold = 123
    all_symbols = set()
    user_symbols_map = {}

    # Step 2: Collect all users and symbols
    page = auth.list_users()
    while page:
        for user in page.users:
            try:
                user_doc = db.collection('users').document(user.uid).get()
                if not user_doc.exists:
                    continue

                volume_symbols = user_doc.to_dict().get('indicators', {}) .get('Volume', {}).get('symbols', [])
                user_symbol_list = []

                for symbol_obj in volume_symbols:
                    symbol = symbol_obj.get('symbol')
                    user_symbol_list.append(symbol)
                    all_symbols.add(symbol)

                user_symbols_map[user.email] = {
                    'uid': user.uid,
                    'symbols': user_symbol_list
                }
                users_processed += 1
            except:
                continue

        page = page.get_next_page()

    # Step 3: Batch fetch all stock data
    if not all_symbols:
        return f"Processed {users_processed} users", 200

    stock_data = get_volume_and_price_data(list(all_symbols))

    # Step 4: Process each user
    for email, user_data in user_symbols_map.items():
        # Sync timestamp structure and get today's already-alerted symbols
        today_timestamps = sync_timestamp_structure(
            user_data['uid'], today_str)

        should_alert = False
        alert_symbols = []
        yesterday_alert_symbols = []

        for s in user_data['symbols']:
            data = stock_data.get(s)
            if not data or len(data.get('volumes', [])) < 3:
                continue

            vols = data['volumes']
            today_vol = vols[0]
            yesterday_vol = vols[1]
            day_before = vols[2]

            ratio = (today_vol / yesterday_vol) * 100
            previous_ratio = (yesterday_vol / day_before) * 100

            if ratio >= vol_ratio_threshold:
                alert_symbols.append(s)
                if s not in today_timestamps:
                    should_alert = True

            if previous_ratio >= vol_ratio_threshold and s not in alert_symbols:
                yesterday_alert_symbols.append(s)

        if (alert_symbols and should_alert) or yesterday_alert_symbols:
            send_alert_email(
                email, user_data['uid'],
                alert_symbols, yesterday_alert_symbols,
                stock_data, today_str, last_session_str
            )

    return f"Processed {users_processed} users", 200