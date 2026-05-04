"""One-time helper: write sales.json as CSV next to this script."""
import csv, json, pathlib

DATA = pathlib.Path(__file__).parent.parent / "data" / "sales.json"
OUT  = pathlib.Path(__file__).parent / "sales_preview.csv"

data = json.loads(DATA.read_text(encoding="utf-8"))

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "type","asin","title","author","narrator","genre",
        "length_hours","rating","rating_count","price","regular_price",
        "cover_url","audible_url",
    ], extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data["sales"])

print(f"Wrote {len(data['sales'])} rows to {OUT}")
