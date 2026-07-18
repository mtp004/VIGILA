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
    from gcx_scraper import parse_html_discounts as parse_gcx, load_gcx_session, save_gcx_session
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

async def scrape_worker(context, url: str, website: str, delay: float, max_attempts: int = 3, backoff_timer: int = 60) -> dict:
    if website == "unknown":
        return {"url": url, "website": website, "discounts": []}
    
    await asyncio.sleep(delay)

    for attempt in range(max_attempts):
        try:
            print(f"[*] Firing async connection for: [{website.upper()}] {url} (attempt {attempt + 1}/{max_attempts})")
            html = await fetch_page(url, context)
            
            if website == "carddepot":
                discounts = parse_carddepot(html)
            elif website == "gcx":
                discounts = parse_gcx(html)
            elif website == "cardcash":
                discounts = parse_cardcash(html)
            else:
                discounts = []

            if discounts:
                print(f"[+] Successfully scraped {len(discounts)} discounts for [{website.upper()}] {url}")
                return {"url": url, "website": website, "discounts": discounts}
        except Exception as e:
            print(f"[-] Attempt {attempt + 1}/{max_attempts} failed for {url}: {e}")

        if attempt < max_attempts - 1:
            await asyncio.sleep(backoff_timer)

    return {"url": url, "website": website, "discounts": []}

async def run_orchestrator(url_list: list[str], db=None) -> list[dict]:
    pre_parsed_tasks = [{"url": url, "website": detect_website(url)} for url in url_list]
    results = []

    context_kwargs = dict(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    gcx_session = load_gcx_session(db)
    if gcx_session:
        print("[*] Loaded GCX session from Firestore.")
        context_kwargs["storage_state"] = gcx_session

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(**context_kwargs)
        tasks = [
            asyncio.ensure_future(
                scrape_worker(context, task["url"], task["website"], delay=i*3)
            )
            for i, task in enumerate(pre_parsed_tasks)
        ]
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)

        if gcx_session is not None or any(t["website"] == "gcx" for t in pre_parsed_tasks):
            try:
                refreshed_state = await context.storage_state()
                save_gcx_session(db, refreshed_state)
            except Exception as e:
                print(f"[-] Could not capture refreshed GCX session: {e}")

        await browser.close()
    return results