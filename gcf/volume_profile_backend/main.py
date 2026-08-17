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
ALERT_LOG_DAYS_TO_KEEP = 7  # volume_profile_cache/{symbol}/alert_log/{YYYY-MM-DD} -> {"alerts": [...]}
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


def _symbol_log_ref(symbol, date_str):
    return db.collection(CACHE_ROOT).document(symbol).collection("alert_log").document(date_str)


def _prune_old_alert_days(symbol, keep=ALERT_LOG_DAYS_TO_KEEP):
    log_ref = db.collection(CACHE_ROOT).document(symbol).collection("alert_log")
    doc_ids = sorted((doc.id for doc in log_ref.list_documents()), reverse=True)

    for stale_id in doc_ids[keep:]:
        log_ref.document(stale_id).delete()
        print(f"[{symbol}] Pruned stale alert log {stale_id}")


def _log_symbol_alert(symbol, info, now):
    """
    Appends this run's alerts to the symbol's shared log for today and
    returns (earlier, entry): earlier is whatever was already logged for
    this symbol today before this call, entry is this alert with
    symbol/time folded in. Called once per triggered symbol regardless of
    how many users are subscribed to it, since the alert itself is
    identical for all of them.
    """
    date_str = now.strftime("%Y-%m-%d")
    log_ref = _symbol_log_ref(symbol, date_str)
    log_doc = log_ref.get()
    earlier = log_doc.to_dict().get("alerts", []) if log_doc.exists else []

    entry = {**info, "symbol": symbol, "time": now.strftime("%I:%M %p")}
    log_ref.set({"alerts": firestore.ArrayUnion([entry])}, merge=True)
    _prune_old_alert_days(symbol)

    return earlier, entry


def _get_symbol_alerts_today(symbol, date_str):
    log_doc = _symbol_log_ref(symbol, date_str).get()
    return log_doc.to_dict().get("alerts", []) if log_doc.exists else []


def check_volume_profile_alerts(request):
    all_symbols, user_symbols = _collect_active_symbols_and_users()
    if not all_symbols:
        return "No active symbols", 200

    triggered_symbols = {}
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
            triggered_symbols[symbol] = {
                "from_zone": from_zone,
                "to_zone": to_zone,
                "price": current_price,
                "val": vp["val"],
                "poc": vp["poc"],
                "vah": vp["vah"],
            }
        else:
            print(f"[{symbol}] No zone change (zone={to_zone}, price={current_price})")

    if not triggered_symbols:
        return f"Processed {len(all_symbols)} symbols, no alerts", 200

    now = datetime.datetime.now(ny_tz)
    date_str = now.strftime("%Y-%m-%d")

    symbol_earlier = {}
    symbol_new_entry = {}
    for symbol in all_symbols:
        if symbol in triggered_symbols:
            earlier, entry = _log_symbol_alert(symbol, triggered_symbols[symbol], now)
            symbol_earlier[symbol] = earlier
            symbol_new_entry[symbol] = entry
        else:
            symbol_earlier[symbol] = _get_symbol_alerts_today(symbol, date_str)

    for uid, symbols in user_symbols.items():
        new_entries = [symbol_new_entry[s] for s in symbols if s in symbol_new_entry]
        if not new_entries:
            continue
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
        except Exception as e:
            print(f"Failed to fetch user {uid}: {e}")
            continue

        earlier_alerts = [a for s in symbols for a in symbol_earlier.get(s, [])]
        print(f"Sending value-area alert to {email} for symbols: {[e['symbol'] for e in new_entries]}")
        send_vp_alert_email(email, new_entries, earlier_alerts)

    return f"Processed {len(all_symbols)} symbols, {len(triggered_symbols)} alerts", 200