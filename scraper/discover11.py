"""
Inject audible website_cookies on BOTH .audible.com AND .amazon.com
so Amazon's SSO check passes when 2for1 redirects to amazon.com/ap/signin.
"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

OVR  = "overrideBaseCountry=true&ipRedirectOverride=true"
BASE = "https://www.audible.com"

async def main():
    cookies = []
    for name, value in (auth.website_cookies or {}).items():
        for domain in [".audible.com", ".amazon.com"]:
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})

    print(f"Injecting {len(cookies)} cookies across both domains")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        await ctx.add_cookies(cookies)

        page = await ctx.new_page()
        url  = f"{BASE}/special-promo/2for1?{OVR}"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        title = await page.title()
        print(f"Page title: {title}")

        html  = await page.content()
        soup  = BeautifulSoup(html, "html.parser")
        cards = soup.select(".productListItem")
        print(f"Product cards: {len(cards)}")
        for card in cards[:5]:
            asin = (card.select_one(".adbl-asin-impression[data-asin]") or {}).get("data-asin", "?")
            h3   = card.select_one("h3.bc-heading")
            sp   = card.select_one(".buybox-sale-price")
            print(f"  {asin} | {h3.get_text(strip=True) if h3 else '?'} | {sp.get_text(strip=True) if sp else 'no price'}")

        await browser.close()

asyncio.run(main())
