"""
Check if a known sale item (from the 2for1 promo page) has any
distinguishing fields vs a regular item in the catalog API.
"""
import json, pathlib, sys
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

SALE_ASIN    = "B0CDXWSS5D"   # known sale item from 2for1 page
REGULAR_ASIN = "B0GZ9BG929"   # regular featured item from earlier

GROUPS = (
    "product_desc,contributors,price,media,rating,product_attrs,"
    "product_plan_details,sku,relationships,series,periodicals"
)

with audible.Client(auth=auth) as client:
    for label, asin in [("SALE ITEM", SALE_ASIN), ("REGULAR ITEM", REGULAR_ASIN)]:
        resp = client.get(f"1.0/catalog/products/{asin}", response_groups=GROUPS)
        product = resp.get("product", resp)
        print(f"\n{'='*60}")
        print(f"{label}: {asin}")
        print(json.dumps(product, indent=2))
