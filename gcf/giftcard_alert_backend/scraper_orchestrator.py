import sys
import json
import asyncio

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install playwright beautifulsoup4")
    print("  playwright install chromium")
    sys.exit(1)

try:
    from carddepot_scraper import parse_html_discounts as parse_carddepot, fetch_page
    from gcx_scraper import parse_html_discounts as parse_gcx
    from cardcash_scraper import parse_html_discounts as parse_cardcash
except ImportError as e:
    print(f"[-] Module loading error: Ensure scraper scripts are in this directory. Details: {e}")
    sys.exit(1)

# =====================================================================
# 1. PRE-PARSE ANALYSIS LAYER
# =====================================================================
def detect_website(url: str) -> str:
    url_lower = url.lower()
    if "carddepot.com" in url_lower: return "carddepot"
    if "gcx.app" in url_lower:       return "gcx"
    if "cardcash.com" in url_lower:  return "cardcash"
    return "unknown"

# =====================================================================
# 2. CLEAN CONCURRENT SCRAE WORKER
# =====================================================================
async def scrape_worker(context, url: str, website: str, brand: str, delay: float) -> dict:
    if website == "unknown" or brand == "unknown":
        return {"url": url, "website": website, "brand": brand, "discounts": []}

    # Stagger execution to prevent Cloudflare/anti-bot rate limiting on concurrent requests
    await asyncio.sleep(delay)

    try:
        print(f"[*] Firing async connection for: [{website.upper()}] {brand}")
        html = await fetch_page(url, context)
        
        if website == "carddepot":
            discounts = parse_carddepot(html)
        elif website == "gcx":
            discounts = parse_gcx(html)
        elif website == "cardcash":
            discounts = parse_cardcash(html)
        else:
            discounts = []

        return {
            "url": url,
            "website": website,
            "brand": brand,
            "discounts": discounts
        }
    except Exception as e:
        print(f"[-] Connection dropped or timed out on {url}: {e}")
        return {"url": url, "website": website, "brand": brand, "discounts": []}

# =====================================================================
# 3. PIPELINE ORCHESTRATOR
# =====================================================================
async def run_orchestrator(url_tasks: list[tuple[str, str]]) -> list[dict]:
    pre_parsed_tasks = []
    for url, brand in url_tasks:
        website = detect_website(url)
        pre_parsed_tasks.append({"url": url, "website": website, "brand": brand})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        tasks = [
            scrape_worker(context, task["url"], task["website"], task["brand"], delay=i*2)
            for i, task in enumerate(pre_parsed_tasks)
        ]
        
        results = await asyncio.gather(*tasks)
        
        await browser.close()
        return results

if __name__ == "__main__":
    TEST_URLS = [
        ("https://www.cardcash.com/buy-gift-cards/discount-apple-(not-itunes)-cards/", "apple"),
        ("https://carddepot.com/brands/discount-nike-gift-cards", "nike"),
        ("https://gcx.app/buy-nike-gift-cards", "nike"),
        ("https://www.cardcash.com/buy-gift-cards/discount-nike-cards/", "nike"),
    ]
    
    output_matrix = asyncio.run(run_orchestrator(TEST_URLS))
    print("\n" + "="*60 + "\nORCHESTRATOR OUTPUT MATRIX:\n" + "="*60)
    print(json.dumps(output_matrix, indent=2))