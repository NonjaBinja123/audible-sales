"""One-time: backfill genre from existing tags data and push."""
import json, pathlib, subprocess
from datetime import datetime, timezone
sys_path_fix = __import__('sys'); sys_path_fix.path.insert(0, str(pathlib.Path(__file__).parent))
from scraper import _genre_from_tags, DATA_FILE, CSV_FILE, CSV_FIELDS
import csv

data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
fixed = 0
for s in data["sales"]:
    if s.get("tags") and not s.get("genre"):
        s["genre"] = _genre_from_tags(s["tags"])
        if s["genre"]:
            fixed += 1

print(f"Backfilled genre for {fixed} items.")

DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data["sales"])

def run(*args):
    subprocess.run(list(args), cwd=str(DATA_FILE.parent.parent), check=True)

run("git", "add", "data/sales.json", "data/sales.csv")
run("git", "commit", "-m", f"chore: backfill genre from tags {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
run("git", "push")
print("Done and pushed.")
