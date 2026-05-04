"""
Save full page HTML and extract product data via JS for analysis.
"""
import asyncio, json, pathlib, sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
OUT = pathlib.Path(__file__).parent / "discover_out"
OUT.mkdir(exist_ok=True)

OVR = "overrideBaseCountry=true&ipRedirectOverride=true"

async def scrape_page(page, url, label):
    print(f"\n{'='*60}\n{label}: {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  Load error: {e}")
        return

    html = await page.content()
    out_file = OUT / f"{label}.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"  Saved HTML to discover_out/{label}.html ({len(html)} chars)")

    # Parse with BS4 to extract product cards
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".productListItem")
    print(f"  Product cards: {len(cards)}")

    for i, card in enumerate(cards[:3]):
        asin_el = card.select_one("[data-asin]")
        asin = asin_el["data-asin"] if asin_el else "?"

        # Title
        title_el = card.select_one("h3, .bc-heading, [class*='title']")
        title = title_el.get_text(strip=True)[:60] if title_el else "?"

        # Author
        author_el = card.select_one(".authorLabel, [class*='author']")
        author = author_el.get_text(strip=True)[:40] if author_el else "?"

        # Price — look for $ signs
        price_text = " ".join(card.get_text().split())
        import re
        prices = re.findall(r'\$[\d,.]+', price_text)

        # Cover image
        img = card.select_one("img[src*='media-amazon']")
        cover = img["src"] if img else "?"

        # Link
        link_el = card.select_one("a[href*='/pd/']")
        link = link_el["href"] if link_el else "?"

        print(f"\n  [{i}] ASIN={asin}")
        print(f"      title={title!r}")
        print(f"      author={author!r}")
        print(f"      prices={prices}")
        print(f"      cover={cover[:80]!r}")
        print(f"      link={link[:80]!r}")

    # Also look for section headers to understand page structure
    print("\n  Section headings:")
    for h in soup.select("h2, h3, .bc-heading")[:10]:
        txt = h.get_text(strip=True)
        if txt and len(txt) > 3:
            print(f"    {h.name}: {txt[:80]!r}")


async def main():
    auth = audible.Authenticator.from_file(AUTH_FILE)
    website_cookies = auth.website_cookies or {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        if website_cookies:
            await ctx.add_cookies([
                {"name": k, "value": v, "domain": ".audible.com", "path": "/"}
                for k, v in website_cookies.items()
            ])

        page = await ctx.new_page()

        await scrape_page(page, f"https://www.audible.com/ep/audiobook-deals?{OVR}", "deals-hub")
        await scrape_page(page, f"https://www.audible.com/ep/monthly-deals-all?{OVR}", "monthly-all")
        await scrape_page(page, f"https://www.audible.com/special-promo/2for1?{OVR}", "2for1")

        await browser.close()

asyncio.run(main())
