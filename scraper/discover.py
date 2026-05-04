"""
Probe the Audible API to find sale browse parameters.
Run this, then share the output so we can identify the right params.
"""
import json
import pathlib
import audible

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

RESPONSE_GROUPS = "product_desc,contributors,price,media,rating,product_attrs"

def dump(label, resp):
    products = resp.get("products", [])
    print(f"\n{'='*60}")
    print(f"{label}: {len(products)} results")
    for p in products[:3]:
        print(f"  {p.get('asin')} | {p.get('title','?')[:50]} | price={p.get('price',{})}")

with audible.Client(auth=auth) as client:

    # 1. Browse categories — find any sale/deal categories
    print("Fetching categories...")
    cats = client.get("1.0/catalog/categories", image_dpi=500)
    for c in cats.get("categories", []):
        print(f"  {c.get('id')} | {c.get('name')}")
        for sub in c.get("subcategories") or []:
            print(f"    {sub.get('id')} | {sub.get('name')}")

    # 2. Try browse_type variations
    for bt in ["deal", "deals", "sale", "featured", "new_release"]:
        try:
            r = client.get("1.0/catalog/products", browse_type=bt,
                           num_results=5, response_groups=RESPONSE_GROUPS)
            dump(f"browse_type={bt}", r)
        except Exception as e:
            print(f"\nbrowse_type={bt}: ERROR {e}")

    # 3. Try the whispersync deals endpoint
    for ep in ["1.0/whispersync/deals", "1.0/catalog/deals", "1.0/promotions"]:
        try:
            r = client.get(ep, num_results=5)
            print(f"\n{ep}: {json.dumps(r, indent=2)[:500]}")
        except Exception as e:
            print(f"\n{ep}: ERROR {e}")
