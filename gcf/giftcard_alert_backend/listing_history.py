import os
from datetime import datetime
from google.cloud import bigquery
from giftcard_catalog import normalize_url

LISTINGS_TABLE = os.environ.get("BQ_LISTINGS_TABLE", "vigila-d6c82.vigila.giftcard_listings")


def build_listing_rows(scraped_results: list[dict], url_to_brand: dict[str, str],
                       run_id: str, run_ts: datetime) -> tuple[list[dict], list[str]]:
    """One row per listing from successful scrapes. Returns (rows, unmapped_urls)."""
    rows = []
    unmapped_urls = []
    for res in scraped_results:
        if res["website"] == "unknown":
            continue
        brand = url_to_brand.get(normalize_url(res["url"]))
        if brand is None:
            unmapped_urls.append(res["url"])
            continue
        # Failed scrapes return no discounts, so they contribute no rows
        for card in res["discounts"]:
            rows.append({
                "run_id": run_id,
                "run_ts": run_ts.isoformat(),
                "platform": res["website"],
                "brand": brand,
                "face_value": float(card["face_value"]),
                "discount": float(card["discount_pct"]),
            })
    return sorted(rows, key=lambda r: (r["brand"], r["platform"])), sorted(unmapped_urls)


def write_listing_rows(rows: list[dict]) -> dict | None:
    """Append rows in a single load job. Returns None on success, else {message, row_count}."""
    if not rows:
        return None
    try:
        client = bigquery.Client()
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            # Never auto-create: the table's partitioning and expiry come from bigquery_schema.sql
            create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
        )
        client.load_table_from_json(rows, LISTINGS_TABLE, job_config=job_config).result()
        print(f"[bigquery] Wrote {len(rows)} listing rows to {LISTINGS_TABLE}")
        return None
    except Exception as e:
        print(f"[bigquery] Failed to write {len(rows)} listing rows: {e}")
        return {"message": str(e), "row_count": len(rows)}
