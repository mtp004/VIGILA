"""Alert Optimization: set each alert's trigger from listing history (episode method).

An episode for discount x is a run of consecutive scrape days whose best qualifying
discount is >= x. The trigger is the highest x whose episodes / history days meets
-ln(1 - CONFIDENCE) / T, where T is the user's patience in days.
"""
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from google.cloud import bigquery
from firebase_admin import firestore

from giftcard_catalog import load_url_to_brand, normalize_url
from listing_history import LISTINGS_TABLE

CONFIDENCE = 0.8
PATIENCE_DAYS = {"1m": 30, "3m": 90, "6m": 180}
MIN_EPISODES = 3
HISTORY_MULTIPLIER = 2              # need >= 2 x T scrape days of history
RECOMPUTE_INTERVAL_HOURS = 20       # full recompute at most once per window
RECOMPUTE_MAX_SECONDS = 120
RUN_DEADLINE_SECONDS = 540          # service timeout is 600s
MIN_RECOMPUTE_SECONDS = 30          # skip if less than this is left before the deadline
LOOKBACK_DAYS = 366
DAY_TZ = "America/New_York"
STATE_DOC = ("app_config", "giftcard_auto_trigger")


def count_episodes(series: list[float | None], x: float) -> int:
    episodes, inside = 0, False
    for best in series:
        hit = best is not None and best >= x
        episodes += hit and not inside
        inside = hit
    return episodes


def compute_trigger(series: list[float | None], patience_days: int) -> dict:
    """series: daily best qualifying discount per scrape day, oldest first (None = no deal)."""
    days = len(series)
    unset = {"computedTrigger": None, "episodes": None, "historyDays": days}
    if days < HISTORY_MULTIPLIER * patience_days:
        return {**unset, "autoStatus": "collecting"}
    rate = -math.log(1 - CONFIDENCE) / patience_days
    for x in sorted({b for b in series if b is not None}, reverse=True):
        episodes = count_episodes(series, x)
        if episodes / days >= rate:
            if episodes >= MIN_EPISODES:
                return {"computedTrigger": x, "episodes": episodes, "historyDays": days, "autoStatus": "active"}
            break
    return {**unset, "autoStatus": "insufficient_data"}


def build_series(run_days: list, group_best: dict) -> list[float | None]:
    """Skips days with no scrape run; history starts at the group's first recorded day."""
    if not group_best:
        return []
    first_day = min(group_best)
    return [group_best.get(d) for d in run_days if d >= first_day]


def load_user_patience(db, uids) -> dict[str, str]:
    snaps = db.get_all([db.collection("users").document(uid) for uid in set(uids)])
    return {s.id: (s.to_dict() or {}).get("giftcardPatience", "manual") if s.exists else "manual" for s in snaps}


def effective_trigger(alert_data: dict, patience: str) -> float:
    """Uses only fields already on the alert, never BigQuery."""
    if patience in PATIENCE_DAYS and alert_data.get("autoStatus") == "active" and alert_data.get("computedTrigger") is not None:
        return float(alert_data["computedTrigger"])
    return float(alert_data.get("minDiscountPercent", 0.0))


def alert_group_key(alert_data: dict, url_to_brand: dict[str, str]):
    """(brandKey, min, max, sorted platforms), or None unless the enabled URLs map to exactly one brand."""
    toggles = alert_data.get("platforms", {})
    enabled = {p: url for p, url in (alert_data.get("urls") or {}).items()
               if url and toggles.get(p, {}).get("active", True)}
    brands = {url_to_brand.get(normalize_url(url)) for url in enabled.values()}
    if len(brands) != 1 or None in brands:
        return None
    return (brands.pop(), float(alert_data.get("minCardValue", 0)),
            float(alert_data.get("maxCardValue", 999999)), tuple(sorted(enabled)))


# One query for all groups: daily best per group (gid >= 0) plus the days the scraper ran (gid = -1)
HISTORY_SQL = f"""
WITH listings AS (
  SELECT DATE(run_ts, @tz) AS d, brand, platform, face_value, discount
  FROM `{LISTINGS_TABLE}`
  WHERE run_ts >= @start AND DATE(run_ts, @tz) < @today
)
SELECT -1 AS gid, d, CAST(NULL AS FLOAT64) AS best
FROM listings
GROUP BY d
UNION ALL
SELECT g.gid, l.d,
       MAX(IF(l.face_value BETWEEN g.min_value AND g.max_value, l.discount, NULL)) AS best
FROM listings AS l
JOIN UNNEST(@groups) AS g
  ON l.brand = g.brand AND l.platform IN UNNEST(g.platforms)
GROUP BY g.gid, l.d
"""


