import json, pathlib
d = json.loads((pathlib.Path(__file__).parent.parent / "data" / "sales.json").read_text(encoding="utf-8"))
ca = [s for s in d["sales"] if s.get("region") == "ca"]
us = [s for s in d["sales"] if s.get("region") == "us"]
no_region = [s for s in d["sales"] if not s.get("region")]
print(f"CA: {len(ca)}, US: {len(us)}, no region: {len(no_region)}")
for s in ca[:3]:
    print(f"  {s['asin']} | {s['audible_url']}")
for s in us[:2]:
    print(f"  {s['asin']} | {s['audible_url']}")
