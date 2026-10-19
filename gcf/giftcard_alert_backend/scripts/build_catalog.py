"""One-off helper to populate giftcard_catalog from existing alert URLs.

Review (read-only): prints a table and writes a proposed catalog JSON to edit.
    python scripts/build_catalog.py review --out catalog_proposal.json

Apply (writes Firestore): uploads the reviewed JSON.
    python scripts/build_catalog.py apply catalog_proposal.json
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import firestore
from giftcard_catalog import CATALOG_COLLECTION, normalize_url

SLUG_PATTERNS = {
    "cardcash": r"/buy-gift-cards/discount-(.+)-cards$",
    "carddepot": r"/brands/discount-(.+)-gift-cards$",
    "gcx": r"/buy-(.+)-gift-cards$",
}


def suggest_brand_key(platform: str, normalized_url: str) -> str:
    match = re.search(SLUG_PATTERNS.get(platform, r"$^"), normalized_url)
    slug = match.group(1) if match else normalized_url.rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "_", slug).strip("_")


def collect_urls(db) -> dict:
    """normalizedUrl -> {platform, brand_key, typed: set of user-typed brands}"""
    urls = {}
    for doc in db.collection_group("giftcard_alerts").stream():
        data = doc.to_dict()
        for platform, url in (data.get("urls") or {}).items():
            if not url:
                continue
            norm = normalize_url(url)
            entry = urls.setdefault(norm, {
                "platform": platform,
                "brand_key": suggest_brand_key(platform, norm),
                "typed": set(),
            })
            entry["typed"].add(str(data.get("brand", "")).strip())
    return urls


def review(db, out_path: str):
    urls = collect_urls(db)
    rows = sorted(urls.items(), key=lambda kv: (kv[1]["brand_key"], kv[1]["platform"]))

    headers = ("URL", "PLATFORM", "SUGGESTED KEY", "USER-TYPED BRANDS")
    table = [(u, e["platform"], e["brand_key"], ", ".join(sorted(e["typed"]))) for u, e in rows]
    widths = [max(len(h), *(len(r[i]) for r in table)) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    for r in table:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))

    proposal = defaultdict(lambda: {"displayName": "", "urls": {}})
    for url, e in rows:
        entry = proposal[e["brand_key"]]
        entry["displayName"] = entry["displayName"] or e["brand_key"].replace("_", " ").title()
        if e["platform"] in entry["urls"]:
            print(f"[!] {e['brand_key']} has multiple {e['platform']} URLs; keeping {entry['urls'][e['platform']]}")
            continue
        entry["urls"][e["platform"]] = url

    with open(out_path, "w") as f:
        json.dump(proposal, f, indent=2, sort_keys=True)
    print(f"\n{len(table)} URLs -> {len(proposal)} proposed brand keys. Proposal written to {out_path}")


def apply(db, in_path: str):
    with open(in_path) as f:
        proposal = json.load(f)
    batch = db.batch()
    for brand_key, entry in proposal.items():
        urls = {p: normalize_url(u) for p, u in entry["urls"].items() if u}
        batch.set(db.collection(CATALOG_COLLECTION).document(brand_key),
                  {"displayName": entry["displayName"], "urls": urls})
    batch.commit()
    print(f"Wrote {len(proposal)} docs to {CATALOG_COLLECTION}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("review").add_argument("--out", default="catalog_proposal.json")
    sub.add_parser("apply").add_argument("path")
    args = parser.parse_args()

    firebase_admin.initialize_app(options={"projectId": os.environ.get("GOOGLE_CLOUD_PROJECT", "vigila-d6c82")})
    db = firestore.client()
    if args.cmd == "review":
        review(db, args.out)
    else:
        apply(db, args.path)
