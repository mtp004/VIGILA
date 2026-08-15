import datetime
import firebase_admin
from firebase_admin import auth, firestore
from market_data import get_market_session_today, get_last_market_session, get_volume_and_price_data_for_date, ny_tz
from alerts_email import send_alert_email

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()

PCT_THRESHOLD = 129

# --- Config for folding the revised check into check_volume_alerts ---
# Only attempt the revised-session check on invocations at/after this NY hour.
# (Keep this <= the first intraday invocation you want it to piggyback on.)
REVISE_CHECK_EARLIEST_HOUR = 8
REVISE_CLAIM_DOC = db.collection("system").document("revised_check_state")


def _collect_active_alerts():
    """
    Collects all active volume_alerts docs across all users.
    Returns (all_symbols, user_alert_docs, alerts_processed).
    """
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

    return all_symbols, user_alert_docs, alerts_processed


def _try_claim_daily_revise_check(claim_key):
    """
    Atomically claims today's revised-session check so only one invocation
    of check_volume_alerts actually runs it, no matter how many times the
    intraday cron fires. Returns True if THIS invocation won the claim.
    """
    transaction = db.transaction()

    @firestore.transactional
    def _claim(txn):
        snapshot = REVISE_CLAIM_DOC.get(transaction=txn)
        last_claimed = snapshot.get("lastClaimedKey") if snapshot.exists else None
        if last_claimed == claim_key:
            return False
        txn.set(REVISE_CLAIM_DOC, {
            "lastClaimedKey": claim_key,
            "claimedAt": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        return True

    return _claim(transaction)


def _run_revised_session_check():
    """
    The body of the old check_last_session_volume_alerts, extracted so it
    can be called either standalone or from inside check_volume_alerts.
    """
    yesterday_str = get_last_market_session()
    if not yesterday_str:
        print("Could not resolve yesterday's market session. Terminating.")
        return

    yesterday_date = datetime.datetime.strptime(yesterday_str, "%Y-%m-%d").date()
    alert_timestamp = ny_tz.localize(datetime.datetime.combine(yesterday_date, datetime.time(16, 0)))

    all_symbols, user_alert_docs, alerts_processed = _collect_active_alerts()
    if not all_symbols:
        print(f"Revised check: processed {alerts_processed} alerts, no symbols")
        return

    stock_data = get_volume_and_price_data_for_date(list(all_symbols), yesterday_date)

    updates_batch = db.batch()

    for uid, alert_docs in user_alert_docs.items():
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
        except Exception as e:
            print(f"Failed to fetch user {uid}: {e}")
            continue

        alert_symbols = []

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
            print(
                f"[{symbol}] revised raw_data={data} "
                f"yesterday_vol={yesterday_vol:,} "
                f"ma5_yesterday={ma5_yesterday:,.2f} "
                f"ratio={ratio:.1f}% (threshold={PCT_THRESHOLD}%)"
            )

            if ratio >= PCT_THRESHOLD:
                last_alert_date_str = None
                if last_alert_timestamp is not None:
                    last_alert_date_str = last_alert_timestamp.astimezone(ny_tz).strftime("%Y-%m-%d")

                if last_alert_date_str != yesterday_str:
                    alert_symbols.append((doc_ref, symbol))
                    print(f"[{symbol}] Revised volume spike confirmed for {yesterday_str}, will alert")
                else:
                    print(f"[{symbol}] Revised volume spike already alerted for {yesterday_str}, skipping")

        if alert_symbols:
            symbols = [symbol for _, symbol in alert_symbols]
            print(f"Sending revised-volume email to {email} for symbols: {symbols}")
            send_alert_email(email, symbols, stock_data, PCT_THRESHOLD, session_date=yesterday_date, revision=True)
            for doc_ref, _ in alert_symbols:
                updates_batch.update(doc_ref, {"lastAlertTimestamp": alert_timestamp})

    updates_batch.commit()
    print(f"Revised check: processed {alerts_processed} alerts")


def check_volume_alerts(request):
    now_ny = datetime.datetime.now(ny_tz)

    # --- Revised-session check: at most once per calendar day, regardless
    # of how many times this cron fires. Placed ABOVE the market-session
    # gate below so it still runs on days the market itself is closed
    # (e.g. checking Friday's revision on a Monday holiday). ---
    if now_ny.hour >= REVISE_CHECK_EARLIEST_HOUR:
        claim_key = now_ny.strftime("%Y-%m-%d")
        if _try_claim_daily_revise_check(claim_key):
            print(f"[revise-check] Won daily claim for {claim_key}, running it")
            _run_revised_session_check()
        else:
            print(f"[revise-check] Already claimed for {claim_key}, skipping")
    else:
        print(f"[revise-check] Skipping, before earliest hour (now={now_ny.hour}, earliest={REVISE_CHECK_EARLIEST_HOUR})")

    # Step 1: Check if today is an open market session
    today_str = get_market_session_today()
    if not today_str:
        print("Today is not an open market session. Terminating.")
        return "Not a market session today", 200

    today_date = datetime.datetime.strptime(today_str, "%Y-%m-%d").date()

    # Step 2: Collect all active volume_alerts docs across all users
    all_symbols, user_alert_docs, alerts_processed = _collect_active_alerts()

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