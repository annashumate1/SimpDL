"""
Alternative Cookie Extraction - Copy Entire Cookie Header
This method is MORE RELIABLE than copying individual cookies.

Run this script to extract your authentication cookies from your browser.
"""

import os
import json

def generate_links(base_link, num_pages):
    """
    Generate links starting from page 2 (page 1 often blocked).
    """
    links = []
    for page_num in range(2, num_pages + 1):
        new_link = f"{base_link.rstrip('/')}/page-{page_num}"
        links.append(new_link)
    return links

def extract_cookie_header():
    """
    Guide user to copy the entire Cookie header from browser DevTools.
    This is more reliable than individual cookies.
    """
    print("="*70)
    print("COOKIE HEADER EXTRACTION (RECOMMENDED METHOD)")
    print("="*70)
    print("""
This method is MORE RELIABLE than copying individual cookies.
Instead of copying cookies one-by-one, we'll copy the entire
Cookie header that your browser sends.

📋 STEP-BY-STEP INSTRUCTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Open Chrome or Firefox
2. Go to https://simpcity.cr (NOT .su - use .cr!)
3. Make sure you're logged in
4. Press F12 to open Developer Tools
5. Go to the "Network" tab
6. Refresh the page (Ctrl+R or Cmd+R)
7. Click on the FIRST request (usually just "simpcity.cr")
8. Look for "Request Headers" section on the right
9. Find the line that starts with "cookie:" or "Cookie:"
10. Right-click that line → Copy value (or Copy as cURL and extract)

The cookie line looks like this:
cookie: ogaddgmetaprof_user=12345%2Cabcd...; ogaddgmetaprof_session=xyz...

COPY THE ENTIRE LINE (everything after "cookie: ")

IMPORTANT: Make sure the URL in your browser is simpcity.cr (NOT .su)!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    print("\nReady? Press ENTER when you have the cookie header copied...")
    input()
    
    print("\nPaste your Cookie header here:")
    print("(Paste everything AFTER 'cookie:' or 'Cookie:')")
    cookie_header = input("→ ").strip()
    
    if not cookie_header:
        print("\n❌ No cookie header provided!")
        return
    
    # Clean up common issues
    if cookie_header.lower().startswith('cookie:'):
        cookie_header = cookie_header[7:].strip()
    
    # Save as cookie header format
    script_dir = os.path.dirname(os.path.realpath(__file__))
    cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")
    os.makedirs(os.path.join(script_dir, "config"), exist_ok=True)
    
    # Parse cookie string into dictionary for readability
    cookie_dict = {}
    for part in cookie_header.split(';'):
        part = part.strip()
        if '=' in part:
            key, value = part.split('=', 1)
            cookie_dict[key.strip()] = value.strip()
    
    # Save both formats
    data = {
        "cookie_header": cookie_header,
        "parsed_cookies": cookie_dict
    }
    
    with open(cookie_file, "w") as f:
        json.dump(data, f, indent=4)
    
    print("\n" + "="*70)
    print("✅ SUCCESS! Cookie header saved!")
    print("="*70)
    print(f"\nSaved to: {cookie_file}")
    print(f"\nFound {len(cookie_dict)} cookies:")
    for name in cookie_dict.keys():
        print(f"  • {name}")
    
    print("\n🚀 Now run: python test_cookies.py")
    print("   Or go straight to your main app!\n")

if __name__ == "__main__":
    try:
        extract_cookie_header()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")