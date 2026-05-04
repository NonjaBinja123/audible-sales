"""Check always-a-deal and 2for1 pages for structure and item counts."""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)
OVR  = "overrideBaseCountry=true&ipRedirectOverride=true"
BASE = "https://www.audible.com"

PAGES = [
    ("always-a-deal", f"{BASE}/ep/always-a-deal?{OVR}"),
    ("2for1",         f"{BASE}/special-promo/2for1?{OVR}"),
]

async def check(page, label, url):
    print(f"\n{'='*60}\n{label}: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)
    title = await page.title()
    print(f"  Title: {title}")
    html  = await page.content()
    soup  = BeautifulSoup(html, "html.parser")
    cards = soup.select(".productListItem")
    print(f"  Cards: {len(cards)}")
    for card in cards[:3]:
        asin = (card.select_one(".adbl-asin-impression[data-asin]") or {}).get("data-asin")
        h3   = card.select_one("h3.bc-heading")
        sp   = card.select_one(".buybox-sale-price")
        print(f"    {asin} | {h3.get_text(strip=True) if h3 else '?'} | {sp.get_text(strip=True) if sp else 'no price'}")
    next_link = soup.select_one("a[href*='pageNext']")
    print(f"  Has next page: {bool(next_link)}")
    if next_link:
        import re
        m = re.search(r'page=(\d+)', next_link["href"])
        print(f"  Next page #: {m.group(1) if m else '?'}")

async def main():
    cookies = [
        {"name": k, "value": v, "domain": ".audible.com", "path": "/"}
        for k, v in (auth.website_cookies or {}).items()
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        ctx  = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        if cookies:
            await ctx.add_cookies(cookies)
        pg = await ctx.new_page()
        for label, url in PAGES:
            await check(pg, label, url)
        await browser.close()

asyncio.run(main())
