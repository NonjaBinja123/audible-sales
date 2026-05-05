"""
Re-enrich genre + categories for all items using category_ladders response group.
Only calls the API for items missing categories (subsequent runs are fast).
"""
import csv, json, pathlib, sys, time
import audible

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from scraper import SCRAPER_DIR, DATA_FILE, CSV_FILE, CSV_FIELDS, _extract_tags, git_push

data  = json.loads(DATA_FILE.read_text(encoding="utf-8"))
sales = data["sales"]

needs = [s for s in sales if s.get("categories") is None]
print(f"{len(needs)} items need category enrichment out of {len(sales)} total")

if not needs:
    print("All items already have categories.")
    sys.exit(0)

auth    = audible.Authenticator.from_file(SCRAPER_DIR / "auth.json")
by_asin = {s["asin"]: s for s in sales}
fixed   = 0
done    = 0

with audible.Client(auth=auth) as client:
    for sale in needs:
        asin = sale["asin"]
        try:
            resp    = client.get(
                f"1.0/catalog/products/{asin}",
                response_groups="product_attrs,product_desc,category_ladders",
            )
            product = resp.get("product", resp)
            tags, genre, categories = _extract_tags(product)
            by_asin[asin]["tags"]       = tags
            by_asin[asin]["genre"]      = genre
            by_asin[asin]["categories"] = categories
            if categories:
                fixed += 1
        except Exception as e:
            by_asin[asin]["categories"] = []
            print(f"  Warning {asin}: {e}", file=sys.stderr)
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{len(needs)} processed, {fixed} with categories...")
        time.sleep(0.15)

print(f"\nCategories populated for {fixed}/{len(needs)} items.")

data["sales"] = list(by_asin.values())
DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for s in data["sales"]:
        row = dict(s)
        if isinstance(row.get("categories"), list):
            seen, flat = set(), []
            for path in row["categories"]:
                for node in path:
                    if node not in seen:
                        seen.add(node); flat.append(node)
            row["categories"] = "; ".join(flat)
        writer.writerow(row)

git_push()
print("Done and pushed.")
