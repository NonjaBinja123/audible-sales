import json, pathlib, collections
d = json.loads((pathlib.Path(__file__).parent.parent / "data" / "sales.json").read_text(encoding="utf-8"))
sales = d["sales"]

no_tags  = [s for s in sales if s.get("tags") is None]
empty    = [s for s in sales if s.get("tags") == ""]
has_tags = [s for s in sales if s.get("tags")]
has_genre= [s for s in sales if s.get("genre")]

print(f"Total: {len(sales)}")
print(f"tags=None: {len(no_tags)}")
print(f"tags='': {len(empty)}")
print(f"tags has data: {len(has_tags)}")
print(f"genre set: {len(has_genre)}")
print()
print("Sample tags from items that have them:")
for s in has_tags[:5]:
    print(f"  {s.get('tags','')[:80]}")
print()
print("Sample tags from empty items:")
for s in empty[:3]:
    print(f"  asin={s['asin']} title={s.get('title','')[:40]}")
