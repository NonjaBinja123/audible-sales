"""
Examine the HTML structure of product cards on the deals pages,
and inject audible auth cookies for the 2for1 page.
"""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
OUT = pathlib.Path(__file__).parent / "discover_out"
OUT.mkdir(exist_ok=True)

OVR = "overrideBaseCountry=true&ipRedirectOverride=true"

async def dump_product_cards(page, label):
    print(f"\n{'='*60}\n{label}")
    await page.wait_for_timeout(2000)

    # Get full HTML of first productListItem
    cards = page.locator(".productListItem")
    count = await cards.count()
    print(f"  .productListItem count: {count}")

    if count > 0:
        html = await cards.nth(0).inner_html()
        print(f"\n  === FIRST CARD HTML (truncated to 3000 chars) ===")
        print(html[:3000])

    # Try to extract data from [data-asin] elements with actual ASINs
    asin_els = page.locator("[data-asin]:not([data-asin='Not Applicable'])")
    asin_count = await asin_els.count()
    print(f"\n  [data-asin] elements with real ASINs: {asin_count}")
    for i in range(min(5, asin_count)):
        el = asin_els.nth(i)
        asin = await el.get_attribute("data-asin")
        # Try to find price within the element
        try:
            price = await el.locator(".bc-color-price, [class*='price'], .buybox-regular-price").first.inner_text()
        except:
            price = "n/a"
        print(f"    [{i}] asin={asin} price={price!r}")


async def main():
    auth = audible.Authenticator.from_file(AUTH_FILE)

    # Extract cookies from audible auth for browser injection
    website_cookies = auth.website_cookies or {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )

        # Inject audible website cookies so 2for1 page doesn't require login
        if website_cookies:
            cookie_list = [
                {"name": k, "value": v, "domain": ".audible.com", "path": "/"}
                for k, v in website_cookies.items()
            ]
            await ctx.add_cookies(cookie_list)
            print(f"Injected {len(cookie_list)} auth cookies")
        else:
            print("No website_cookies found in auth — 2for1 may require login")

        page = await ctx.new_page()

        # 1. Main deals hub
        await page.goto(f"https://www.audible.com/ep/audiobook-deals?{OVR}", wait_until="networkidle")
        await dump_product_cards(page, "AUDIOBOOK DEALS HUB")
        await page.screenshot(path=str(OUT / "hub_full.png"), full_page=True)

        # 2. Monthly deals all
        await page.goto(f"https://www.audible.com/ep/monthly-deals-all?{OVR}", wait_until="networkidle")
        await dump_product_cards(page, "MONTHLY DEALS ALL")

        # 3. 2for1 promo
        await page.goto(f"https://www.audible.com/special-promo/2for1?{OVR}", wait_until="networkidle")
        title = await page.title()
        print(f"\n{'='*60}\n2FOR1 PAGE title: {title}")
        await page.screenshot(path=str(OUT / "2for1_authed.png"))
        await dump_product_cards(page, "2FOR1 PROMO")

        await browser.close()

asyncio.run(main())
