"""Auto trigger: derive each alert's trigger discount from listing history.

Episode method: for a discount x, an episode is a run of consecutive scrape days
whose best qualifying discount is >= x. The trigger is the highest x whose
episode rate (episodes / history days) meets the rate needed to see at least
one episode within the user's patience window with CONFIDENCE probability.
"""
import math
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from google.api_core.exceptions import FailedPrecondition
from google.cloud import bigquery
from firebase_admin import firestore

from giftcard_catalog import load_url_to_brand, normalize_url
from listing_history import LISTINGS_TABLE

# ── Tunables ────────────────────────────────────────────────────────────────
CONFIDENCE = 0.8
PATIENCE_DAYS = {"1m": 30, "3m": 90, "6m": 180}
MIN_EPISODES = 3
HISTORY_MULTIPLIER = 2              # need >= 2 x T scrape days before trusting the result
RECOMPUTE_INTERVAL_HOURS = 20       # full recompute at most once per this window
RECOMPUTE_MAX_SECONDS = 120         # time budget for one recompute
RUN_DEADLINE_SECONDS = 540          # never let a recompute push the run past this (service timeout is 600s)
MIN_RECOMPUTE_SECONDS = 30          # skip the recompute if less than this is left before the deadline
LOOKBACK_DAYS = 366                 # the table keeps 365 days of partitions
DAY_TZ = "America/New_York"

PATIENCE_VALUES = {"manual", *PATIENCE_DAYS}
STATE_DOC = ("app_config", "giftcard_auto_trigger")


# ── Pure computation ────────────────────────────────────────────────────────
def required_rate(patience_days: int) -> float:
    """λ* = -ln(1 - c) / T"""
    return -math.log(1 - CONFIDENCE) / patience_days


def count_episodes(series: list[float | None], x: float) -> int:
    episodes = 0
    inside = False
    for best in series:
        hit = best is not None and best >= x
        if hit and not inside:
            episodes += 1
        inside = hit
    return episodes


def compute_trigger(series: list[float | None], patience_days: int) -> dict:
    """series: daily best qualifying discount per scrape day, oldest first (None = no deal)."""
    history_days = len(series)
    unset = {"computedTrigger": None, "episodes": None, "historyDays": history_days}
    if history_days < HISTORY_MULTIPLIER * patience_days:
        return {**unset, "autoStatus": "collecting"}

    rate = required_rate(patience_days)
    for x in sorted({b for b in series if b is not None}, reverse=True):
        episodes = count_episodes(series, x)
        if episodes / history_days >= rate:
            if episodes < MIN_EPISODES:
                break
            return {"computedTrigger": x, "episodes": episodes,
                    "historyDays": history_days, "autoStatus": "active"}
    return {**unset, "autoStatus": "insufficient_data"}


def build_series(run_days: list[date], group_best: dict[date, float | None]) -> list[float | None]:
    """Days without any scrape run are skipped; history starts at the group's first recorded day."""
    if not group_best:
        return []
    first_day = min(group_best)
    return [group_best.get(d) for d in run_days if d >= first_day]


# ── Alert helpers ───────────────────────────────────────────────────────────
def normalize_patience(value) -> str:
    return value if value in PATIENCE_VALUES else "manual"


def load_user_patience(db, uids) -> dict[str, str]:
    refs = [db.collection("users").document(uid) for uid in set(uids)]
    patience = {}
    for snap in db.get_all(refs):
        data = snap.to_dict() if snap.exists else {}
        patience[snap.id] = normalize_patience(data.get("giftcardPatience"))
    return patience


def effective_trigger(alert_data: dict, patience: str) -> tuple[float, bool]:
    """(trigger, is_auto). Never touches BigQuery: reads only fields already on the alert."""
    computed = alert_data.get("computedTrigger")
    if patience != "manual" and alert_data.get("autoStatus") == "active" and computed is not None:
        return float(computed), True
    return float(alert_data.get("minDiscountPercent", 0.0)), False


def alert_group_key(alert_data: dict, url_to_brand: dict[str, str]):
    """(brandKey, min, max, platforms) or None if the alert's URLs don't map to exactly one brand."""
    toggles = alert_data.get("platforms", {})
    platforms, brands = [], set()
    for platform, url in (alert_data.get("urls") or {}).items():
        if not url or not toggles.get(platform, {}).get("active", True):
            continue
        platforms.append(platform)
        brands.add(url_to_brand.get(normalize_url(url)))
    if not platforms or len(brands) != 1 or None in brands:
        return None
    return (
        brands.pop(),
        float(alert_data.get("minCardValue", 0)),
        float(alert_data.get("maxCardValue", 999999)),
        tuple(sorted(platforms)),
    )


# ── BigQuery ────────────────────────────────────────────────────────────────
def _query_params(today: date, extra=()):
    start = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    return [
        bigquery.ScalarQueryParameter("tz", "STRING", DAY_TZ),
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", start),
        bigquery.ScalarQueryParameter("today", "DATE", today),
        *extra,
    ]