def fetch_group_history(client, group_keys: list, today, timeout: float):
    """Returns (sorted run days, [{day: best} for each group in group_keys order])."""
    params = [
        bigquery.ScalarQueryParameter("tz", "STRING", DAY_TZ),
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)),
        bigquery.ScalarQueryParameter("today", "DATE", today),
        bigquery.ArrayQueryParameter("groups", "STRUCT", [
            bigquery.StructQueryParameter(
                None,
                bigquery.ScalarQueryParameter("gid", "INT64", gid),
                bigquery.ScalarQueryParameter("brand", "STRING", brand),
                bigquery.ScalarQueryParameter("min_value", "FLOAT64", lo),
                bigquery.ScalarQueryParameter("max_value", "FLOAT64", hi),
                bigquery.ArrayQueryParameter("platforms", "STRING", list(platforms)),
            )
            for gid, (brand, lo, hi, platforms) in enumerate(group_keys)
        ]),
    ]
    job = client.query(HISTORY_SQL, job_config=bigquery.QueryJobConfig(query_parameters=params))
    run_days, group_best = set(), [{} for _ in group_keys]
    for row in job.result(timeout=timeout):
        if row.gid == -1:
            run_days.add(row.d)
        else:
            group_best[row.gid][row.d] = row.best
    return sorted(run_days), group_best


def claim_full_recompute(db) -> bool:
    """Atomically take the once-per-window slot so concurrent runs don't both recompute."""
    ref = db.collection(STATE_DOC[0]).document(STATE_DOC[1])
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def claim(transaction):
        snap = ref.get(transaction=transaction)
        last = snap.to_dict().get("lastRecomputeAt") if snap.exists else None
        if last and now - last < timedelta(hours=RECOMPUTE_INTERVAL_HOURS):
            return False
        transaction.set(ref, {"lastRecomputeAt": now}, merge=True)
        return True

    return claim(db.transaction())


def run_recompute(db, full: bool, deadline: float) -> tuple[dict, dict]:
    """Recompute all non-manual alerts (full) or only pending ones; never raises.
    Returns (report, {alert doc path: fields written})."""
    started = time.monotonic()
    report = {"mode": "full" if full else "pending", "alerts": 0, "groups": 0, "status_counts": {}, "issues": []}
    written = {}
    try:
        docs = list(db.collection_group("giftcard_alerts").stream())
        patience = load_user_patience(db, [d.reference.parent.parent.id for d in docs])
        targets = []
        for doc in docs:
            p = patience.get(doc.reference.parent.parent.id)
            data = doc.to_dict()
            if p in PATIENCE_DAYS and (full or data.get("autoStatus") in (None, "pending")):
                targets.append((doc, data, p))
        report["alerts"] = len(targets)
        if not targets:
            return report, written

        url_to_brand = load_url_to_brand(db)
        groups, results = defaultdict(list), {}
        for doc, data, p in targets:
            key = alert_group_key(data, url_to_brand)
            if key is None:
                results[doc.id] = {"computedTrigger": None, "episodes": None, "historyDays": None, "autoStatus": "unmapped"}
            else:
                groups[key].append((doc, p))
        report["groups"] = len(groups)

        if groups:
            try:
                today = datetime.now(ZoneInfo(DAY_TZ)).date()
                run_days, group_best = fetch_group_history(
                    bigquery.Client(), list(groups), today, timeout=max(1.0, deadline - time.monotonic()))
                for members, best in zip(groups.values(), group_best):
                    series = build_series(run_days, best)
                    for doc, p in members:
                        results[doc.id] = compute_trigger(series, PATIENCE_DAYS[p])
            except Exception as e:
                # Every grouped alert keeps its previous values
                report["issues"].append(f"History query failed: {e}")

        # Batched writes (Firestore allows 500 per batch). An alert edited mid-recompute can
        # get a stale result; the next full pass corrects it.
        to_write = [doc for doc, _, _ in targets if doc.id in results]
        status_counts = Counter()
        for i in range(0, len(to_write), 500):
            if time.monotonic() >= deadline:
                report["issues"].append("Time budget ran out while writing; remaining alerts unchanged")
                break
            batch = db.batch()
            for doc in to_write[i:i + 500]:
                batch.update(doc.reference, {**results[doc.id], "computedAt": firestore.SERVER_TIMESTAMP})
            batch.commit()
            for doc in to_write[i:i + 500]:
                written[doc.reference.path] = results[doc.id]
                status_counts[results[doc.id]["autoStatus"]] += 1
        report["status_counts"] = dict(status_counts)
    except Exception as e:
        report["issues"].append(f"Recompute failed: {e}")
    finally:
        report["seconds"] = round(time.monotonic() - started, 1)
        print(f"[auto_trigger] {report}")
    return report, written
