import firebase_admin
firebase_admin.initialize_app()

from firebase_admin import auth, firestore
from volume_profile import build_volume_profile_and_price, fetch_today_bars
from alerts_email import send_value_area_alert_email

# Initialize Firebase
db = firestore.client()

CACHE_ROOT = "volume_profile_cache"  # doc id = symbol; also holds vp.py's months/shards subcollections


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

        print(f"Sending value-area alert to {email} for symbols: {list(relevant.keys())}")
        send_value_area_alert_email(email, relevant)

    return f"Processed {len(all_symbols)} symbols, {len(crossed_symbols)} crossings", 200