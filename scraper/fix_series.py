"""
Enrich series name, sequence, and is_series_start for all sales items.
Skips items that already have series data. Safe to re-run.
Uses the 'series' response group from the Audible catalog API.
"""
import csv, json, pathlib, sys, time
import audible

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from scraper import SCRAPER_DIR, DATA_FILE, CSV_FILE, CSV_FIELDS, git_push

data  = json.loads(DATA_FILE.read_text(encoding="utf-8"))
sales = data["sales"]

needs = [s for s in sales if s.get("series_name") is None and s.get("series_sequence") is None]
print(f"{len(needs)} items need series enrichment out of {len(sales)} total")

if not needs:
    print("All items already have series data.")
    sys.exit(0)

auth    = audible.Authenticator.from_file(SCRAPER_DIR / "auth.json")
by_asin = {s["asin"]: s for s in sales}
done    = 0
found   = 0

with audible.Client(auth=auth) as client:
    for sale in needs:
        asin = sale["asin"]
        try:
            resp    = client.get(
                f"1.0/catalog/products/{asin}",
                response_groups="series",
            )
            product = resp.get("product", resp)
            series_list = product.get("series") or []
            if series_list:
                s0 = series_list[0]
                by_asin[asin]["series_name"]     = s0.get("title")
                by_asin[asin]["series_sequence"]  = s0.get("sequence")
                by_asin[asin]["is_series_start"]  = s0.get("sequence") == "1"
                found += 1
            else:
                by_asin[asin]["series_name"]     = ""
                by_asin[asin]["series_sequence"]  = ""
                by_asin[asin]["is_series_start"]  = False
        except Exception as e:
            by_asin[asin]["series_name"]    = ""
            by_asin[asin]["series_sequence"] = ""
            by_asin[asin]["is_series_start"] = False
            print(f"  Warning {asin}: {e}", file=sys.stderr)
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{len(needs)} processed, {found} in a series...")
        time.sleep(0.15)

print(f"\nSeries data populated for {found}/{len(needs)} items.")

data["sales"] = list(by_asin.values())
DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# Update CSV — add series fields if not already in CSV_FIELDS
fields = CSV_FIELDS if "series_name" in CSV_FIELDS else CSV_FIELDS + ["series_name", "series_sequence", "is_series_start"]
with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
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
