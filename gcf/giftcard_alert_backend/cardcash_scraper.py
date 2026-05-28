import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# LIST SCHEMA:
#     "face_value":   face,
#     "discount_pct": pct,
#     "sale_price":   sale,
#     "savings":      round(face - sale, 2),

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
    """Parse gift card denominations, discounts, and sale prices from CardCash HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    
    # 1. Target all individual gift card rows using the base row descriptor class
    rows = soup.find_all("div", class_=lambda x: x and "brand-table-row" in x)
    
    for item in rows:
        try:
            # 2. Extract values dynamically based on internal structural indicators
            # Face value maps to 'eu6gvn920' elements, Sale price maps to 'eu6gvn90' or 'eu6gvn0' base
            face_div = item.find("div", class_=lambda x: x and "eu6gvn920" in x)
            sale_div = item.find("div", class_=lambda x: x and "eu6gvn919" in x)
            disc_span = item.find("span", class_=lambda x: x and "eu6gvn914" in x)
            
            if face_div and sale_div and disc_span:
                # Isolate clean alphanumeric contents out of raw string boundaries
                face_text = face_div.get_text()
                disc_text = disc_span.get_text()
                
                # Use sub-element text scoping to prevent structural extraction duplicates
                sale_text = sale_div.find("span").get_text() if sale_div.find("span") else sale_div.get_text()
                
                # 3. Clean strings and normalize into floating-point numbers
                face = float(face_text.replace("$", "").replace(",", "").strip())
                sale = float(sale_text.replace("$", "").replace(",", "").strip())
                pct  = float(disc_text.replace("%", "").strip())
                
                cards.append({
                    "site":         "cardcash",
                    "face_value":   face,
                    "discount_pct": pct,
                    "sale_price":   sale,
                    "savings":      round(face - sale, 2),
                })
        except (AttributeError, ValueError, IndexError):
            # Skip variations seamlessly if a cell undergoes dynamic layout updates
            continue
 
    return sorted(cards, key=lambda c: c["face_value"], reverse=True)
