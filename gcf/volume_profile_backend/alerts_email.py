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


def _short_crossing_label(info):
    crossed = _crossed_boundary_names(info["from_zone"], info["to_zone"])
    boundary = crossed[-1] if _is_upward(info) else crossed[0]
    direction = "above" if _is_upward(info) else "below"
    return f"{info['time']} {direction} {boundary}"


def _symbol_block(symbol, entries, is_new):
    entries = sorted(entries, key=lambda e: datetime.datetime.strptime(e["time"], "%I:%M %p"))
    latest = entries[-1]
    count = f" ({len(entries)}x)" if len(entries) > 1 else ""

    if is_new:
        color = "green" if _is_upward(latest) else "red"
        newest_label = f'<span style="color: {color};">{latest["time"]} {_crossing_description(latest)}</span>'
    else:
        newest_label = _short_crossing_label(latest)

    trail = " &rarr; ".join([_short_crossing_label(e) for e in entries[:-1]] + [newest_label])
    header = f'<p><b>{symbol}</b>{count}: {trail}</p>'

    if not is_new:
        return header

    return header + f"""
    <ul>
      <li>Price: ${latest['price']:.2f}</li>
      <li>Now in: {_zone_label(latest['to_zone'])}</li>
      <li>VAL: ${latest['val']:.2f}</li>
      <li>POC: ${latest['poc']:.2f}</li>
      <li>VAH: ${latest['vah']:.2f}</li>
    </ul>
    """


def send_vp_alert_email(email, new_alerts, earlier_alerts=None):
    """
    new_alerts: [{"symbol", "from_zone", "to_zone", "price", "val", "poc", "vah", "time"}, ...]
    earlier_alerts: same shape, alerts already logged today before this run.
    """
    if not new_alerts:
        return
    earlier_alerts = earlier_alerts or []
    new_symbols = {info["symbol"] for info in new_alerts}

    by_symbol = {}
    for info in earlier_alerts + new_alerts:
        by_symbol.setdefault(info["symbol"], []).append(info)

    now = datetime.datetime.now(ny_tz)
    current_date = now.strftime("%m/%d/%Y")
    today_name = now.strftime("%A")
    total_today = len(earlier_alerts) + len(new_alerts)

    html_body = f"""
    <html>
      <body>
        <p><b>{len(new_alerts)}</b> new crossing(s)
        ({total_today} total today):</p>
        <br>
    """

    for symbol, entries in by_symbol.items():
        html_body += _symbol_block(symbol, entries, is_new=symbol in new_symbols)

    html_body += """
        <br>
        <p>Vigila Team</p>
      </body>
    </html>
    """

    msg = MIMEText(html_body, 'html')
    msg['Subject'] = f"{today_name}'s POI Alert - {current_date}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)