import csv, json, os, pathlib, re, subprocess, sys
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from curl_cffi import requests as curl
from dotenv import load_dotenv
import audible

load_dotenv()

SCRAPER_DIR = pathlib.Path(__file__).parent
ROOT        = pathlib.Path(__file__).parent.parent

if (SCRAPER_DIR / "scraper.disabled").exists():
    print(f"Scraper disabled (scraper.disabled flag file present). Remove it to re-enable.")
    sys.exit(0)
DATA_FILE = ROOT / "data" / "sales.json"
CSV_FILE  = ROOT / "data" / "sales.csv"

CSV_FIELDS = [
    "region","type","asin","title","author","narrator","genre","categories","tags",
    "length_hours","rating","rating_count","price","regular_price",
    "cover_url","audible_url",
]

# Regions to scrape. Add/remove entries here to enable/disable regions.
# auth_file must exist (run auth_setup.py with AUDIBLE_LOCALE=<code> to create it).
REGION_CONFIGS = {
    "us": {
        "base":        "https://www.audible.com",
        "ovr":         "overrideBaseCountry=true&ipRedirectOverride=true",
        "auth_file":   SCRAPER_DIR / "auth.json",
        "deals_path":  "/ep/audiobook-deals",
    },
    "ca": {
        "base":        "https://www.audible.ca",
        "ovr":         "",
        "auth_file":   SCRAPER_DIR / "auth_ca.json",
        "deals_path":  "/ep/monthly-deals-all",
    },
}

ENABLED_REGIONS = [r.strip() for r in os.environ.get("AUDIBLE_REGIONS", "us").split(",") if r.strip()]


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def _make_session(cookies: dict | None = None) -> curl.Session:
    s = curl.Session(impersonate="edge101")
    if cookies:
        s.cookies.update(cookies)
    return s


def _auth_cookies(auth_file: pathlib.Path) -> dict:
    auth = audible.Authenticator.from_file(auth_file)
    return dict(auth.website_cookies or {})


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_card(card, sale_type: str, region: str = "us", base: str = "https://www.audible.com") -> dict | None:
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
        "region":        region,
        "type":          sale_type,
        "asin":          asin,
        "title":         title,
        "author":        author,
        "narrator":      narrator,
        "genre":         None,
        "categories":    None,
        "length_hours":  length_hours,
        "rating":        rating,
        "rating_count":  rating_count,
        "price":         price,
        "regular_price": regular_price,
        "cover_url":     cover_url,
        "audible_url":   f"{base}/pd/{asin}",
    }


def _scrape_listing(session: curl.Session, start_url: str, sale_type: str,
                    region: str = "us", base: str = "https://www.audible.com") -> list[dict]:
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
            item = _parse_card(card, sale_type, region, base)
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