# One query for every group: daily best qualifying discount per group (gid >= 0),
# plus the days the scraper ran at all (gid = -1), so the job overhead is paid once
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


def _groups_param(group_keys: list) -> bigquery.ArrayQueryParameter:
    return bigquery.ArrayQueryParameter("groups", "STRUCT", [
        bigquery.StructQueryParameter(
            None,
            bigquery.ScalarQueryParameter("gid", "INT64", gid),
            bigquery.ScalarQueryParameter("brand", "STRING", brand),
            bigquery.ScalarQueryParameter("min_value", "FLOAT64", min_value),
            bigquery.ScalarQueryParameter("max_value", "FLOAT64", max_value),
            bigquery.ArrayQueryParameter("platforms", "STRING", list(platforms)),
        )
        for gid, (brand, min_value, max_value, platforms) in enumerate(group_keys)
    ])


def fetch_group_history(client, group_keys: list, today: date, timeout: float):
    """Returns (run_days, [daily best by day for each group, in group_keys order])."""
    job = client.query(HISTORY_SQL, job_config=bigquery.QueryJobConfig(
        query_parameters=_query_params(today, [_groups_param(group_keys)])))
    run_days = set()
    group_best = [{} for _ in group_keys]
    for row in job.result(timeout=timeout):
        if row.gid == -1:
            run_days.add(row.d)
        else:
            group_best[row.gid][row.d] = row.best
    return sorted(run_days), group_best


# ── Recompute ───────────────────────────────────────────────────────────────
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


def _collect_targets(db, full: bool):
    """Non-manual alerts to recompute: all of them (full) or only those awaiting a first result."""
    docs = [d for d in db.collection_group("giftcard_alerts").stream() if d.reference.parent.parent]
    patience = load_user_patience(db, [d.reference.parent.parent.id for d in docs])
    targets = []
    for doc in docs:
        p = patience.get(doc.reference.parent.parent.id, "manual")
        if p == "manual":
            continue
        data = doc.to_dict()
        if full or data.get("autoStatus") in (None, "pending"):
            targets.append((doc, data, p))
    return targets


def run_recompute(db, full: bool, deadline: float) -> dict:
    """Recompute auto triggers. Returns a report for the admin email; never raises."""
    started = time.monotonic()
    report = {"mode": "full" if full else "pending", "alerts": 0, "groups": 0,
              "status_counts": {}, "issues": []}
    try:
        targets = _collect_targets(db, full)
        report["alerts"] = len(targets)
        if not targets:
            return report

        url_to_brand = load_url_to_brand(db)
        groups = defaultdict(list)
        results = {}
        for doc, data, patience in targets:
            key = alert_group_key(data, url_to_brand)
            if key is None:
                results[doc.id] = {"computedTrigger": None, "episodes": None,
                                   "historyDays": None, "autoStatus": "unmapped"}
            else:
                groups[key].append((doc, patience))
        report["groups"] = len(groups)

        if groups:
            group_keys = list(groups)
            today = datetime.now(ZoneInfo(DAY_TZ)).date()
            try:
                run_days, group_best = fetch_group_history(
                    bigquery.Client(), group_keys, today, timeout=max(1.0, deadline - time.monotonic()))
            except Exception as e:
                # Every group's alerts keep their previous values
                report["issues"].append(f"History query failed for all {len(group_keys)} groups: {e}")
                print(f"[auto_trigger] History query failed: {e}")
                group_keys = []

            for key, best in zip(group_keys, group_best if group_keys else []):
                try:
                    series = build_series(run_days, best)
                    for doc, patience in groups[key]:
                        results[doc.id] = compute_trigger(series, PATIENCE_DAYS[patience])
                except Exception as e:
                    # Leave this group's alerts untouched; other groups continue
                    brand, min_value, max_value, platforms = key
                    report["issues"].append(
                        f"{brand} ${min_value:g}-${max_value:g} [{', '.join(platforms)}]: {e}")
                    print(f"[auto_trigger] Group {key} failed: {e}")

        status_counts = Counter()
        for doc, _, _ in targets:
            result = results.get(doc.id)
            if result is None:
                continue
            if time.monotonic() >= deadline:
                report["issues"].append("Time budget exhausted while writing results; remaining alerts unchanged")
                break
            try:
                # Precondition: skip alerts the user edited while we were computing
                doc.reference.update({**result, "computedAt": firestore.SERVER_TIMESTAMP},
                                     option=db.write_option(last_update_time=doc.update_time))
                status_counts[result["autoStatus"]] += 1
            except FailedPrecondition:
                print(f"[auto_trigger] Alert {doc.id} changed during recompute; skipped")
        report["status_counts"] = dict(status_counts)
    except Exception as e:
        report["issues"].append(f"Recompute failed: {e}")
        print(f"[auto_trigger] Recompute failed: {e}")
    finally:
        report["seconds"] = round(time.monotonic() - started, 1)
        print(f"[auto_trigger] {report}")
    return report
