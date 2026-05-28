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
            await page.wait_for_timeout(2000)
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
                await page.wait_for_timeout(2000)
                html = await page.content()
            finally:
                await browser.close()
            return html
        
def parse_html_discounts(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for item in soup.find_all("label", class_="brand-item"):
        try:
            face_text = item.find("div", class_="brand-item-value").get_text()
            disc_text = item.find("div", class_="brand-item-discount").get_text()
            sale_text = item.find("div", class_="brand-item-price").get_text()
            
            face = float(face_text.replace("$", "").replace(",", "").strip())
            pct  = float(disc_text.replace("% off", "").strip())
            sale = float(sale_text.replace("$", "").replace(",", "").strip())
            
            cards.append({
                "face_value":   face,
                "discount_pct": pct,
                "sale_price":   sale,
                "savings":      round(face - sale, 2),
            })
        except (AttributeError, ValueError):
            continue
    return sorted(cards, key=lambda c: c["face_value"], reverse=True)