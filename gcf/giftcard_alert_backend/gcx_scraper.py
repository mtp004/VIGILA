import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# LIST SCHEMA:
#     "face_value":   face,
#     "discount_pct": pct,
#     "sale_price":   sale,
#     "savings":      round(face - sale, 2),
GCX_SESSION_DOC = ("app_config", "gcx_session")
 
 
def load_gcx_session(db) -> dict | None:
    """Fetch the saved GCX storage_state dict from Firestore, or None if absent/unset."""
    if db is None:
        return None
    try:
        collection, doc_id = GCX_SESSION_DOC
        doc = db.collection(collection).document(doc_id).get()
        if not doc.exists:
            print("[*] No GCX session doc found in Firestore — proceeding unauthenticated.")
            return None
        state = doc.to_dict().get("state")
        if not state:
            print("[*] GCX session doc exists but has no 'state' field — proceeding unauthenticated.")
            return None
        return state
    except Exception as e:
        print(f"[-] Failed to load GCX session from Firestore: {e}")
        return None
 
 
def save_gcx_session(db, state: dict) -> None:
    """Persist a refreshed GCX storage_state dict back to Firestore."""
    if db is None or not state:
        return
    try:
        from firebase_admin import firestore
        collection, doc_id = GCX_SESSION_DOC
        db.collection(collection).document(doc_id).set({
            "state": state,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        print("[*] Refreshed GCX session saved to Firestore.")
    except Exception as e:
        print(f"[-] Failed to save GCX session to Firestore: {e}")
        
async def fetch_page(url: str, context=None) -> str:
    if context:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(30000)
            html = await page.content()
        finally:
            await page.close()
        return html
    else:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            temp_context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = await temp_context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(30000)
                html = await page.content()
            finally:
                await browser.close()
            return html

def parse_html_discounts(html: str) -> list[dict]:
    """Parse gift card denominations, discounts, and sale prices from GCX HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    
    # 1. Target all individual gift card rows using a partial CSS class match
    # (Using lambda allows us to bypass the volatile trailing random hashes)
    rows = soup.find_all("div", class_=lambda x: x and "grouped-listing_listingRow" in x)
    
    for item in rows:
        try:
            # 2. Extract values based on sequential order and specific classes
            value_divs = item.find_all("div", class_=lambda x: x and "grouped-listing_value" in x)
            disc_div = item.find("div", class_=lambda x: x and "grouped-listing_discount" in x)
            
            # Ensure we found all required fields before unpacking
            if len(value_divs) >= 2 and disc_div:
                face_text = value_divs[0].get_text()  # First match is Face Value
                sale_text = value_divs[1].get_text()  # Second match is Sale Price
                disc_text = disc_div.get_text()
                
                # 3. Clean strings and normalize into floating-point numbers
                face = float(face_text.replace("$", "").replace(",", "").strip())
                pct  = float(disc_text.replace("% OFF", "").replace("% off", "").strip())
                sale = float(sale_text.replace("$", "").replace(",", "").strip())
                
                cards.append({
                    "site":         "gcx",
                    "face_value":   face,
                    "discount_pct": pct,
                    "sale_price":   sale,
                    "savings":      round(face - sale, 2),
                })
        except (AttributeError, ValueError, IndexError):
            # Skip rows if data is corrupt or formatting changes mid-render
            continue
 
    return sorted(cards, key=lambda c: c["face_value"], reverse=True)