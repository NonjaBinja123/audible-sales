"""
Check if 2for1 is active by using the authenticated audible API client
to look for promo-specific catalog items and endpoints.
"""
import json, pathlib, sys
import audible

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

GROUPS = "product_desc,contributors,price,media,rating,product_plan_details"

with audible.Client(auth=auth) as client:

    # Try endpoints we haven't hit yet
    for ep in [
        "1.0/offers",
        "1.0/promotions/current",
        "1.0/catalog/promotions",
        "1.0/membership/promotions",
        "1.0/credit/offers",
    ]:
        try:
            r = client.get(ep)
            print(f"\n{ep}: OK")
            print(json.dumps(r, indent=2)[:500])
        except Exception as e:
            print(f"{ep}: {e}")

    # Try browse_type values specific to 2for1 / credit promos
    print("\n--- browse_type attempts ---")
    for bt in ["2for1", "credit_2for1", "2_for_1", "promo", "promotion",
               "credit_sale", "credit_promo", "limited_time", "special"]:
        try:
            r = client.get("1.0/catalog/products",
                           browse_type=bt, num_results=3,
                           response_groups=GROUPS)
            products = r.get("products", [])
            print(f"browse_type={bt!r}: {len(products)} results, total={r.get('total_results')}")
            for p in products[:2]:
                price = p.get("price", {})
                print(f"  {p.get('asin')} | credit_price={price.get('credit_price')} | plans={p.get('plans')}")
        except Exception as e:
            print(f"browse_type={bt!r}: {e}")
