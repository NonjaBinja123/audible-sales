"""
Dump the full API response for the current deals to find all available fields.
"""
import json
import pathlib
import audible

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

ALL_GROUPS = (
    "product_desc,contributors,price,media,rating,product_attrs,"
    "product_plan_details,sku,relationships,series"
)

with audible.Client(auth=auth) as client:
    resp = client.get(
        "1.0/catalog/products",
        browse_type="deal",
        num_results=50,
        response_groups=ALL_GROUPS,
    )

products = resp.get("products", [])
print(f"Total items: {len(products)}\n")

# Dump first product in full so we can see every available field
if products:
    print("=== FULL FIRST PRODUCT ===")
    print(json.dumps(products[0], indent=2))

    print("\n=== PRICE FIELDS FOR ALL PRODUCTS ===")
    for p in products:
        print(f"\n{p.get('asin')} | {p.get('title','?')[:50]}")
        print(f"  price: {json.dumps(p.get('price'), indent=4)}")
        print(f"  plans: {json.dumps(p.get('plans'), indent=4)}")
        print(f"  merchandising: {p.get('merchandising_summary')}")
        print(f"  badge_types: {p.get('badge_types')}")
        print(f"  sale_details: {p.get('sale_details')}")
