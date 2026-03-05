import os
import time
import json
import requests
import tkinter as tk
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

def _default_output_dir() -> str:
    return os.path.join(os.path.expanduser('~'), 'Downloads', 'SimpDL')

def _sanitize_output_dir(path: str) -> str:
    path = (path or '').strip()
    if not path or path == '/path':
        return _default_output_dir()
    return os.path.expanduser(path)

def _has_auth_cookies(cookie_data: dict) -> bool:
    if not isinstance(cookie_data, dict):
        return False
    ch = (cookie_data.get('cookie_header') or '').strip()
    pc = cookie_data.get('parsed_cookies') or {}
    return bool(ch) or (isinstance(pc, dict) and len(pc) > 0)


def _normalize_url(page_url, raw_url):
    if not raw_url:
        return None
    raw_url = raw_url.strip()
    if not raw_url or raw_url.startswith(("data:", "javascript:", "#")):
        return None
    if raw_url.startswith("//"):
        return "https:" + raw_url
    return urljoin(page_url, raw_url)


def _parse_srcset(srcset_value):
    urls = []
    for part in srcset_value.split(","):
        part = part.strip()
        if not part:
            continue
        urls.append(part.split()[0])
    return urls


def _looks_like_thumbnail(image_url):
    lower = image_url.lower()
    thumb_hints = (
        "thumbnail",
        "/thumb/",
        "/thumbs/",
        "thumb_",
        "_thumb",
        "-thumb",
        "/small/",
        "/preview/",
        "preview="
    )
    return any(hint in lower for hint in thumb_hints)


def _extract_image_candidates(img_tag, page_url):
    raw_candidates = []
    parent_link = img_tag.find_parent("a")
    if parent_link:
        raw_candidates.extend([
            parent_link.get("href"),
            parent_link.get("data-url"),
            parent_link.get("data-src")
        ])

    raw_candidates.extend([
        img_tag.get("data-full-src"),
        img_tag.get("data-full"),
        img_tag.get("data-original"),
        img_tag.get("data-url"),
        img_tag.get("data-src")
    ])

    data_srcset = img_tag.get("data-srcset")
    if data_srcset:
        raw_candidates.extend(reversed(_parse_srcset(data_srcset)))

    srcset = img_tag.get("srcset")
    if srcset:
        raw_candidates.extend(reversed(_parse_srcset(srcset)))

    raw_candidates.append(img_tag.get("src"))

    normalized = []
    seen = set()
    for raw_url in raw_candidates:
        normalized_url = _normalize_url(page_url, raw_url)
        if normalized_url and normalized_url not in seen:
            seen.add(normalized_url)
            normalized.append(normalized_url)

    preferred = [url for url in normalized if not _looks_like_thumbnail(url)]
    fallback = [url for url in normalized if url not in preferred]
    return preferred + fallback


def _collect_image_candidates(soup, page_url):
    candidates = []
    seen_first = set()

    for img_tag in soup.find_all("img"):
        candidate_set = _extract_image_candidates(img_tag, page_url)
        if not candidate_set:
            continue

        first_choice = candidate_set[0]
        if first_choice in seen_first:
            continue

        seen_first.add(first_choice)
        candidates.append(candidate_set)

    return candidates


