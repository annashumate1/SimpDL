import os
import time
import json
import requests
import argparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from image_utils import is_valid_image
from utils import (
    _sanitize_output_dir, 
    _default_output_dir, 
    _has_auth_cookies, 
    get_folder_name,
    verify_full_quality,
    resolve_source_image_headless
)

def log_message(msg):
    print(msg)

def run_cli_download(low_res=False):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(script_dir, "config", "config.json")
    urls_file = os.path.join(script_dir, "config", "urls.txt")
    cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f) or {}

        output_directory = _sanitize_output_dir(config.get("output_directory", ""))
        os.makedirs(output_directory, exist_ok=True)

        with open(urls_file, "r", encoding="utf-8") as file:
            urls = [line.strip() for line in file if line.strip()]

        if not urls:
            log_message("No URLs found in urls.txt")
            return

        if not os.path.exists(cookie_file):
            log_message("ERROR: manual_cookies.json not found.")
            return

        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_data = json.load(f) or {}

        if not _has_auth_cookies(cookie_data):
            log_message("ERROR: Cookies not configured correctly.")
            return

        # Setup output directory
        folder_name = get_folder_name(urls[0])
        suffix = "_lowres" if low_res else ""
        combined_output_dir = os.path.join(output_directory, folder_name + suffix)
        os.makedirs(combined_output_dir, exist_ok=True)

        # Setup requests session
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://simpcity.cr/'
        }
        if "cookie_header" in cookie_data:
            headers['Cookie'] = cookie_data["cookie_header"]
        session.headers.update(headers)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            if "parsed_cookies" in cookie_data:
                cookies_to_set = []
                for name, value in cookie_data["parsed_cookies"].items():
                    cookies_to_set.append({
                        'name': name, 'value': value, 'domain': '.simpcity.cr', 'path': '/'
                    })
                context.add_cookies(cookies_to_set)

            total_pages = len(urls)
            total_downloaded = 0

            for current_page_idx, url in enumerate(urls, 1):
                log_message(f"\n[Page {current_page_idx}/{total_pages}] Processing: {url}")
                
                page = context.new_page()
                page.goto(url, wait_until='networkidle', timeout=60000)
                time.sleep(2)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                html = page.content()
                page.close()
                
                soup = BeautifulSoup(html, 'html.parser')
                images = soup.select('div.bbWrapper img')
                log_message(f"Found {len(images)} potential images. Processing...")

                for idx, img in enumerate(images):
                    try:
                        source_url = None
                        
                        if not low_res:
                            # Speculative Path: Try suffix stripping the thumbnail URL first
                            # This is often hidden in data-original or just the src with .md. prefix
                            thumb_src = img.get('data-url') or img.get('data-src') or img.get('src')
                            if thumb_src:
                                if thumb_src.startswith('//'): thumb_src = 'https:' + thumb_src
                                elif thumb_src.startswith('/'): thumb_src = 'https://simpcity.cr' + thumb_src
                                
                                # If it's already a direct image host (not a proxy), try stripping suffixes
                                if any(host in thumb_src for host in ['selti-delivery.ru', 'imgbox.com', 'pixl.is']):
                                    speculative_source = verify_full_quality(thumb_src, session)
                                    if speculative_source != thumb_src:
                                        source_url = speculative_source
                                        # log_message(f"    (Speculative hit: {os.path.basename(source_url)})")

                            # Traditional Path: Resolve parent link if speculative failed
                            if not source_url:
                                parent_a = img.find_parent('a')
                                if parent_a:
                                    href = parent_a.get('href')
                                    if href:
                                        log_message(f"  [{idx+1}/{len(images)}] Resolving: {href[:60]}...")
                                        source_url = resolve_source_image_headless(href, context, session)
                        
                        # Low-Res Path or Fallback
                        if not source_url:
                            source_url = img.get('data-url') or img.get('data-src') or img.get('src')
                        
                        if source_url:
                            if source_url.startswith('//'): source_url = 'https:' + source_url
                            elif source_url.startswith('/'): source_url = 'https://simpcity.cr' + source_url
                            
                            if any(x in source_url for x in ['/styles/', '/data/avatars/', 'favicon', 'logo']):
                                continue
                                
                            if is_valid_image(source_url):
                                img_headers = session.headers.copy()
                                img_headers['Referer'] = url
                                img_response = session.get(source_url, timeout=20, headers=img_headers)
                                
                                if img_response.status_code == 200:
                                    current_count = len([f for f in os.listdir(combined_output_dir) if f.endswith('.jpg')])
                                    filename = f"image_{current_count + 1}.jpg"
                                    filepath = os.path.join(combined_output_dir, filename)
                                    with open(filepath, 'wb') as f:
                                        f.write(img_response.content)
                                    
                                    total_downloaded += 1
                                    log_message(f"    ✓ Downloaded: {filename} ({len(img_response.content)//1024} KB)")

                    except Exception as e:
                        log_message(f"    ✗ Error: {e}")
                    
                    time.sleep(0.1)

            browser.close()

        log_message(f"\n{'='*70}")
        log_message(f"✅ DOWNLOAD COMPLETE!")
        log_message(f"📊 Total downloaded: {total_downloaded}")
        log_message(f"📁 Saved to: {combined_output_dir}")
        log_message(f"{'='*70}")

    except Exception as e:
        log_message(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SimpDL CLI Downloader")
    parser.add_argument("--lowres", action="store_true", help="Download low-resolution previews (faster)")
    args = parser.parse_args()
    
    run_cli_download(low_res=args.lowres)
