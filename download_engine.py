"""Authenticated thread fetching and image/video downloads."""

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import time
from urllib.parse import urlsplit

from PIL import Image
import requests

from site_utils import POST_SELECTOR, parse_cookies, parse_page, parse_media_page, thread_folder, thread_key, thread_url
from video_utils import VideoDownloader, video_identity

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp", "AVIF": ".avif", "BMP": ".bmp"}


@dataclass
class DownloadResult:
    pages: int = 0
    saved: int = 0
    skipped: int = 0
    errors: int = 0
    cancelled: bool = False
    images: int = 0
    videos: int = 0


class ThreadClient:
    def __init__(self, cookie_data, log=print, browser_mode=False, transfer=lambda *args: None):
        self.log = log
        self.browser_mode = browser_mode
        self.cookie_data = cookie_data
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": cookie_data.get("user_agent") or DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })
        for name, value in parse_cookies(cookie_data).items():
            self.session.cookies.set(name, value, domain="simpcity.cr", path="/", secure=True)
        self.playwright = self.browser = self.context = self.page = None
        self.video_downloader = VideoDownloader(self.session, log, transfer)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.browser:
                self.browser.close()
        finally:
            try:
                if self.playwright:
                    self.playwright.stop()
            finally:
                self.session.close()

    def _browser_page(self, url, cancelled):
        if not self.page:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=not self.browser_mode)
            options = {}
            if self.cookie_data.get("user_agent"):
                options["user_agent"] = self.cookie_data["user_agent"]
            self.context = self.browser.new_context(**options)
            self.context.add_cookies([
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path, "secure": c.secure}
                for c in self.session.cookies
            ])
            self.page = self.context.new_page()
            self.session.headers["User-Agent"] = self.page.evaluate("navigator.userAgent")
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        status = response.status if response else 200
        # Browser mode lets the user finish login/verification in the visible window.
        deadline = time.monotonic() + (120 if self.browser_mode else 5)
        if self.browser_mode:
            self.log("Browser opened. Complete login/verification there if prompted (up to 120 seconds).")
        while not self.page.locator(POST_SELECTOR).count() and time.monotonic() < deadline:
            if cancelled():
                raise InterruptedError("Download cancelled")
            self.page.wait_for_timeout(500)
        html = self.page.content()
        # A completed browser navigation can replace the original challenge response.
        if self.page.locator(POST_SELECTOR).count():
            status = 200
        parse_page(html, self.page.url, status)
        self.session.cookies.clear()
        for cookie in self.context.cookies():
            self.session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"], secure=cookie.get("secure", False))
        return html, self.page.url

    def fetch_page(self, url, cancelled=lambda: False):
        if not self.browser_mode:
            try:
                with self.session.get(url, timeout=(15, 45)) as response:
                    parse_page(response.text, response.url, response.status_code)
                    return response.text, response.url
            except (requests.RequestException, ValueError) as error:
                self.log(f"HTTP fetch could not read posts: {error}")
                self.log("Trying the browser for this page...")
        return self._browser_page(url, cancelled)

    def save_image(self, url, referer, directory, cancelled=lambda: False):
        """Fetch once, verify actual image bytes, and atomically save by content hash."""
        content = bytearray()
        with self.session.get(url, headers={"Referer": referer}, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(64 * 1024):
                if cancelled():
                    raise InterruptedError("Download cancelled")
                content.extend(chunk)
                if len(content) > 100 * 1024 * 1024:
                    raise ValueError("Image exceeds the 100 MiB download limit")
        with Image.open(BytesIO(content)) as image:
            extension = FORMATS.get(image.format)
            if extension is None:
                raise ValueError("Unsupported image format")
            if min(image.size) < 256:
                return False
            image.verify()
        destination = Path(directory) / (sha256(content).hexdigest() + extension)
        if destination.exists():
            return False
        partial = destination.with_suffix(extension + ".part")
        try:
            partial.write_bytes(content)
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
        return True

    def save_video(self, url, referer, directory, cancelled=lambda: False, embedded=False):
        return self.video_downloader.save(url, referer, directory, cancelled, embedded)


def download_threads(client, urls, output_directory, log=print, progress=lambda *args: None,
                     cancelled=lambda: False, follow_pagination=True, delay=1.0, media_types=("image", "video")):
    media_types = set(media_types)
    if not media_types or not media_types <= {"image", "video"}:
        raise ValueError("Choose images, videos, or both")
    normalized = list(dict.fromkeys(thread_url(url) for url in urls))
    if not normalized:
        raise ValueError("No URLs found. Add thread URLs first.")
    queue = deque(normalized)
    visited = set()
    seen_media = set()
    # Generated/explicit page lists keep their selected range. A bare thread follows Next.
    explicit_threads = {thread_key(url) for url in normalized if url != thread_url(url, 1)}
    follow_threads = {thread_key(url) for url in normalized} - explicit_threads if follow_pagination else set()
    folders = {thread_key(url): thread_folder(url) for url in normalized}
    result = DownloadResult()
    while queue:
        if cancelled():
            result.cancelled = True
            break
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if result.pages:
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline and not cancelled():
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        if cancelled():
            result.cancelled = True
            break
        log(f"Reading {url}")
        try:
            html, final_url = client.fetch_page(url, cancelled)
            if thread_key(final_url) != thread_key(url):
                raise ValueError("Thread redirected to a different thread; check the URL")
            media, following = parse_media_page(html, final_url)
            media = [item for item in media if ("image" if item.kind == "image" else "video") in media_types]
            visited.add(thread_url(final_url))
            result.pages += 1
            directory = Path(output_directory) / folders[thread_key(url)]
            directory.mkdir(parents=True, exist_ok=True)
            log(f"Found {len(media)} media links on page {result.pages}")
            if not media:
                log("No matching media on this page.")
            for index, item in enumerate(media, 1):
                if cancelled():
                    raise InterruptedError("Download cancelled")
                kind = "image" if item.kind == "image" else "video"
                media_key = (thread_key(url), item.url if kind == "image" else video_identity(item.url))
                if media_key not in seen_media:
                    try:
                        log(f"Downloading {kind} {index}/{len(media)} from {urlsplit(item.url).hostname}")
                        if kind == "image":
                            saved = client.save_image(item.url, final_url, directory, cancelled)
                        else:
                            saved = client.save_video(item.url, final_url, directory, cancelled, embedded=item.kind == "embed")
                        if saved:
                            result.saved += 1
                            if kind == "image":
                                result.images += 1
                            else:
                                result.videos += 1
                            log(f"Saved {kind} · {result.saved} files saved so far")
                        else:
                            result.skipped += 1
                        seen_media.add(media_key)
                    except InterruptedError:
                        raise
                    except Exception as error:
                        result.errors += 1
                        log(f"{kind.capitalize()} failed ({item.url}): {error}")
                else:
                    result.skipped += 1
                progress(result.pages, index, len(media), result.saved)
            if following and thread_key(url) in follow_threads and following not in visited:
                queue.append(following)
        except InterruptedError:
            result.cancelled = True
            break
        except Exception as error:
            result.errors += 1
            log(f"Page failed: {error}")
    return result
