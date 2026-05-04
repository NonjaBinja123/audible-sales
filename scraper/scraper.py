import csv, json, os, pathlib, re, subprocess, sys
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from curl_cffi import requests as curl
from dotenv import load_dotenv
import audible

load_dotenv()

ROOT      = pathlib.Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "sales.json"
CSV_FILE  = ROOT / "data" / "sales.csv"
AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"

CSV_FIELDS = [
    "type","asin","title","author","narrator","genre","tags",
    "length_hours","rating","rating_count","price","regular_price",
    "cover_url","audible_url",
]

OVR  = "overrideBaseCountry=true&ipRedirectOverride=true"
BASE = "https://www.audible.com"


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def _make_session(cookies: dict | None = None) -> curl.Session:
    s = curl.Session(impersonate="edge101")
    if cookies:
        s.cookies.update(cookies)
    return s


def _auth_cookies() -> dict:
    auth = audible.Authenticator.from_file(AUTH_FILE)
    return dict(auth.website_cookies or {})


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_card(card, sale_type: str) -> dict | None:
    asin_el = card.select_one(".adbl-asin-impression[data-asin]")
    if not asin_el:
        return None
    asin = asin_el.get("data-asin", "")
    if not asin or asin == "Not Applicable":
        return None

    h3    = card.select_one("h3.bc-heading")
    title = h3.get_text(strip=True) if h3 else None

    author_el = card.select_one(".authorLabel")
    author = re.sub(r'^By:\s*', '', author_el.get_text(strip=True)) if author_el else None

    narrator_el = card.select_one(".narratorLabel")
    narrator = re.sub(r'^Narrated by:\s*', '', narrator_el.get_text(strip=True)) if narrator_el else None

    length_hours = None
    runtime_el = card.select_one(".runtimeLabel")
    if runtime_el:
        rt   = runtime_el.get_text(strip=True)
        h    = int(m.group(1)) if (m := re.search(r'(\d+)\s+hr',  rt)) else 0
        mins = int(m.group(1)) if (m := re.search(r'(\d+)\s+min', rt)) else 0
        length_hours = round(h + mins / 60, 1) if (h or mins) else None

    rating = rating_count = None
    rating_el = card.select_one(".ratingsLabel")
    if rating_el:
        rt = rating_el.get_text(strip=True)
        if m := re.search(r'(\d+\.\d)([\d,]+)', rt):
            rating       = float(m.group(1))
            rating_count = int(m.group(2).replace(",", ""))

    # Cash sale price (monthly deals); absent for 2for1 (credit-based)
    price = None
    sale_el = card.select_one(".buybox-sale-price")
    if sale_el:
        if m := re.search(r'\$([\d.]+)', sale_el.get_text()):
            price = float(m.group(1))

    # Regular/list price
    regular_price = None
    reg_el = card.select_one(".buybox-regular-price")
    if reg_el:
        if m := re.search(r'\$([\d.]+)', reg_el.get_text()):
            regular_price = float(m.group(1))

    img       = card.select_one("img[src*='media-amazon']")
    cover_url = img.get("src") if img else None

    return {
        "type":          sale_type,
        "asin":          asin,
        "title":         title,
        "author":        author,
        "narrator":      narrator,
        "genre":         None,
        "length_hours":  length_hours,
        "rating":        rating,
        "rating_count":  rating_count,
        "price":         price,
        "regular_price": regular_price,
        "cover_url":     cover_url,
        "audible_url":   f"{BASE}/pd/{asin}",
    }


def _scrape_listing(session: curl.Session, start_url: str, sale_type: str) -> list[dict]:
    """Scrape a paginated product listing page, return all items."""
    items: list[dict] = []
    seen:  set[str]   = set()
    url = start_url
    page_num = 0

    while True:
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} on {url}", file=sys.stderr)
            break

        soup  = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".productListItem")
        new   = 0
        for card in cards:
            item = _parse_card(card, sale_type)
            if item and item["asin"] not in seen:
                items.append(item)
                seen.add(item["asin"])
                new += 1

        if not new:
            break
        print(f"    Page {page_num}: +{new} (total so far: {len(items)})")

        next_link = soup.select_one("a[href*='pageNext']")
        if not next_link:
            break
        m = re.search(r'[?&]page=(\d+)', next_link["href"])
        if not m:
            break
        # Build clean next-page URL using the same base
        base_url = re.sub(r'[?&]page=\d+', '', url).rstrip('&').rstrip('?')
        sep = '&' if '?' in base_url else '?'
        url = f"{base_url}{sep}page={m.group(1)}"
        page_num += 1

    return items