def _is_valid_image_response(response):
    if response.status_code != 200:
        return False
    try:
        image = Image.open(BytesIO(response.content))
        width, height = image.size
        return width >= 256 and height >= 256
    except Exception:
        return False


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
        log_message("⚡ STARTING HYBRID DOWNLOAD ENGINE")
        log_message("=" * 70)

        threading.Thread(target=run_download, daemon=True).start()

    def download_page_with_browser(url, output_dir):
        """Use browser for a single page (page 1 only)"""
        log_message(f"🌐 Opening browser for: {url}")
        
        script_dir = os.path.dirname(os.path.realpath(__file__))
        cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")
        
        with open(cookie_file, "r") as f:
            cookie_data = json.load(f)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            # Set cookies
            if "parsed_cookies" in cookie_data:
                cookies_to_set = []
                for name, value in cookie_data["parsed_cookies"].items():
                    cookies_to_set.append({
                        'name': name,
                        'value': value,
                        'domain': '.simpcity.cr',
                        'path': '/'
                    })
                context.add_cookies(cookies_to_set)
            
            page = context.new_page()
            page.goto(url, wait_until='networkidle', timeout=60000)
            time.sleep(3)
            
            # Scroll to load images
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            html = page.content()
            browser.close()
            
            return html

    def download_page_with_requests(session, url):
        """Use requests for pages 2+"""
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            return response.text
        return None

    def run_download():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f) or {}

            output_directory = _sanitize_output_dir(config.get("output_directory", ""))
            # Make sure it's creatable; if not, fall back to ~/Downloads/SimpDL
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
                log_message("Open config/manual_cookies.json and paste your Cookie header, or run extract_cookie_header.py")
                return

            with open(cookie_file, "r", encoding="utf-8") as f:
                cookie_data = json.load(f) or {}

            if not _has_auth_cookies(cookie_data):
                log_message("ERROR: Cookies file exists but is empty.")
                log_message("Open config/manual_cookies.json and paste your Cookie header, or run extract_cookie_header.py")
                return

            # Cookie header (requests) or parsed cookies (playwright) will be used below
            if "cookie_header" in cookie_data:
                cookie_header = cookie_data.get("cookie_header", "")
            else:
                cookie_header = None

            folder_name = get_folder_name(urls[0])
            combined_output_dir = os.path.join(output_directory, folder_name)
            if not os.path.exists(combined_output_dir):
                os.makedirs(combined_output_dir)

            # Setup requests session for pages 2+
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://simpcity.cr/'
            }
            
            if cookie_header:
                headers['Cookie'] = cookie_header
            
            session.headers.update(headers)

            total_pages = len(urls)
            total_downloaded = 0

            for current_page, url in enumerate(urls, 1):
                log_message(f"\n[Page {current_page}/{total_pages}] Processing: {url}")
                
                # Use browser ONLY for page 1 or pages without /page-X
                is_first_page = (current_page == 1 and '/page-' not in url) or '/page-1' in url
                
                try:
                    if is_first_page:
                        log_message("Using BROWSER method (bypasses page 1 protection)...")
                        html_content = download_page_with_browser(url, combined_output_dir)
                    else:
                        log_message("Using REQUESTS method (fast)...")
                        time.sleep(2)
                        html_content = download_page_with_requests(session, url)
                    
                    if not html_content:
                        log_message("Failed to fetch page content")
                        continue
                    
                    # Parse HTML
                    soup = BeautifulSoup(html_content, 'html.parser')
                    images = soup.find_all('img')
                    image_candidates = _collect_image_candidates(soup, url)

                    log_message(f"Found {len(images)} image tags.")
                    log_message(f"Resolved {len(image_candidates)} candidate image URLs (source-first).")
                    
                    page_downloaded = 0
                    for idx, candidates in enumerate(image_candidates):
                        downloaded = False
                        try:
                            for img_url in candidates:
                                img_headers = session.headers.copy()
                                img_headers['Referer'] = url
                                
                                img_response = session.get(img_url, timeout=15, headers=img_headers)
                                
                                if _is_valid_image_response(img_response):
                                    filename = f"image_{len(os.listdir(combined_output_dir)) + 1}.jpg"
                                    filepath = os.path.join(combined_output_dir, filename)
                                    
                                    with open(filepath, 'wb') as f:
                                        f.write(img_response.content)
                                    
                                    page_downloaded += 1
                                    total_downloaded += 1
                                    downloaded = True

                                if downloaded:
                                    log_message(f"  Downloaded: {filename}")
                                    break
                                    
                        except Exception as e:
                            log_message(f"  ✗ Error: {str(e)[:50]}")
                        
                        if not downloaded:
                            log_message("  Skipped: no valid source image URL")

                        progress = ((idx + 1) / len(image_candidates)) * 100 if image_candidates else 100
                        frame.after(0, lambda val=progress: progress_bar.configure(value=val))
                        status_text = page_status(idx + 1, len(image_candidates), current_page, total_pages)
                        frame.after(0, lambda st=status_text: progress_label.config(text=st))
                        
                        time.sleep(0.2)
                    
                    log_message(f"Page complete: {page_downloaded} images downloaded")
                
                except Exception as e:
                    log_message(f"ERROR on page {current_page}: {str(e)}")

            log_message(f"\n{'='*60}")
            log_message(f"✅ DOWNLOAD COMPLETE!")
            log_message(f"{'='*60}")
            log_message(f"📊 Total images downloaded: {total_downloaded}")
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

    def get_folder_name(url):
        url = url.rstrip('/')
        parts = url.split('/')
        if 'threads' in parts:
            idx = parts.index('threads')
            if idx + 1 < len(parts):
                folder = parts[idx + 1]
                if folder.startswith('page-'):
                    if idx + 2 < len(parts):
                        folder = parts[idx + 2]
                return folder.split('?')[0]
        return "default_folder"

    # Control buttons
    button_frame = tb.Frame(frame, bootstyle="dark")
    button_frame.pack(pady=10)

    start_button = tb.Button(
        button_frame,
        text="▶️ Start Download",
        bootstyle="success",
        command=start_download
    )
    start_button.pack(side="left", padx=5, ipadx=20, ipady=10)

    def clear_log():
        log_text.delete(1.0, tk.END)
        progress_bar.configure(value=0)
        status_indicator.config(foreground="#ffc107")
        progress_label.config(text="Ready to download")
        progress_detail.config(text="Click 'Start Download' to begin")

    clear_button = tb.Button(
        button_frame,
        text="🗑️ Clear Log",
        bootstyle="secondary-outline",
        command=clear_log
    )
    clear_button.pack(side="left", padx=5, ipadx=20, ipady=10)

    return frame
