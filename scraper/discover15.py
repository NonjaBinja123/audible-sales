"""
Test the 2for1 category node URLs for server-rendered product cards.
"""
import pathlib, sys, re
from curl_cffi import requests
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)
cookies = dict(auth.website_cookies or {})
BASE = "https://www.audible.com"
OVR  = "overrideBaseCountry=true&ipRedirectOverride=true"

# First fetch the main page to get all node IDs
main = requests.get(f"{BASE}/special-promo/2for1?{OVR}", cookies=cookies,
                    impersonate="edge101", timeout=15)
nodes = list(dict.fromkeys(re.findall(r'/special-promo/2for1/cat\?node=(\d+)', main.text)))
print(f"Found {len(nodes)} category nodes: {nodes}")

# Test each node
session = requests.Session(impersonate="edge101")
for node in nodes:
    url = f"{BASE}/special-promo/2for1/cat?node={node}&{OVR}"
    r = session.get(url, cookies=cookies, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select(".productListItem")
    title = soup.title.get_text(strip=True) if soup.title else "?"
    next_link = soup.select_one("a[href*='pageNext']")
    print(f"\nnode={node} | status={r.status_code} | title={title!r} | cards={len(cards)} | has_next={bool(next_link)}")
    for card in cards[:2]:
        asin = (card.select_one(".adbl-asin-impression[data-asin]") or {}).get("data-asin", "?")
        h3   = card.select_one("h3.bc-heading")
        sp   = card.select_one(".buybox-sale-price")
        cp   = card.select_one(".buybox-regular-price")
        print(f"  {asin} | {h3.get_text(strip=True) if h3 else '?'} | sale={sp.get_text(strip=True) if sp else '?'} | reg={cp.get_text(strip=True) if cp else '?'}")
