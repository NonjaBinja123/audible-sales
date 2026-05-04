"""
Find product data embedded in the 2for1 page HTML —
look for JSON blobs, script tags with data, and API URLs.
"""
import pathlib, sys, re, json
from curl_cffi import requests
from bs4 import BeautifulSoup
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)
cookies = dict(auth.website_cookies or {})
OVR = "overrideBaseCountry=true&ipRedirectOverride=true"
URL = f"https://www.audible.com/special-promo/2for1?{OVR}"

r = requests.get(URL, cookies=cookies, impersonate="edge101", timeout=15)
html = r.text

# Save raw HTML for manual inspection
out = pathlib.Path(__file__).parent / "discover_out" / "2for1_raw.html"
out.write_text(html, encoding="utf-8")
print(f"Saved {len(html)} chars to discover_out/2for1_raw.html")

# Look for JSON-LD or embedded data
soup = BeautifulSoup(html, "html.parser")

# 1. Script tags with JSON
print("\n=== Script tags with data ===")
for tag in soup.find_all("script"):
    src = tag.get("src", "")
    txt = tag.string or ""
    if any(k in txt for k in ["asin", "ASIN", "product", "catalog", "items"]):
        print(f"  type={tag.get('type')} | {txt[:300]!r}")

# 2. window.__STATE__ / initial data patterns
print("\n=== Embedded state variables ===")
for m in re.finditer(r'window\.__(\w+)\s*=\s*(\{.*?\});', html, re.DOTALL):
    print(f"  window.__{m.group(1)}: {m.group(2)[:200]}")

# 3. API endpoint URLs in the HTML/JS
print("\n=== API-like URLs referenced ===")
api_urls = set(re.findall(r'["\'](https?://[^\s"\']*(?:catalog|product|promo|offer|browse)[^\s"\']*)["\']', html))
for u in sorted(api_urls)[:20]:
    print(f"  {u}")

# 4. Any JSON arrays with "asin" fields
print("\n=== JSON blobs containing ASINs ===")
for m in re.finditer(r'\{[^{}]*"asin"\s*:\s*"([A-Z0-9]{10})"[^{}]*\}', html):
    print(f"  {m.group()[:200]}")
    if len(list(re.finditer(r'"asin"', html[:m.start()]))) > 5:
        break
