import smtplib
from email.mime.text import MIMEText
import datetime
import os
import pytz

ny_tz = pytz.timezone('America/New_York')
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

def send_alert_email(email, alert_symbols, stock_data, pct_threshold, session_date=None, revision=False):
    if not alert_symbols:
        return

    if session_date is None:
        session_date = datetime.datetime.now(ny_tz).date()
    current_date = session_date.strftime("%m/%d/%Y")
    today_name = session_date.strftime("%A")

    revision_note = ""
    if revision:
        revision_note = """
        <p><i>Note: this reflects revised volume data for yesterday's session, updated overnight after market close.</i></p>
        """

    html_body = f"""
    <html>
      <body>
        <p>These <b>{len(alert_symbols)}</b> symbols exhibit unusual trading activity, exceeding {pct_threshold}% of the 5-day average volume:</p>
        {revision_note}
        <br>
    """

    volume_label = "Yesterday's Volume" if revision else "Current Volume"

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
          <li>{volume_label}: {vols[0]:,}</li>
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

    subject_label = "Volume Alert (Revised)" if revision else "Volume Alert"

    msg = MIMEText(html_body, 'html')
    msg['Subject'] = f"{today_name}'s {subject_label} - {current_date}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)