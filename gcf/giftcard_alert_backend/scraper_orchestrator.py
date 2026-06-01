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

async def scrape_worker(context, url: str, website: str, delay: float) -> dict:
    if website == "unknown":
        return {"url": url, "website": website, "discounts": []}
    await asyncio.sleep(delay)
    try:
        print(f"[*] Firing async connection for: [{website.upper()}] {url}")
        html = await fetch_page(url, context)
        if website == "carddepot":
            discounts = parse_carddepot(html)
        elif website == "gcx":
            discounts = parse_gcx(html)
        elif website == "cardcash":
            discounts = parse_cardcash(html)
        else:
            discounts = []
        return {"url": url, "website": website, "discounts": discounts}
    except Exception as e:
        print(f"[-] Connection dropped or timed out on {url}: {e}")
        return {"url": url, "website": website, "discounts": []}

async def run_orchestrator(url_list: list[str]) -> list[dict]:
    pre_parsed_tasks = [{"url": url, "website": detect_website(url)} for url in url_list]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        tasks = [
            scrape_worker(context, task["url"], task["website"], delay=i*2)
            for i, task in enumerate(pre_parsed_tasks)
        ]
        results = await asyncio.gather(*tasks)
        await browser.close()
        return results