def _fetch_daily_deal(asin: str, base: str = "https://www.audible.com", region: str = "us") -> dict | None:
    """Fetch daily deal item: price from product page, metadata from API."""
    session = _make_session()
    price = regular_price = None
    try:
        r    = session.get(f"{base}/pd/{asin}", timeout=20)
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
        auth = audible.Authenticator.from_file(SCRAPER_DIR / "auth.json")
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
            "region":        region,
            "type":          "daily",
            "asin":          asin,
            "title":         p.get("title"),
            "author":        ", ".join(c.get("name","") for c in authors if c.get("name")),
            "narrator":      ", ".join(n.get("name","") for n in narrs   if n.get("name")),
            "genre":         None,
            "categories":    None,
            "tags":          None,
            "length_hours":  round(runtime / 60, 1) if runtime else None,
            "rating":        float(overall.get("display_average_rating", 0) or 0) or None,
            "rating_count":  int(overall.get("num_ratings", 0) or 0) or None,
            "price":         price,
            "regular_price": regular_price,
            "cover_url":     (p.get("product_images") or {}).get("500"),
            "audible_url":   f"{base}/pd/{asin}",
        }
    except Exception as e:
        print(f"  Daily deal API error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Monthly deals (public — no auth needed)
# ---------------------------------------------------------------------------

def scrape_monthly(base: str, ovr: str, region: str, deals_path: str = "/ep/audiobook-deals") -> tuple[list[dict], list[dict]]:
    """Returns (monthly_items, daily_items) — daily kept separate so it can coexist with monthly."""
    session = _make_session()
    url = f"{base}{deals_path}?{ovr}" if ovr else f"{base}{deals_path}"
    print(f"  Starting at {url}")

    # Identify daily deal ASIN from page 0 before full scrape
    try:
        r0         = session.get(url, timeout=20)
        soup0      = BeautifulSoup(r0.text, "html.parser")
        daily_asin = _find_daily_deal_asin(soup0)
        if daily_asin:
            print(f"  Daily deal ASIN: {daily_asin}")
    except Exception:
        daily_asin = None

    items = _scrape_listing(session, url, "monthly", region, base)

    daily_items: list[dict] = []
    if daily_asin:
        print(f"  Fetching daily deal data...")
        daily_item = _fetch_daily_deal(daily_asin, base, region)
        if daily_item:
            daily_items.append(daily_item)
            print(f"  Daily deal: {daily_item.get('title', daily_asin)}")

    return items, daily_items


# ---------------------------------------------------------------------------
# Special promos — dynamic discovery (auth required)
# ---------------------------------------------------------------------------

def _slug_to_type(slug: str) -> str:
    """Derive a sale type string from a URL slug like '2for1' or 'cash-sale'."""
    slug = slug.lower()
    if any(x in slug for x in ('2for1', '2-for-1', 'bogo', 'buy2')):
        return '2for1'
    if any(x in slug for x in ('cash', 'price', 'dollar')):
        return 'cash'
    if any(x in slug for x in ('site-wide', 'sitewide', 'sale', 'savings')):
        return 'cash'  # site-wide promos are almost always cash-price discounts
    if 'daily' in slug:
        return 'daily'
    # Normalize slug: strip non-alphanumeric, truncate
    return re.sub(r'[^a-z0-9]', '', slug)[:20] or 'promo'


def _detect_type_from_content(html: str, slug_type: str) -> str:
    """Refine sale type from page content when the URL slug is ambiguous."""
    text = html.lower()
    credit_signals = (text.count('1 credit') + text.count('use 1 credit')
                      + len(re.findall(r'with\s+1\s+credit', text)))
    cash_signals   = len(re.findall(r'\$[\d]+\.[\d]{2}', html))
    if credit_signals > cash_signals * 2:
        return '2for1'
    if cash_signals > credit_signals * 2 and slug_type not in ('2for1',):
        return 'cash'
    return slug_type


def _discover_promo_paths(session: curl.Session, base: str, ovr: str) -> dict[str, str]:
    """
    Scrape Audible's hub pages to find active promotional sale URLs.
    Returns {promo_path: sale_type}.
    Looks for /special-promo/ links and refines type from page content.
    """
    found: dict[str, str] = {}
    def url(path): return f"{base}{path}?{ovr}" if ovr else f"{base}{path}"
    check = [url("/"), url("/ep/audiobook-deals"), url("/ep/deals-and-sales"), url("/ep/deals")]
    for hub_url in check:
        try:
            r = session.get(hub_url, timeout=20)
            paths = re.findall(r'href="(/special-promo/[^/"?]+)', r.text)
            for path in paths:
                if path not in found:
                    slug      = path.split('/')[-1]
                    slug_type = _slug_to_type(slug)
                    # Fetch the promo page itself to refine type from content
                    try:
                        promo_url = f"{base}{path}?{ovr}" if ovr else f"{base}{path}"
                        pr = session.get(promo_url, timeout=20)
                        if pr.status_code == 200:
                            slug_type = _detect_type_from_content(pr.text, slug_type)
                    except Exception:
                        pass
                    found[path] = slug_type
        except Exception as e:
            print(f"  Discovery error on {hub_url}: {e}", file=sys.stderr)
    return found


def _scrape_promo_path(session: curl.Session, path: str, sale_type: str,
                       base: str, ovr: str, region: str) -> list[dict]:
    """Scrape a single special promo, handling category-node pages if present."""
    promo_url = f"{base}{path}?{ovr}" if ovr else f"{base}{path}"
    r = session.get(promo_url, timeout=20)
    if r.status_code != 200:
        print(f"  {path} returned {r.status_code} — may require auth or be inactive",
              file=sys.stderr)
        return []

    # Look for category-node sub-pages (e.g. /special-promo/2for1/cat?node=...)
    node_pattern = re.escape(path) + r'/cat\?node=(\d+)'
    nodes = list(dict.fromkeys(re.findall(node_pattern, r.text)))

    items: list[dict] = []
    seen: set[str] = set()

    if nodes:
        for node in nodes:
            node_url = f"{base}{path}/cat?node={node}&{ovr}" if ovr else f"{base}{path}/cat?node={node}"
            print(f"    Node {node}:")
            for item in _scrape_listing(session, node_url, sale_type, region, base):
                if item["asin"] not in seen:
                    items.append(item)
                    seen.add(item["asin"])
    else:
        for item in _scrape_listing(session, promo_url, sale_type, region, base):
            if item["asin"] not in seen:
                items.append(item)
                seen.add(item["asin"])

    return items


def scrape_promos(base: str, ovr: str, auth_file: pathlib.Path, region: str) -> list[dict]:
    """Discover and scrape all currently active special promotional sales."""
    cookies = _auth_cookies(auth_file)
    session = _make_session(cookies)

    print("  Discovering active promotions...")
    promo_paths = _discover_promo_paths(session, base, ovr)

    if not promo_paths:
        print("  No special promotions found on hub pages.")
        return []

    all_items: list[dict] = []
    seen: set[str] = set()

    for path, sale_type in promo_paths.items():
        print(f"  Promo: {path}  ->  type={sale_type!r}")
        for item in _scrape_promo_path(session, path, sale_type, base, ovr, region):
            if item["asin"] not in seen:
                all_items.append(item)
                seen.add(item["asin"])
        print(f"    Subtotal: {len(all_items)}")

    return all_items


# ---------------------------------------------------------------------------
# Tag enrichment via Audible API
# ---------------------------------------------------------------------------

def _extract_categories(product: dict) -> list[list[str]]:
    """Extract full category hierarchy as array of paths (one per ladder)."""
    result = []
    for ladder in (product.get("category_ladders") or []):
        path = [
            rung.get("name", "").strip()
            for rung in (ladder.get("ladder") or [])
            if rung.get("name", "").strip()
        ]
        if path:
            result.append(path)
    return result


def _extract_tags(product: dict) -> tuple[str, str | None, list[list[str]]]:
    """Returns (thesaurus_tags_string, genre, categories_array)."""
    categories = _extract_categories(product)
    genre = categories[0][0] if categories else None

    tags = []
    for kw in (product.get("thesaurus_subject_keywords") or []):
        kw = kw.strip()
        if not kw:
            continue
        readable = _GENRE_MAP.get(kw.lower(), kw)
        if readable not in tags:
            tags.append(readable)

    if genre is None and tags:
        genre = tags[0]

    return "; ".join(tags), genre, categories


_GENRE_MAP = {
    'literature-and-fiction':      'Literature & Fiction',
    'mystery-thriller-suspense':   'Mystery, Thriller & Suspense',
    'science-fiction-fantasy':     'Science Fiction & Fantasy',
    'romance':                     'Romance',
    'biographies-memoirs':         'Biographies & Memoirs',
    'business-careers':            'Business & Careers',
    'self-development':            'Self Development',
    'history':                     'History',
    'health-wellness':             'Health & Wellness',
    'true-crime':                  'True Crime',
    'politics-social-sciences':    'Politics & Social Sciences',
    'religion-spirituality':       'Religion & Spirituality',
    'children':                    "Children's",
    'teen-young-adult':            'Teen & Young Adult',
    'science-technology':          'Science & Technology',
    'arts-entertainment':          'Arts & Entertainment',
    'comedy-humor':                'Comedy & Humor',
    'education-learning':          'Education & Learning',
    'money-finance':               'Money & Finance',
    'sports-outdoors':             'Sports & Outdoors',
    'travel-tourism':              'Travel & Tourism',
    'home-garden':                 'Home & Garden',
    'erotica':                     'Erotica',
    'lgbtq':                       'LGBTQ+',
}

def _slug_to_genre(slug: str) -> str:
    """Convert a slug like 'literature-and-fiction' to a readable genre."""
    return _GENRE_MAP.get(slug.lower()) or slug.replace('-', ' ').title()

def _genre_from_tags(tags_str: str) -> str | None:
    """Derive genre from existing tags string — picks first recognisable tag."""
    if not tags_str:
        return None
    for tag in tags_str.split(";"):
        tag = tag.strip()
        if not tag:
            continue
        if tag.lower() in _GENRE_MAP:
            return _GENRE_MAP[tag.lower()]
        if ' ' in tag or (tag and tag[0].isupper()):
            return tag
        if '-' in tag:
            return _slug_to_genre(tag)
    return None


def enrich_tags(sales: list[dict]) -> list[dict]:
    # Backfill genre for already-enriched items (no API calls needed)
    backfilled = 0
    for s in sales:
        if s.get("tags") is not None and not s.get("genre"):
            s["genre"] = _genre_from_tags(s["tags"])
            if s["genre"]:
                backfilled += 1
    if backfilled:
        print(f"  Backfilled genre for {backfilled} existing items from tags.")

    needs_asins = {s["asin"] for s in sales if s.get("tags") is None or s.get("categories") is None}
    if not needs_asins:
        print("  Tags already up to date.")
        return sales

    # One API call per unique ASIN — same book may appear under multiple types
    seen: set[str] = set()
    to_enrich = []
    for s in sales:
        if s["asin"] in needs_asins and s["asin"] not in seen:
            to_enrich.append(s)
            seen.add(s["asin"])

    print(f"  Enriching {len(to_enrich)} items with Audible category data...")
    print("  (First run may take several minutes — subsequent runs only process new items)")

    auth     = audible.Authenticator.from_file(SCRAPER_DIR / "auth.json")
    enriched: dict[str, dict] = {}
    done     = 0

    with audible.Client(auth=auth) as client:
        for sale in to_enrich:
            asin = sale["asin"]
            try:
                resp    = client.get(
                    f"1.0/catalog/products/{asin}",
                    response_groups="product_attrs,product_desc,category_ladders",
                )
                product = resp.get("product", resp)
                tags, genre, categories = _extract_tags(product)
                enriched[asin] = {"tags": tags, "genre": genre, "categories": categories}
            except Exception as e:
                enriched[asin] = {"tags": "", "genre": None, "categories": None}
                print(f"  Warning: could not enrich {asin}: {e}", file=sys.stderr)
            done += 1
            if done % 100 == 0:
                print(f"  Enriched {done}/{len(to_enrich)}...")
            import time; time.sleep(0.15)

    # Apply enrichment to ALL items with that ASIN (covers daily + monthly duplicates)
    for s in sales:
        if s["asin"] in enriched:
            s.update(enriched[s["asin"]])

    print(f"  Done enriching {len(to_enrich)} items.")
    return sales


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": None, "sales": []}


def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    # Key by (asin, region, type) so the same book can appear under multiple sale types
    def _key(s):
        return (s["asin"], s.get("region", "us"), s.get("type", ""))
    by_key = {_key(s): s for s in existing}
    for item in fresh:
        by_key[_key(item)] = item
    return list(by_key.values())


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
        for s in sales:
            # Flatten categories array → semicolon string for CSV
            row = dict(s)
            if isinstance(row.get("categories"), list):
                seen, flat = set(), []
                for path in row["categories"]:
                    for node in path:
                        if node not in seen:
                            seen.add(node); flat.append(node)
                row["categories"] = "; ".join(flat)
            writer.writerow(row)

    by_type = {}
    for s in sales:
        by_type[s['type']] = by_type.get(s['type'], 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items()))
    print(f"Wrote {len(sales)} items ({summary})")


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
    all_monthly: list[dict] = []
    all_daily:   list[dict] = []
    all_promos:  list[dict] = []

    for region_code in ENABLED_REGIONS:
        cfg = REGION_CONFIGS[region_code]
        base, ovr, auth_file = cfg["base"], cfg["ovr"], cfg["auth_file"]

        print(f"\n=== [{region_code.upper()}] Monthly deals ===")
        monthly, daily = scrape_monthly(base, ovr, region_code, cfg.get("deals_path", "/ep/audiobook-deals"))
        print(f"  Monthly: {len(monthly)}  Daily: {len(daily)}")
        all_monthly.extend(monthly)
        all_daily.extend(daily)

        print(f"\n=== [{region_code.upper()}] Special promotions ===")
        if auth_file.exists():
            promos = scrape_promos(base, ovr, auth_file, region_code)
            print(f"  Total: {len(promos)}")
            all_promos.extend(promos)
        else:
            print(f"  No auth file ({auth_file.name}) — skipping promos for {region_code}")

    if not any([all_monthly, all_daily, all_promos]):
        print("Nothing scraped.")
        return

    existing = load_existing()
    # Monthly items carry forward; promos and daily are replaced fresh each run
    _stable = {"monthly"}
    stable_existing = [s for s in existing["sales"] if s.get("type") in _stable]
    merged = merge(stable_existing, all_monthly)
    merged = merge(merged, all_promos)
    # Daily items use type-aware key so they coexist with monthly for the same ASIN
    merged = merge(merged, all_daily)

    print("\n=== Enriching tags ===")
    merged = enrich_tags(merged)
    save(merged)
    git_push()


if __name__ == "__main__":
    main()
