"""
Use the audible auth token to make authenticated HTTP requests to the 2for1 page.
No browser needed if the access_token works as a Bearer token.
"""
import pathlib, sys, json
import httpx
import audible
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

print(f"access_token present: {bool(auth.access_token)}")
print(f"website_cookies: {auth.website_cookies}")
print(f"customer_info: {auth.customer_info}")

OVR  = "overrideBaseCountry=true&ipRedirectOverride=true"
BASE = "https://www.audible.com"
URL  = f"{BASE}/special-promo/2for1?{OVR}"

# Build cookie header from website_cookies
cookies = auth.website_cookies or {}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Authorization": f"Bearer {auth.access_token}",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

print(f"\nRequesting: {URL}")
r = httpx.get(URL, headers=headers, cookies=cookies, follow_redirects=True, timeout=15)
print(f"Status: {r.status_code}")
print(f"Final URL: {r.url}")

soup = BeautifulSoup(r.text, "html.parser")
title = soup.find("title")
print(f"Page title: {title.get_text() if title else '?'}")

cards = soup.select(".productListItem")
print(f"Product cards: {len(cards)}")
for card in cards[:3]:
    asin = (card.select_one(".adbl-asin-impression[data-asin]") or {}).get("data-asin", "?")
    h3   = card.select_one("h3.bc-heading")
    sp   = card.select_one(".buybox-sale-price")
    print(f"  {asin} | {h3.get_text(strip=True) if h3 else '?'} | {sp.get_text(strip=True) if sp else 'no price'}")
