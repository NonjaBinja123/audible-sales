import audible, pathlib
d = pathlib.Path(__file__).parent
for name, fname in [("US", "auth.json"), ("CA", "auth_ca.json")]:
    f = d / fname
    if not f.exists():
        print(f"{name}: no auth file ({fname})")
        continue
    auth = audible.Authenticator.from_file(f)
    print(f"{name}: OK — {auth.customer_info.get('given_name')}, website_cookies={bool(auth.website_cookies)}")
