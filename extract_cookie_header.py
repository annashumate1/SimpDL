"""Save a browser Cookie request header for use by SimpDL."""

from getpass import getpass
from pathlib import Path

from config_utils import write_json
from site_utils import parse_cookies


def extract_cookie_header():
    print("Save browser cookies for SimpDL")
    print("\n1. Sign in at https://simpcity.cr.")
    print("2. Open Developer Tools, select Network, and reload a thread.")
    print("3. Select the thread request and copy its Cookie request header.")
    print("\nThe pasted header is hidden and saved locally in config/manual_cookies.json.")
    header = getpass("Cookie header: ").strip()
    if header.lower().startswith("cookie:"):
        header = header[7:].strip()
    cookies = parse_cookies({"cookie_header": header})
    if not cookies:
        raise ValueError("No valid name=value cookies found. Nothing was saved.")
    user_agent = input("Matching User-Agent (optional): ").strip()
    destination = Path(__file__).resolve().parent / "config" / "manual_cookies.json"
    write_json(destination, {"cookie_header": header, "parsed_cookies": cookies, "user_agent": user_agent})
    print("\nCookies saved. Run python main.py and choose Saved cookies.")


if __name__ == "__main__":
    try:
        extract_cookie_header()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
    except (ValueError, OSError) as error:
        print(f"Could not save cookies: {error}")
