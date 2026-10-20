from urllib.parse import urlsplit, urlunsplit

CATALOG_COLLECTION = "giftcard_catalog"


def normalize_url(url: str) -> str:
    """Lowercase, drop query string and fragment, drop trailing slash."""
    parts = urlsplit(url.strip().lower())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def load_url_to_brand(db) -> dict[str, str]:
    """Invert giftcard_catalog/{brandKey}.urls into normalizedUrl -> brandKey."""
    url_to_brand = {}
    for doc in db.collection(CATALOG_COLLECTION).stream():
        for url in (doc.to_dict().get("urls") or {}).values():
            if url:
                url_to_brand[normalize_url(url)] = doc.id
    return url_to_brand
