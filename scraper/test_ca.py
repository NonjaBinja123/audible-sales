"""Check CA monthly-deals-all pagination and sample data."""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from scraper import _make_session, _scrape_listing
from bs4 import BeautifulSoup

session = _make_session()
base = "https://www.audible.ca"
url  = f"{base}/ep/monthly-deals-all"

r    = session.get(url, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")
next_link = soup.select_one("a[href*='pageNext']")
print(f"Cards on page 0: {len(soup.select('.productListItem'))}")
print(f"Has next page: {bool(next_link)}")
if next_link:
    print(f"Next href: {next_link['href'][:80]}")

items = _scrape_listing(session, url, "monthly", region="ca", base=base)
print(f"\nTotal items scraped: {len(items)}")
for item in items[:5]:
    print(f"  {item['asin']} | {(item['title'] or '')[:40]} | ${item['price']} | {item['region']}")
