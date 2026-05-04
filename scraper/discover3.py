"""
Try price-based filtering to find actual sale/deal items.
"""
import json
import pathlib
import audible
import os, sys

# Fix Windows terminal encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

GROUPS = "product_desc,contributors,price,media,rating,product_attrs,product_plan_details"

def show(label, resp):
    products = resp.get("products", [])
    total = resp.get("total_results", "?")
    print(f"\n{'='*60}")
    print(f"{label}: {len(products)} returned, {total} total")
    for p in products[:5]:
        price = p.get("price", {})
        lp = price.get("lowest_price", {}).get("base")
        list_p = price.get("list_price", {}).get("base")
        plans = p.get("plans")
        print(f"  {p.get('asin')} | {str(p.get('title','?'))[:45]:<45} | cash=${lp} list=${list_p} | plans={plans}")

with audible.Client(auth=auth) as client:

    # Try various approaches to find actual sale items
    queries = [
        ("price_max=5",         dict(price_max=5, sort_by="Price", num_results=10)),
        ("price_max=3",         dict(price_max=3, sort_by="Price", num_results=10)),
        ("price_max=2",         dict(price_max=2, sort_by="Price", num_results=10)),
        ("sort_by=Price asc",   dict(sort_by="Price", num_results=10)),
        ("browse_type=deal + price_max=5", dict(browse_type="deal", price_max=5, num_results=10)),
        ("browse_type=top_sellers", dict(browse_type="top_sellers", num_results=5)),
        ("browse_type=whats_hot",   dict(browse_type="whats_hot", num_results=5)),
    ]

    for label, params in queries:
        try:
            r = client.get("1.0/catalog/products", response_groups=GROUPS, **params)
            show(label, r)
        except Exception as e:
            print(f"\n{label}: ERROR {e}")
