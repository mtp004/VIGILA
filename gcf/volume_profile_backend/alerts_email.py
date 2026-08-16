import smtplib
from email.mime.text import MIMEText
import datetime
import os
import pytz

ny_tz = pytz.timezone('America/New_York')
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

ZONE_LABELS = ["Below Value Area", "Lower Value Area", "Upper Value Area", "Above Value Area"]
BOUNDARY_NAMES = ["VAL", "POC", "VAH"]  # boundary i separates zone i and zone i+1


def _zone_label(zone_idx):
    return ZONE_LABELS[zone_idx] if 0 <= zone_idx < len(ZONE_LABELS) else f"Zone {zone_idx}"


def _is_upward(info):
    return info["to_zone"] > info["from_zone"]


def _crossed_boundary_names(from_zone, to_zone):
    """Every boundary strictly between from_zone and to_zone was crossed, in order."""
    lo, hi = min(from_zone, to_zone), max(from_zone, to_zone)
    return BOUNDARY_NAMES[lo:hi]


def _crossing_description(info):
    boundary_values = {"VAL": info["val"], "POC": info["poc"], "VAH": info["vah"]}
    crossed = _crossed_boundary_names(info["from_zone"], info["to_zone"])
    direction = "above" if _is_upward(info) else "below"

    if len(crossed) == 1:
        name = crossed[0]
        return f"crossed {direction} {name} (${boundary_values[name]:.2f})"

    names_with_values = ", ".join(f"{n} (${boundary_values[n]:.2f})" for n in crossed)
    return (
        f"jumped from {_zone_label(info['from_zone'])} to {_zone_label(info['to_zone'])}, "
        f"crossing {names_with_values}"
    )


def send_value_area_alert_email(email, crossed_symbols):
    """
    crossed_symbols: {symbol: {"from_zone", "to_zone", "price", "val", "poc", "vah"}}
    """
    if not crossed_symbols:
        return

    now = datetime.datetime.now(ny_tz)
    current_date = now.strftime("%m/%d/%Y")
    today_name = now.strftime("%A")

    html_body = f"""
    <html>
      <body>
        <p><b>{len(crossed_symbols)}</b> symbol(s) crossed a value-area boundary:</p>
        <br>
    """

    for symbol, info in crossed_symbols.items():
        color = "green" if _is_upward(info) else "red"
        description = _crossing_description(info)

        html_body += f"""
        <p><b>{symbol}</b>: <span style="color: {color};">{description}</span></p>
        <ul>
          <li>Current Price: ${info['price']:.2f}</li>
          <li>Now in: {_zone_label(info['to_zone'])}</li>
          <li>VAL: ${info['val']:.2f}</li>
          <li>POC: ${info['poc']:.2f}</li>
          <li>VAH: ${info['vah']:.2f}</li>
        </ul>
        """

    html_body += """
        <br>
        <p>Vigila Team</p>
      </body>
    </html>
    """

    msg = MIMEText(html_body, 'html')
    msg['Subject'] = f"{today_name}'s Value Area Alert - {current_date}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)
