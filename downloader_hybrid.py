import os
import time
import json
import requests
import tkinter as tk
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
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

def build_download_frame(parent, config_path, urls_file):
    """Premium download interface."""
    frame = tb.Frame(parent, bootstyle="secondary")

    # Main card
    card = tb.Frame(frame, bootstyle="dark")
    card.pack(fill="both", expand=True)

    content = tb.Frame(card, bootstyle="dark")
    content.pack(padx=40, pady=40, fill="both", expand=True)

    # Title
    title_label = tb.Label(
        content,
        text="Download Center",
        font=("Helvetica", 16, "bold"),
        foreground="#ffffff"
    )
    title_label.pack(anchor="w", pady=(0, 10))

    subtitle_label = tb.Label(
        content,
        text="Execute and monitor your download operations",
        font=("Helvetica", 10),
        foreground="#94a3b8"
    )
    subtitle_label.pack(anchor="w", pady=(0, 25))

    # Status panel
    status_panel = tb.Frame(content, bootstyle="secondary")
    status_panel.pack(fill="x", pady=(0, 20))

    status_content = tb.Frame(status_panel, bootstyle="secondary")
    status_content.pack(padx=25, pady=20)

    # Status row
    status_row = tb.Frame(status_content, bootstyle="secondary")
    status_row.pack(fill="x")

    status_indicator = tb.Label(
        status_row,
        text="●",
        font=("Helvetica", 28),
        foreground="#fbbf24"
    )
    status_indicator.pack(side="left", padx=(0, 15))

    status_text_frame = tb.Frame(status_row, bootstyle="secondary")
    status_text_frame.pack(side="left", fill="x", expand=True)

    progress_label = tb.Label(
        status_text_frame,
        text="Ready",
        font=("Helvetica", 14, "bold"),
        foreground="#ffffff"
    )
    progress_label.pack(anchor="w")

    progress_detail = tb.Label(
        status_text_frame,
        text="System ready to start downloading",
        font=("Helvetica", 10),
        foreground="#94a3b8"
    )
    progress_detail.pack(anchor="w")

    # Progress bar
    progress_bar = tb.Progressbar(
        status_content,
        orient="horizontal",
        mode="determinate",
        bootstyle="success"
    )
    progress_bar.pack(fill="x", pady=(15, 0))

    # Log section
    log_label = tb.Label(
        content,
        text="Activity Log",
        font=("Helvetica", 11, "bold"),
        foreground="#e2e8f0"
    )
    log_label.pack(anchor="w", pady=(0, 10))

    log_container = tb.Frame(content, bootstyle="secondary")
    log_container.pack(fill="both", expand=True, pady=(0, 20))

    log_text = tk.Text(
        log_container,
        height=14,
        bg="#0f172a",
        fg="#10b981",
        font=("Courier", 10),
        wrap="word",
        relief="flat",
        padx=15,
        pady=15
    )
    log_text.pack(fill="both", expand=True)

    # Options section
    options_frame = tb.Frame(content, bootstyle="dark")
    options_frame.pack(fill="x", pady=(0, 20))

    low_res_var = tk.BooleanVar(value=False)
    low_res_check = tb.Checkbutton(
        options_frame,
        text="Low-Resolution Mode (Direct previews, faster)",
        variable=low_res_var,
        bootstyle="round-toggle"
    )
    low_res_check.pack(side="left")

    download_in_progress = [False]

    def log_message(msg):
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)

    def start_download():
        if download_in_progress[0]:
            return

        download_in_progress[0] = True
        start_button.config(state="disabled", text="Downloading...")
        status_indicator.config(foreground="#10b981")
        progress_label.config(text="In Progress")
        progress_detail.config(text="Downloading files...")
        log_message("=" * 70)
        mode_str = "LOW-RES" if low_res_var.get() else "SOURCE QUALITY"
        log_message(f"⚡ STARTING {mode_str} DOWNLOAD ENGINE")
        log_message("=" * 70)

        threading.Thread(target=run_download, daemon=True).start()

    def run_download():
        low_res = low_res_var.get()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f) or {}

            output_directory = _sanitize_output_dir(config.get("output_directory", ""))
            try:
                os.makedirs(output_directory, exist_ok=True)
            except Exception:
                output_directory = _default_output_dir()
                os.makedirs(output_directory, exist_ok=True)

            with open(urls_file, "r", encoding="utf-8") as file:
                urls = [line.strip() for line in file if line.strip()]

            if not urls:
                log_message("No URLs found. Please add URLs first.")
                return

            script_dir = os.path.dirname(os.path.realpath(__file__))
            cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")

            if not os.path.exists(cookie_file):
                log_message("ERROR: Cookies not configured yet.")
                return

            with open(cookie_file, "r", encoding="utf-8") as f:
                cookie_data = json.load(f) or {}

            if not _has_auth_cookies(cookie_data):
                log_message("ERROR: Cookies file configured incorrectly.")
                return

            # Setup output directory with suffix if needed
            folder_name = get_folder_name(urls[0])
            suffix = "_lowres" if low_res else ""
            combined_output_dir = os.path.join(output_directory, folder_name + suffix)
            os.makedirs(combined_output_dir, exist_ok=True)

            # Setup requests session
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
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
                    
                    try:
                        page = context.new_page()
                        page.goto(url, wait_until='networkidle', timeout=60000)
                        time.sleep(2)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        
                        html_content = page.content()
                        page.close()

                        if not html_content:
                            log_message("Failed to fetch page content")
                            continue
                        
                        soup = BeautifulSoup(html_content, 'html.parser')
                        images = soup.select('div.bbWrapper img')
                        log_message(f"Found {len(images)} images. Processing...")
                        
                        page_downloaded = 0
                        for idx, img in enumerate(images):
                            try:
                                source_url = None
                                
                                if not low_res:
                                    # Speculative Path: Try suffix stripping the thumbnail URL first
                                    thumb_src = img.get('data-url') or img.get('data-src') or img.get('src')
                                    if thumb_src:
                                        if thumb_src.startswith('//'): thumb_src = 'https:' + thumb_src
                                        elif thumb_src.startswith('/'): thumb_src = 'https://simpcity.cr' + thumb_src
                                        
                                        if any(host in thumb_src for host in ['selti-delivery.ru', 'imgbox.com', 'pixl.is']):
                                            speculative_source = verify_full_quality(thumb_src, session)
                                            if speculative_source != thumb_src:
                                                source_url = speculative_source
                                    
                                    # Traditional Path: Resolve parent link if speculative failed
                                    if not source_url:
                                        parent_a = img.find_parent('a')
                                        if parent_a:
                                            href = parent_a.get('href')
                                            if href:
                                                log_message(f"  [{idx+1}/{len(images)}] Resolving: {href[:50]}...")
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
                                            
                                            page_downloaded += 1
                                            total_downloaded += 1
                                            log_message(f"    ✓ Downloaded: {filename} ({len(img_response.content)//1024} KB)")

                            except Exception as e:
                                log_message(f"    ✗ Error: {str(e)[:50]}")
                            
                            # UI Progress Update
                            progress = ((idx + 1) / len(images)) * 100
                            frame.after(0, lambda val=progress: progress_bar.configure(value=val))
                            status_text = page_status(idx + 1, len(images), current_page_idx, total_pages)
                            frame.after(0, lambda st=status_text: progress_label.config(text=st))
                            time.sleep(0.1)

                        log_message(f"Page complete: {page_downloaded} images downloaded")
                    except Exception as e:
                        log_message(f"ERROR on page {current_page_idx}: {str(e)}")

                browser.close()

            log_message(f"\n{'='*60}")
            log_message(f"✅ DOWNLOAD COMPLETE!")
            log_message(f"📊 Total downloaded: {total_downloaded}")
            log_message(f"📁 Saved to: {combined_output_dir}")
            log_message(f"{'='*60}")
            
            frame.after(0, lambda: status_indicator.config(foreground="#00ff00"))
            frame.after(0, lambda: progress_label.config(text="Download complete!"))
            frame.after(0, lambda: progress_detail.config(text=f"{total_downloaded} images saved successfully"))

        except Exception as e:
            log_message(f"\n{'='*60}")
            log_message(f"❌ ERROR: {str(e)}")
            log_message(f"{'='*60}")
            import traceback
            log_message(traceback.format_exc())
            frame.after(0, lambda: status_indicator.config(foreground="#dc3545"))
            frame.after(0, lambda: progress_label.config(text="Download failed"))
            frame.after(0, lambda: progress_detail.config(text="Check log for details"))
        finally:
            download_in_progress[0] = False
            frame.after(0, lambda: start_button.config(state="normal", text="▶️ Start Download"))

    def page_status(current_img, total_img, current_page, total_pages):
        return f"Page {current_page}/{total_pages}: {current_img}/{total_img} images"

    # Control buttons
    button_frame = tb.Frame(frame, bootstyle="dark")
    button_frame.pack(pady=10)

    start_button = tb.Button(
        button_frame, text="▶️ Start Download", bootstyle="success", command=start_download
    )
    start_button.pack(side="left", padx=5, ipadx=20, ipady=10)

    def clear_log():
        log_text.delete(1.0, tk.END)
        progress_bar.configure(value=0)
        status_indicator.config(foreground="#ffc107")
        progress_label.config(text="Ready to download")
        progress_detail.config(text="Click 'Start Download' to begin")

    clear_button = tb.Button(
        button_frame, text="🗑️ Clear Log", bootstyle="secondary-outline", command=clear_log
    )
    clear_button.pack(side="left", padx=5, ipadx=20, ipady=10)

    return frame
