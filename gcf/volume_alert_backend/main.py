import datetime
import firebase_admin
from firebase_admin import auth, firestore
from market_data import get_market_session_today, get_last_market_session, get_volume_and_price_data_for_date, ny_tz
from alerts_email import send_alert_email

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()

PCT_THRESHOLD = 129

def check_volume_alerts(request):
    # Step 1: Check if today is an open market session
    today_str = get_market_session_today()
    if not today_str:
        print("Today is not an open market session. Terminating.")
        return "Not a market session today", 200

    today_date = datetime.datetime.strptime(today_str, "%Y-%m-%d").date()

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
    stock_data = get_volume_and_price_data_for_date(list(all_symbols), today_date)

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
            send_alert_email(email, alert_symbols, stock_data, PCT_THRESHOLD)
            for doc_ref in symbols_to_mark:
                updates_batch.update(doc_ref, {
                    "lastAlertTimestamp": firestore.SERVER_TIMESTAMP,
                })

    updates_batch.commit()

    return f"Processed {alerts_processed} alerts", 200


def check_last_session_volume_alerts(request):
    """
    Runs once a day (any time) as a catch-up pass. yfinance revises the prior
    day's volume overnight (always higher than the 4PM print, to account for
    afterhours), so a spike that was missed by check_volume_alerts during the
    day can only be caught here, using the now-finalized data.

    Looks up yesterday's bar by actual date via
    get_volume_and_price_data_for_date rather than assuming it's the most
    recent row, since today's bar may already exist by the time this runs.
    """
    # Step 1: Resolve yesterday's session
    yesterday_str = get_last_market_session()
    if not yesterday_str:
        print("Could not resolve yesterday's market session. Terminating.")
        return "No prior market session found", 200

    yesterday_date = datetime.datetime.strptime(yesterday_str, "%Y-%m-%d").date()
    alert_timestamp = ny_tz.localize(datetime.datetime.combine(yesterday_date, datetime.time(16, 0)))

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

    # Step 3: Batch fetch all stock data, looked up by yesterday's exact date
    stock_data = get_volume_and_price_data_for_date(list(all_symbols), yesterday_date)

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
            yesterday_vol = vols[0]

            if ma5_yesterday == 0:
                continue

            ratio = (yesterday_vol / ma5_yesterday) * 100
            print(f"[{symbol}] revised ratio={ratio:.1f}% (threshold={PCT_THRESHOLD}%)")

            if ratio >= PCT_THRESHOLD:
                alert_symbols.append(symbol)

                last_alert_date_str = None
                if last_alert_timestamp is not None:
                    last_alert_date_str = last_alert_timestamp.astimezone(ny_tz).strftime("%Y-%m-%d")

                if last_alert_date_str != yesterday_str:
                    should_alert = True
                    symbols_to_mark.append(doc_ref)
                    print(f"[{symbol}] Revised volume spike confirmed for {yesterday_str}, last_alert_date={last_alert_date_str}, will alert")
                else:
                    print(f"[{symbol}] Revised volume spike already alerted for {yesterday_str}, skipping")

        if alert_symbols and should_alert:
            print(f"Sending revised-volume email to {email} for symbols: {alert_symbols}")
            send_alert_email(email, alert_symbols, stock_data, PCT_THRESHOLD, session_date=yesterday_date, revision=True)
            for doc_ref in symbols_to_mark:
                updates_batch.update(doc_ref, {
                    "lastAlertTimestamp": alert_timestamp,
                })

    updates_batch.commit()

    return f"Processed {alerts_processed} alerts", 200