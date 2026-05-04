"""
Parse the saved deals-hub HTML to find all fields in a product card.
"""
import sys, re, json
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

html = open("scraper/discover_out/deals-hub.html", encoding="utf-8").read()
soup = BeautifulSoup(html, "html.parser")

cards = soup.select(".productListItem")
print(f"Total cards: {len(cards)}")

# Dump the full text + key elements of the first 3 cards
for i, card in enumerate(cards[:3]):
    print(f"\n{'='*60}\nCARD {i}")

    # Full text (cleaned)
    text = " | ".join(t.strip() for t in card.stripped_strings if t.strip())
    print(f"  FULL TEXT: {text[:400]}")

    # Specific elements
    for sel, label in [
        ("[data-asin]",          "asin_el"),
        ("h3",                   "h3"),
        ("h2",                   "h2"),
        (".authorLabel",         "authorLabel"),
        (".narratorLabel",       "narratorLabel"),
        ("[class*='narrator']",  "narrator_cls"),
        ("[class*='author']",    "author_cls"),
        ("[class*='price']",     "price_cls"),
        ("[class*='genre']",     "genre_cls"),
        ("[class*='runtime']",   "runtime_cls"),
        ("[class*='rating']",    "rating_cls"),
        ("img[src*='amazon']",   "img"),
        ("a[href*='/pd/']",      "pd_link"),
    ]:
        els = card.select(sel)
        if els:
            for el in els[:2]:
                txt = el.get_text(strip=True)[:80]
                attrs = {k: v for k, v in el.attrs.items() if k in ("class","data-asin","src","href","alt")}
                print(f"  [{label}] {txt!r} | {attrs}")

# Also look for the daily deal section separately
print("\n\n=== PAGE SECTION STRUCTURE ===")
for section in soup.select("section, [class*='section'], [data-widget-id]")[:20]:
    h = section.find(["h1","h2","h3"])
    heading = h.get_text(strip=True) if h else ""
    cards_in = len(section.select(".productListItem"))
    asin_in = len(section.select("[data-asin]"))
    cls = " ".join(section.get("class", []))[:60]
    if heading or cards_in:
        print(f"  section heading={heading!r:40} cards={cards_in} asins={asin_in} class={cls!r}")