# ---------------------------------------------------------------------------
# Daily deal helpers
# ---------------------------------------------------------------------------

def _find_daily_deal_asin(soup) -> str | None:
    widget = soup.select_one('[id*="adbl-daily-deal"]')
    if not widget:
        return None
    link = widget.select_one('a[href*="/pd/"]')
    if not link:
        return None
    m = re.search(r'/pd/([A-Z0-9]{10})', link.get('href', ''))
    return m.group(1) if m else None


def _fetch_daily_deal(asin: str) -> dict | None:
    """Fetch daily deal item: price from product page, metadata from API."""
    # Price from product page (reflects live sale price)
    session = _make_session()
    price = regular_price = None
    try:
        r    = session.get(f"{BASE}/pd/{asin}?{OVR}", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        sale_el = soup.select_one(".buybox-sale-price")
        if sale_el:
            if m := re.search(r'\$([\d.]+)', sale_el.get_text()):
                price = float(m.group(1))
        reg_el = soup.select_one(".buybox-regular-price")
        if reg_el:
            if m := re.search(r'\$([\d.]+)', reg_el.get_text()):
                regular_price = float(m.group(1))
    except Exception as e:
        print(f"  Daily deal page error: {e}", file=sys.stderr)

    # Metadata from API
    try:
        auth = audible.Authenticator.from_file(AUTH_FILE)
        with audible.Client(auth=auth) as client:
            resp = client.get(
                f"1.0/catalog/products/{asin}",
                response_groups="product_desc,contributors,media,rating",
            )
        p        = resp.get("product", resp)
        authors  = p.get("authors")  or []
        narrs    = p.get("narrators") or []
        runtime  = p.get("runtime_length_min") or 0
        overall  = (p.get("rating") or {}).get("overall_distribution") or {}
        return {
            "type":          "daily",
            "asin":          asin,
            "title":         p.get("title"),
            "author":        ", ".join(c.get("name","") for c in authors if c.get("name")),
            "narrator":      ", ".join(n.get("name","") for n in narrs   if n.get("name")),
            "genre":         None,
            "tags":          None,
            "length_hours":  round(runtime / 60, 1) if runtime else None,
            "rating":        float(overall.get("display_average_rating", 0) or 0) or None,
            "rating_count":  int(overall.get("num_ratings", 0) or 0) or None,
            "price":         price,
            "regular_price": regular_price,
            "cover_url":     (p.get("product_images") or {}).get("500"),
            "audible_url":   f"{BASE}/pd/{asin}",
        }
    except Exception as e:
        print(f"  Daily deal API error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Monthly deals (public — no auth needed)
# ---------------------------------------------------------------------------

def scrape_monthly() -> list[dict]:
    session = _make_session()
    url     = f"{BASE}/ep/audiobook-deals?{OVR}"
    print(f"  Starting at {url}")

    # Identify daily deal ASIN from page 0 before full scrape
    try:
        r0          = session.get(url, timeout=20)
        soup0       = BeautifulSoup(r0.text, "html.parser")
        daily_asin  = _find_daily_deal_asin(soup0)
        if daily_asin:
            print(f"  Daily deal ASIN: {daily_asin}")
    except Exception:
        daily_asin = None

    items = _scrape_listing(session, url, "monthly")

    if daily_asin:
        print(f"  Fetching daily deal data...")
        daily_item = _fetch_daily_deal(daily_asin)
        if daily_item:
            items.append(daily_item)

    return items


# ---------------------------------------------------------------------------
# 2-for-1 promo (auth required)
# ---------------------------------------------------------------------------

def scrape_2for1() -> list[dict]:
    cookies = _auth_cookies()
    session = _make_session(cookies)

    # Fetch main promo page to discover category nodes
    r = session.get(f"{BASE}/special-promo/2for1?{OVR}", timeout=20)
    if r.status_code != 200:
        print(f"  2for1 page returned {r.status_code}", file=sys.stderr)
        return []

    nodes = list(dict.fromkeys(
        re.findall(r'/special-promo/2for1/cat\?node=(\d+)', r.text)
    ))
    print(f"  Found {len(nodes)} category nodes")

    if not nodes:
        print("  No nodes found — sale may not be active or auth failed", file=sys.stderr)
        return []

    all_items: list[dict] = []
    seen: set[str] = set()

    for node in nodes:
        url = f"{BASE}/special-promo/2for1/cat?node={node}&{OVR}"
        print(f"  Node {node}:")
        items = _scrape_listing(session, url, "2for1")
        for item in items:
            if item["asin"] not in seen:
                all_items.append(item)
                seen.add(item["asin"])

    return all_items


# ---------------------------------------------------------------------------
# Tag enrichment via Audible API
# ---------------------------------------------------------------------------

def _extract_tags(product: dict) -> str:
    tags = []
    for ladder in (product.get("category_ladders") or []):
        for rung in (ladder.get("ladder") or []):
            name = rung.get("name", "").strip()
            if name and name not in tags:
                tags.append(name)
    for kw in (product.get("thesaurus_subject_keywords") or []):
        kw = kw.strip()
        if kw and kw not in tags:
            tags.append(kw)
    return "; ".join(tags)


def enrich_tags(sales: list[dict]) -> list[dict]:
    needs = [s for s in sales if s.get("tags") is None]
    if not needs:
        print("  Tags already up to date.")
        return sales

    print(f"  Enriching {len(needs)} items with Audible category data...")
    print("  (First run may take several minutes — subsequent runs only process new items)")

    auth   = audible.Authenticator.from_file(AUTH_FILE)
    by_asin = {s["asin"]: s for s in sales}
    done   = 0

    with audible.Client(auth=auth) as client:
        for sale in needs:
            asin = sale["asin"]
            try:
                resp    = client.get(
                    f"1.0/catalog/products/{asin}",
                    response_groups="product_attrs,product_desc",
                )
                product = resp.get("product", resp)
                by_asin[asin]["tags"] = _extract_tags(product)
            except Exception as e:
                by_asin[asin]["tags"] = ""
                print(f"  Warning: could not enrich {asin}: {e}", file=sys.stderr)
            done += 1
            if done % 100 == 0:
                print(f"  Enriched {done}/{len(needs)}...")

    print(f"  Done enriching {len(needs)} items.")
    return list(by_asin.values())


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": None, "sales": []}


def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    by_asin = {s["asin"]: s for s in existing}
    for item in fresh:
        by_asin[item["asin"]] = item
    return list(by_asin.values())


def save(sales: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "sales": sales,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sales)

    print(f"Wrote {len(sales)} items ({sum(1 for s in sales if s['type']=='2for1')} 2for1, "
          f"{sum(1 for s in sales if s['type']=='monthly')} monthly)")


# ---------------------------------------------------------------------------
# Git push
# ---------------------------------------------------------------------------

def git_push() -> None:
    repo = str(ROOT)
    def run(*args):
        subprocess.run(list(args), cwd=repo, check=True)
    run("git", "add", "data/sales.json", "data/sales.csv")
    run("git", "commit", "-m",
        f"chore: update sales data {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    run("git", "push")
    print("Pushed to GitHub.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Monthly deals ===")
    monthly = scrape_monthly()
    print(f"Monthly total: {len(monthly)}")

    print("\n=== 2-for-1 promo ===")
    two_for_one = scrape_2for1()
    print(f"2-for-1 total: {len(two_for_one)}")

    fresh = monthly + two_for_one
    if not fresh:
        print("Nothing scraped.")
        return

    existing = load_existing()
    merged   = merge(existing["sales"], monthly)
    merged   = merge(merged, two_for_one)   # 2for1 overwrites monthly if same ASIN

    print("\n=== Enriching tags ===")
    merged = enrich_tags(merged)
    save(merged)
    git_push()


if __name__ == "__main__":
    main()
