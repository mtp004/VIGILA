import os
import datetime
import firebase_admin
from firebase_admin import auth, firestore
import smtplib
from email.message import EmailMessage
import yfinance as yf
from email.mime.text import MIMEText 

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN")

def save_alerted_timestamp(user_uid, symbols, timestamp):
    """
    Update a symbol alert timestamp with the provided timestamp
    Create one if not yet exist
    """
    try:
        user_doc_ref = db.collection('users').document(user_uid)
        
        # Build the update dict for all symbols at once
        updates = {symbol: timestamp for symbol in symbols}
        
        user_doc_ref.set({
            'volume_alert_timestamps': updates
        }, merge=True)
    except Exception as e:
        print(f"Error saving timestamps: {e}")

def get_volume_data(symbols):
    try:
        # Batch download all symbols at once
        data = yf.download(symbols, period="3d", group_by='ticker', threads=True)
        volume_data = {}
        
        for symbol in symbols:
            try:
                vol_data = data[symbol]['Volume']

                if len(vol_data) < 3:
                    continue

                # index 0 = today, 1 = yesterday, 2 = day before
                volumes = [
                    int(vol_data.iloc[-1]),
                    int(vol_data.iloc[-2]),
                    int(vol_data.iloc[-3])
                ]

                volume_data[symbol] = volumes
            except:
                continue
                
        return volume_data
    except:
        return {}

def send_alert_email(email, user_uid, alert_symbols, yesterday_alert_symbols, volume_data):
    if not alert_symbols:
        return
    
    today = datetime.date.today()
    current_date = today.strftime("%m/%d/%Y")
    today_name = today.strftime("%A")
    yesterday_name = (today - datetime.timedelta(days=1)).strftime("%A")
    
    # 1. Build the HTML body content
    html_body = f"""
    <html>
      <body>
        <p>These <b>{len(alert_symbols)}</b> symbols exhibit unusual trading activity, exceeding 125% of previous session volume:</p>
        <br>
    """

    for symbol in alert_symbols:
        data = volume_data.get(symbol)
        if not data or len(data) < 2:
            continue
        
        html_body += f"""
        <p><b>{symbol}</b>:</p>
        <ul>
          <li>Current Volume: {data[0]:,}</li>
          <li>Previous Volume: {data[1]:,}</li>
          <li>Ratio: {(100 * data[0] / data[1]):.1f}%</li>
        </ul>
        """

    if yesterday_alert_symbols:
        html_body += f"""
        <hr>
        <p><b>{yesterday_name}'s Alert</b> - These <b>{len(yesterday_alert_symbols)}</b> symbols previously exceeded 125% of the day before's volume:</p>
        <br>
        """

        for symbol in yesterday_alert_symbols:
            data = volume_data.get(symbol)
            if not data or len(data) < 3:
                continue

            html_body += f"""
            <p><b>{symbol}</b>:</p>
            <ul>
              <li>Previous Volume: {data[1]:,}</li>
              <li>Day Before Volume: {data[2]:,}</li>
              <li>Ratio: {(100 * data[1] / data[2]):.1f}%</li>
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
    
    alert_timestamp = datetime.datetime.now(datetime.timezone.utc)
    save_alerted_timestamp(user_uid, alert_symbols, alert_timestamp)

def check_volume_alerts(request):
    token = request.args.get("token")
    if token != SECRET_TOKEN:
        return "Unauthorized", 401

    users_processed = 0
    
    # Collect all unique symbols first
    all_symbols = set()
    user_symbols_map = {}
    
    page = auth.list_users()
    while page:
        for user in page.users:
            try:
                user_doc = db.collection('users').document(user.uid).get()
                if not user_doc.exists:
                    continue
                    
                volume_symbols = user_doc.to_dict().get('indicators', {}).get('Volume', [])
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
    
    # Batch download all symbols once
    if all_symbols:
        volume_data = get_volume_data(list(all_symbols))
        
        # Send alerts to users
        today = datetime.date.today()
        for email, user_data in user_symbols_map.items():
            user_doc = db.collection('users').document(user_data['uid']).get()
            alert_timestamps = user_doc.to_dict().get('volume_alert_timestamps', {}) if user_doc.exists else {}
            
            should_alert = False
            alert_symbols = []
            yesterday_alert_symbols = []
            for s in user_data['symbols']:
                vols = volume_data.get(s)
                if not vols or len(vols) < 3:
                    continue

                today_vol = vols[0]
                yesterday_vol = vols[1]
                day_before = vols[2]

                ratio = (today_vol / yesterday_vol) * 100

                previous_ratio = (yesterday_vol / day_before) * 100
                
                # Check timestamp for whether there are any new volume spike that has not been alerted today or not
                if ratio >= 123:
                    alert_symbols.append(s)
                    last_timestamp = alert_timestamps.get(s)
                    if not last_timestamp or last_timestamp.date() < today:
                        should_alert = True
                if previous_ratio >= 123:
                    yesterday_alert_symbols.append(s)
            if alert_symbols and should_alert:
                send_alert_email(email, user_data['uid'], alert_symbols, yesterday_alert_symbols, volume_data)
    
    return f"Processed {users_processed} users", 200