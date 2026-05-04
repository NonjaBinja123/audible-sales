"""
Use Playwright to explore the Audible deals pages and understand
the HTML structure before writing the real scraper.
"""
import asyncio, json, sys, pathlib, re
from playwright.async_api import async_playwright

OUT = pathlib.Path(__file__).parent / "discover_out"
OUT.mkdir(exist_ok=True)

OVR = "overrideBaseCountry=true&ipRedirectOverride=true"
ENTRY_POINTS = [
    ("audiobook-deals", f"https://www.audible.com/ep/audiobook-deals?{OVR}"),
    ("2for1",           f"https://www.audible.com/special-promo/2for1?{OVR}"),
    ("daily-deal",      f"https://www.audible.com/deals?{OVR}"),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()

        for name, url in ENTRY_POINTS:
            print(f"\n{'='*60}")
            print(f"Visiting: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            title = await page.title()
            print(f"Page title: {title}")

            # Save screenshot
            await page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
            print(f"Screenshot saved: discover_out/{name}.png")

            # Look for JSON-LD structured data
            ld_scripts = await page.eval_on_selector_all(
                'script[type="application/ld+json"]',
                "els => els.map(e => e.textContent)"
            )
            if ld_scripts:
                print(f"JSON-LD blocks: {len(ld_scripts)}")
                for i, s in enumerate(ld_scripts[:2]):
                    print(f"  LD[{i}]: {s[:300]}")

            # Look for product cards — try common Audible selectors
            selectors = [
                "li[data-asin]",
                "[data-asin]",
                ".bc-list-item",
                ".productListItem",
                ".adbl-prod-module",
                "li.bc-list-item",
            ]
            for sel in selectors:
                count = await page.locator(sel).count()
                if count:
                    print(f"  Selector '{sel}': {count} elements")
                    # Show data-asin of first few
                    for i in range(min(3, count)):
                        el = page.locator(sel).nth(i)
                        asin = await el.get_attribute("data-asin")
                        txt = (await el.inner_text())[:80].replace("\n", " ")
                        print(f"    [{i}] asin={asin} | {txt}")

            # Find all links containing sale-related keywords
            hrefs = await page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.href)"
            )
            sale_links = [h for h in hrefs if any(
                k in h for k in ["promo", "deal", "sale", "special"]
            )]
            print(f"Sale-related links: {len(sale_links)}")
            for l in sorted(set(sale_links))[:15]:
                print(f"  {l}")

        await browser.close()

asyncio.run(main())
