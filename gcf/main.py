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

def get_volume_data(symbols):
    try:
        # Batch download all symbols at once
        data = yf.download(symbols, period="2d", group_by='ticker', threads=True)
        volume_data = {}
        
        for symbol in symbols:
            try:
                vol_data = data[symbol]['Volume']

                if len(vol_data) < 2:
                    continue
                              
                current_vol = vol_data.iloc[-1]
                previous_vol = vol_data.iloc[-2]
                
                if previous_vol > 0:
                    ratio = (current_vol / previous_vol) * 100
                    volume_data[symbol] = {
                        'current_volume': int(current_vol),
                        'previous_volume': int(previous_vol),
                        'ratio': ratio
                    }
            except:
                continue
                
        return volume_data
    except:
        return {}

def send_alert_email(email, alert_symbols, volume_data):
    if not alert_symbols:
        return
    
    current_date = datetime.date.today().strftime("%m/%d/%Y")
    
    # 1. Build the HTML body content
    html_body = f"""
    <html>
      <body>
        <p>Volume Alert - These <b>{len(alert_symbols)}</b> symbols exhibit unusual trading activity, exceeding 125% of previous day volume:</p>
        <br>
    """
    
    for symbol in alert_symbols:
        data = volume_data[symbol]
        
        html_body += f"""
        <p><b>{symbol}</b>:</p>
        <ul>
          <li>Current Volume: {data['current_volume']:,}</li>
          <li>Previous Volume: {data['previous_volume']:,}</li>
          <li>Ratio: {data['ratio']:.1f}%</li>
        </ul>
        """
    
    html_body += """
        <br>
        <p>Vigila Team</p>
      </body>
    </html>
    """
    
    msg = MIMEText(html_body, 'html') 
    
    msg['Subject'] = f"Vigila High Volume Alert - {current_date}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

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
                
                user_symbols_map[user.email] = user_symbol_list
                users_processed += 1
            except:
                continue
        
        page = page.get_next_page()
    
    # Batch download all symbols once
    if all_symbols:
        volume_data = get_volume_data(list(all_symbols))
        
        # Send alerts to users
        for email, symbols in user_symbols_map.items():
            alert_symbols = [s for s in symbols if volume_data.get(s, {}).get('ratio', 0) >= 123]
            if alert_symbols:
                send_alert_email(email, alert_symbols, volume_data)
    
    return f"Processed {users_processed} users", 200