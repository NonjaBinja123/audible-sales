"""
One-time auth setup using direct login (no browser).
Run this whenever you need to refresh credentials.
Saves auth.json with both API tokens and website cookies.
"""
import pathlib, os
from dotenv import load_dotenv
import audible

load_dotenv()

LOCALE    = os.environ.get("AUDIBLE_LOCALE", "us")
AUTH_FILES = {"us": "auth.json", "ca": "auth_ca.json", "uk": "auth_uk.json"}
AUTH_FILE  = pathlib.Path(__file__).parent / AUTH_FILES.get(LOCALE, f"auth_{LOCALE}.json")
EMAIL     = os.environ["AUDIBLE_EMAIL"]
PASSWORD  = os.environ["AUDIBLE_PASSWORD"]


def captcha_callback(captcha_url: str) -> str:
    print(f"\nCAPTCHA required. Open this URL and solve it:\n{captcha_url}")
    return input("Enter CAPTCHA answer: ").strip()


def otp_callback() -> str:
    return input("Enter your 2FA code from your authenticator app: ").strip()


def cvf_callback() -> str:
    print("Amazon sent a verification code to your email or phone.")
    return input("Enter the CVF code: ").strip()


print(f"Logging in to Audible ({LOCALE}) as {EMAIL}...")
auth = audible.Authenticator.from_login(
    username=EMAIL,
    password=PASSWORD,
    locale=LOCALE,
    captcha_callback=captcha_callback,
    otp_callback=otp_callback,
    cvf_callback=cvf_callback,
    with_username=False,
)

auth.to_file(AUTH_FILE)
print(f"\nSuccess! Saved to {AUTH_FILE}")
print(f"website_cookies present: {bool(auth.website_cookies)}")
print(f"customer: {auth.customer_info.get('given_name')} ({auth.customer_info.get('user_id')})")
