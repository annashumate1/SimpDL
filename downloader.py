import os
import time
import json
import requests
import tkinter as tk
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from bs4 import BeautifulSoup

from image_utils import is_valid_image

def build_download_frame(parent, config_path, urls_file):
    """
    Returns a Frame that downloads images using pure requests (no browser).
    Requires manual cookie extraction from your browser.
    """
    frame = tb.Frame(parent, bootstyle="dark")

    title = tb.Label(frame, text="Download Images (Requests-Only Mode)", font=("Helvetica", 18, "bold"))
    title.pack(pady=10)

    # Instructions
    instructions = tb.Label(
        frame, 
        text="⚠️ First time? Click 'Setup Cookies' to extract your login cookies",
        font=("Helvetica", 10),
        bootstyle="warning"
    )
    instructions.pack(pady=5)

    progress_label = tb.Label(frame, text="Progress: Not started", font=("Helvetica", 12))
    progress_label.pack(pady=5)

    progress_bar = tb.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
    progress_bar.pack(pady=5)

    log_text = tk.Text(frame, height=15, width=60, bg="#282828", fg="#1DB954", wrap="word")
    log_text.pack(pady=10, fill="both", expand=True)

    download_in_progress = [False]

    def log_message(msg):
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)

    def show_cookie_instructions():
        """Show instructions for extracting cookies"""
        instructions_text = """
========================================
HOW TO EXTRACT COOKIES FROM YOUR BROWSER
========================================

1. Open Chrome/Firefox and log into simpcity.su
2. Press F12 to open Developer Tools
3. Go to "Application" tab (Chrome) or "Storage" tab (Firefox)
4. Click "Cookies" → "https://simpcity.su"
5. Find these cookies and copy their values:
   - xf_user
   - xf_session  
   - cf_clearance (if present)
   
6. Create a file: config/manual_cookies.json
7. Paste this template and fill in YOUR values:

{
    "xf_user": "PASTE_YOUR_VALUE_HERE",
    "xf_session": "PASTE_YOUR_VALUE_HERE",
    "cf_clearance": "PASTE_YOUR_VALUE_HERE"
}

8. Save the file and click "Start Download"

NOTE: Cookies expire! If download fails, extract fresh cookies.
========================================
        """
        log_message(instructions_text)

    def start_download():
        """Triggered by the button. Spawns a background thread for the main download."""
        if download_in_progress[0]:
            return  

        download_in_progress[0] = True
        start_button.config(state="disabled")
        log_message("Starting download with requests-only mode...")

        threading.Thread(target=run_download, daemon=True).start()

    def run_download():
        """
        Download using pure requests - no browser automation.
        """
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            output_directory = config.get("output_directory", "")

            with open(urls_file, "r") as file:
                urls = [line.strip() for line in file if line.strip()]

            if not urls:
                log_message("No URLs found. Please add URLs first.")
                return

            # Check for manual cookies
            script_dir = os.path.dirname(os.path.realpath(__file__))
            cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")
            
            if not os.path.exists(cookie_file):
                log_message("ERROR: manual_cookies.json not found!")
                log_message("Click 'Setup Cookies' button for instructions.")
                return
            
            with open(cookie_file, "r") as f:
                cookie_data = json.load(f)
            
            # Check if using new cookie_header format or old individual cookies
            if "cookie_header" in cookie_data:
                log_message("Using cookie header format (more reliable)")
                cookies = cookie_data.get("parsed_cookies", {})
                cookie_header = cookie_data.get("cookie_header", "")
            else:
                log_message("Using individual cookies format")
                cookies = cookie_data
                cookie_header = None
            
            log_message(f"Loaded cookies: {', '.join(cookies.keys())}")

            folder_name = get_folder_name(urls[0])
            combined_output_dir = os.path.join(output_directory, folder_name)
            if not os.path.exists(combined_output_dir):
                os.makedirs(combined_output_dir)

            # Setup requests session with cookies and headers
            session = requests.Session()
            
            # Comprehensive headers to mimic real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Referer': 'https://simpcity.cr/'
            }
            
            # If we have a cookie header, use ONLY that (most reliable)
            if cookie_header:
                log_message("Using raw cookie header method (most reliable)...")
                headers['Cookie'] = cookie_header
                log_message(f"  ✓ Cookie header set ({len(cookie_header)} chars)")
            else:
                # Only set individual cookies if no header exists
                log_message("Using individual cookie method...")
                from http.cookiejar import Cookie
                
                for cookie_name, cookie_value in cookies.items():
                    cookie_obj = Cookie(
                        version=0,
                        name=cookie_name,
                        value=cookie_value,
                        port=None,
                        port_specified=False,
                        domain='simpcity.cr',
                        domain_specified=True,
                        domain_initial_dot=False,
                        path='/',
                        path_specified=True,
                        secure=True,
                        expires=None,
                        discard=True,
                        comment=None,
                        comment_url=None,
                        rest={'HttpOnly': None},
                        rfc2109=False
                    )
                    session.cookies.set_cookie(cookie_obj)
                    log_message(f"  ✓ {cookie_name}")
            
            session.headers.update(headers)

            # Warm-up: Visit homepage first to establish session properly
            log_message("Warming up session by visiting homepage...")
            try:
                warmup = session.get('https://simpcity.cr/', timeout=15)
                log_message(f"Homepage status: {warmup.status_code}")
                time.sleep(2)
            except Exception as e:
                log_message(f"Warmup failed (continuing anyway): {e}")

            total_pages = len(urls)
            total_downloaded = 0

            for current_page, url in enumerate(urls, 1):
                # Workaround: If URL doesn't have /page-X, add /page-1 to avoid extra protection
                if '/page-' not in url:
                    url = url.rstrip('/') + '/page-1'
                    log_message(f"\n[Page {current_page}/{total_pages}] Fetching: {url} (normalized)")
                else:
                    log_message(f"\n[Page {current_page}/{total_pages}] Fetching: {url}")
                
                # Add small delay before first request and between pages
                if current_page == 1:
                    log_message("Adding initial delay to avoid rate limiting...")
                    time.sleep(3)
                elif current_page > 1:
                    time.sleep(2)
                
                try:
                    # Add referer header for this specific request
                    request_headers = session.headers.copy()
                    if current_page > 1:
                        request_headers['Referer'] = urls[current_page - 2]
                    else:
                        request_headers['Referer'] = 'https://simpcity.cr/'
                    
                    response = session.get(url, timeout=30, headers=request_headers, allow_redirects=True)
                    
                    log_message(f"Response status: {response.status_code}")
                    
                    if response.status_code == 403:
                        log_message("⚠️ ERROR 403: Access Forbidden")
                        log_message("Waiting 5 seconds and retrying...")
                        time.sleep(5)
                        
                        # Retry once
                        response = session.get(url, timeout=30, headers=request_headers, allow_redirects=True)
                        log_message(f"Retry status: {response.status_code}")
                        
                        if response.status_code == 403:
                            log_message("Still blocked. Skipping this page.")
                            log_message("Tip: If this persists, extract fresh cookies")
                            continue
                    
                    if response.status_code != 200:
                        log_message(f"ERROR: HTTP {response.status_code}")
                        log_message("Skipping this page...")
                        continue
                    
                    # Check for Cloudflare challenge
                    if 'challenge' in response.text.lower() or ('cloudflare' in response.text.lower() and 'ray id' in response.text.lower()):
                        log_message("⚠️ WARNING: Cloudflare challenge detected!")
                        log_message("Your cookies may be expired. Please extract fresh cookies.")
                        continue
                    
                    # Check if we're actually logged in
                    if 'login' in response.url or 'register' in response.url:
                        log_message("⚠️ WARNING: Not logged in! Cookies may be invalid.")
                        log_message("Please extract fresh cookies from your browser.")
                        continue
                    
                    # Parse HTML
                    soup = BeautifulSoup(response.content, 'html.parser')
                    images = soup.find_all('img')
                    
                    log_message(f"Found {len(images)} image tags. Filtering valid images...")
                    
                    valid_images = []
                    for img in images:
                        img_url = img.get('src') or img.get('data-src')
                        if img_url:
                            # Convert relative URLs to absolute
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = 'https://simpcity.cr' + img_url
                            valid_images.append(img_url)
                    
                    log_message(f"Processing {len(valid_images)} image URLs...")
                    
                    page_downloaded = 0
                    for idx, img_url in enumerate(valid_images):
                        try:
                            if is_valid_image(img_url):
                                # Download with proper headers
                                img_headers = session.headers.copy()
                                img_headers['Referer'] = url
                                img_headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                                
                                img_response = session.get(img_url, timeout=15, headers=img_headers)
                                
                                if img_response.status_code == 200:
                                    filename = f"image_{len(os.listdir(combined_output_dir)) + 1}.jpg"
                                    filepath = os.path.join(combined_output_dir, filename)
                                    
                                    with open(filepath, 'wb') as f:
                                        f.write(img_response.content)
                                    
                                    page_downloaded += 1
                                    total_downloaded += 1
                                    log_message(f"  ✓ Downloaded: {filename} ({page_downloaded} on this page)")
                                    
                                else:
                                    log_message(f"  ✗ Failed: HTTP {img_response.status_code}")
                        except Exception as e:
                            log_message(f"  ✗ Error downloading: {str(e)[:50]}")
                        
                        # Update progress
                        progress = ((idx + 1) / len(valid_images)) * 100
                        frame.after(0, lambda val=progress: progress_bar.configure(value=val))
                        status_text = page_status(idx + 1, len(valid_images), current_page, total_pages)
                        frame.after(0, lambda st=status_text: progress_label.config(text=st))
                        
                        # Small delay between images
                        time.sleep(0.2)
                    
                    log_message(f"Page complete: {page_downloaded} images downloaded")
                    
                    # Delay between pages
                    if current_page < total_pages:
                        log_message("Waiting 2 seconds before next page...")
                        time.sleep(2)
                
                except Exception as e:
                    log_message(f"ERROR on page {current_page}: {str(e)}")

            log_message(f"\n{'='*50}")
            log_message(f"DOWNLOAD COMPLETE!")
            log_message(f"Total images downloaded: {total_downloaded}")
            log_message(f"Saved to: {combined_output_dir}")
            log_message(f"{'='*50}")

        except FileNotFoundError as e:
            log_message(f"ERROR: File not found - {str(e)}")
        except json.JSONDecodeError:
            log_message("ERROR: Invalid JSON in manual_cookies.json")
            log_message("Please check the file format.")
        except Exception as e:
            log_message(f"ERROR: {str(e)}")
            import traceback
            log_message(traceback.format_exc())

        finally:
            download_in_progress[0] = False
            frame.after(0, lambda: start_button.config(state="normal"))

    def page_status(current_img, total_img, current_page, total_pages):
        return f"Page {current_page}/{total_pages}: {current_img}/{total_img} images"

    def get_folder_name(url):
        """
        Extract the portion after 'threads/' from the URL.
        """
        url = url.rstrip('/')
        parts = url.split('/')
        if 'threads' in parts:
            idx = parts.index('threads')
            if idx + 1 < len(parts):
                # Remove page-X suffix if present
                folder = parts[idx + 1]
                if folder.startswith('page-'):
                    if idx + 2 < len(parts):
                        folder = parts[idx + 2]
                return folder.split('?')[0]  # Remove query params
        return "default_folder"

    # Buttons
    button_frame = tb.Frame(frame, bootstyle="dark")
    button_frame.pack(pady=10)

    setup_button = tb.Button(
        button_frame, 
        text="Setup Cookies", 
        bootstyle="info outline", 
        command=show_cookie_instructions
    )
    setup_button.pack(side="left", padx=5)

    start_button = tb.Button(
        button_frame, 
        text="Start Download", 
        bootstyle="success outline", 
        command=start_download
    )
    start_button.pack(side="left", padx=5)

    return frame