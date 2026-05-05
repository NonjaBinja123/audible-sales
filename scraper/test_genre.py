"""
Investigate category_ladders — the source of proper genre data.
Tests multiple known books and response group combinations.
"""
import json, pathlib, sys
import audible

AUTH_FILE = pathlib.Path(__file__).parent / "auth.json"
auth = audible.Authenticator.from_file(AUTH_FILE)

# Mix of books from different genres
TEST_ASINS = [
    "B07KKPGDZF",  # Can't Hurt Me — Biography
    "B0868ZFF7X",  # Breaking the Habit of Being Yourself — Self Help
    "B00JFF4WMS",  # The Girl With All the Gifts — SciFi/Horror
    "B0CDXWSS5D",  # Eye of the Bedlam Bride — Fantasy
    "B0C6FPMDGV",  # Starter Villain — SciFi
]

with audible.Client(auth=auth) as client:
    for asin in TEST_ASINS:
        resp = client.get(
            f"1.0/catalog/products/{asin}",
            response_groups="product_attrs,product_desc,category_ladders",
        )
        p = resp.get("product", resp)
        ladders  = p.get("category_ladders") or []
        keywords = p.get("thesaurus_subject_keywords") or []
        title    = p.get("title", "?")[:40]

        print(f"\n{asin} | {title}")
        print(f"  category_ladders: {json.dumps(ladders)[:200]}")
        print(f"  thesaurus_keywords: {keywords}")
