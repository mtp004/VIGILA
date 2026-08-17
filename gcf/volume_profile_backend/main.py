import datetime
import pytz

import firebase_admin
firebase_admin.initialize_app()

from firebase_admin import auth, firestore
from volume_profile import build_volume_profile_and_price, fetch_today_bars
from alerts_email import send_vp_alert_email

# Initialize Firebase
db = firestore.client()

CACHE_ROOT = "volume_profile_cache"  # doc id = symbol; also holds vp.py's months/shards subcollections
ALERT_LOG_ROOT = "volume_profile_alert_log"  # {uid}/days/{YYYY-MM-DD} -> {"alerts": [...]}
ALERT_LOG_DAYS_TO_KEEP = 7
ny_tz = pytz.timezone('America/New_York')


def _collect_active_symbols_and_users():
    """
    Same source as the volume-alert list: every active volume_alerts doc
    across all users. Returns (all_symbols, user_symbols) where
    user_symbols maps uid -> set(symbol) for that user's active alerts.
    """
    alerts_query = db.collection_group("volume_alerts").where("isActive", "==", True).stream()

    all_symbols = set()
    user_symbols = {}

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
        user_symbols.setdefault(uid, set()).add(symbol)

    return all_symbols, user_symbols


def _zone(price, sorted_bounds):
    """
    Classifies `price` against 3 sorted boundary values into one of 4 zones:
    0 = below all three, 1/2 = between adjacent boundaries, 3 = above all.
    """
    idx = 0
    for bound in sorted_bounds:
        if price > bound:
            idx += 1
        else:
            break
    return idx


def _save_last_price(state_ref, price):
    state_ref.set({"lastPrice": price, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)


def _prune_old_alert_days(uid, keep=ALERT_LOG_DAYS_TO_KEEP):
    days_ref = db.collection(ALERT_LOG_ROOT).document(uid).collection("days")
    doc_ids = sorted((doc.id for doc in days_ref.list_documents()), reverse=True)

    for stale_id in doc_ids[keep:]:
        days_ref.document(stale_id).delete()
        print(f"[{uid}] Pruned stale alert log {stale_id}")


def _log_and_get_todays_alerts(uid, new_alerts):
    """
    Appends this run's crossings to the user's log for today and returns
    (earlier, new_entries): earlier is whatever was already logged today
    before this call, new_entries is this run's crossings with symbol/time
    folded in. Callers pass both to the email so it can show today's full
    picture instead of just the latest crossing.
    """
    now = datetime.datetime.now(ny_tz)
    date_str = now.strftime("%Y-%m-%d")
    day_ref = db.collection(ALERT_LOG_ROOT).document(uid).collection("days").document(date_str)
    day_doc = day_ref.get()
    earlier = day_doc.to_dict().get("alerts", []) if day_doc.exists else []

    new_entries = [
        {**info, "symbol": symbol, "time": now.strftime("%I:%M %p")}
        for symbol, info in new_alerts.items()
    ]
    day_ref.set({"alerts": firestore.ArrayUnion(new_entries)}, merge=True)
    _prune_old_alert_days(uid)

    return earlier, new_entries


def check_volume_profile_alerts(request):
    all_symbols, user_symbols = _collect_active_symbols_and_users()
    if not all_symbols:
        return "No active symbols", 200

    crossed_symbols = {}
    today_bars = fetch_today_bars(all_symbols)

    for symbol in all_symbols:
        result = build_volume_profile_and_price(symbol, today_bars)
        if result is None:
            print(f"[{symbol}] Could not build volume profile, skipping")
            continue

        vp, current_price = result
        if current_price is None:
            print(f"[{symbol}] No current price available, skipping")
            continue

        bounds = sorted([vp["val"], vp["poc"], vp["vah"]])
        state_ref = db.collection(CACHE_ROOT).document(symbol)
        state_doc = state_ref.get()
        last_price = state_doc.to_dict().get("lastPrice") if state_doc.exists else None

        if last_price is None:
            _save_last_price(state_ref, current_price)
            print(f"[{symbol}] No prior state, initializing at price={current_price}")
            continue

        # Classify both prices against TODAY's boundaries, so a boundary
        # shift (e.g. month rollover onto a new base VP) never looks like
        # a price cross that didn't actually happen.
        from_zone = _zone(last_price, bounds)
        to_zone = _zone(current_price, bounds)
        _save_last_price(state_ref, current_price)

        if from_zone != to_zone:
            print(
                f"[{symbol}] Zone change {from_zone} -> {to_zone} "
                f"(price {last_price} -> {current_price}, "
                f"VAL={vp['val']} POC={vp['poc']} VAH={vp['vah']})"
            )
            crossed_symbols[symbol] = {
                "from_zone": from_zone,
                "to_zone": to_zone,
                "price": current_price,
                "val": vp["val"],
                "poc": vp["poc"],
                "vah": vp["vah"],
            }
        else:
            print(f"[{symbol}] No zone change (zone={to_zone}, price={current_price})")

    if not crossed_symbols:
        return f"Processed {len(all_symbols)} symbols, no crossings", 200

    for uid, symbols in user_symbols.items():
        relevant = {s: crossed_symbols[s] for s in symbols if s in crossed_symbols}
        if not relevant:
            continue
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
        except Exception as e:
            print(f"Failed to fetch user {uid}: {e}")
            continue

        earlier, new_entries = _log_and_get_todays_alerts(uid, relevant)
        print(f"Sending value-area alert to {email} for symbols: {list(relevant.keys())}")
        send_vp_alert_email(email, new_entries, earlier)

    return f"Processed {len(all_symbols)} symbols, {len(crossed_symbols)} crossings", 200