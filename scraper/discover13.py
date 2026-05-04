"""Test curl_cffi with website_cookies to access the 2for1 page."""
import pathlib, sys
from curl_cffi import requests
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

cookies = dict(auth.website_cookies or {})
url = "https://www.audible.com/special-promo/2for1?overrideBaseCountry=true&ipRedirectOverride=true"

print(f"Requesting {url} with {len(cookies)} cookies...")
r = requests.get(url, cookies=cookies, impersonate="edge101", allow_redirects=True, timeout=15)
print(f"Status: {r.status_code}  Final URL: {r.url}")

soup = BeautifulSoup(r.text, "html.parser")
print(f"Title: {soup.title.get_text() if soup.title else '?'}")

cards = soup.select(".productListItem")
print(f"Product cards: {len(cards)}")
for card in cards[:5]:
    asin = (card.select_one(".adbl-asin-impression[data-asin]") or {}).get("data-asin", "?")
    h3   = card.select_one("h3.bc-heading")
    sp   = card.select_one(".buybox-sale-price")
    print(f"  {asin} | {h3.get_text(strip=True) if h3 else '?'} | {sp.get_text(strip=True) if sp else 'no price'}")
