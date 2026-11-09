"""Authenticated thread fetching and concurrent image/video downloads."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.parse import urlsplit

from PIL import Image
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config_utils import read_json, write_json
from site_utils import POST_SELECTOR, parse_media_page, parse_cookies, thread_folder, thread_key, thread_url
from video_utils import VideoDownloader, bunkr_items, bunkr_route, content_length, resolve_bunkr, session_cookies, video_identity

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp", "AVIF": ".avif", "BMP": ".bmp"}
# Files downloaded at once. Six is what a browser opens per host; file hosts answer much more with HTTP 429.
WORKERS = 6


@dataclass
class DownloadResult:
    pages: int = 0
    saved: int = 0
    skipped: int = 0
    errors: int = 0
    cancelled: bool = False
    images: int = 0
    videos: int = 0
    found: int = 0  # Files discovered so far ...
    done: int = 0  # ... and how many of them are saved, skipped or failed.


class MediaIndex:
    """One folder's record of finished downloads, so a rerun skips them without any network request."""

    def __init__(self, directory):
        self.path = Path(directory) / ".simpdl-videos.json"  # The name predates image records.
        self.lock = threading.Lock()
        self.unsaved = False
        self.written = time.monotonic()
        try:
            self.entries = read_json(self.path)
        except (ValueError, OSError):
            self.entries = {}

    @staticmethod
    def _key(url):
        return sha256(video_identity(url).encode()).hexdigest()

    def known(self, url):
        entry = self.entries.get(self._key(url))
        if not isinstance(entry, dict):
            return False
        if entry.get("ignored"):
            return True
        name = entry.get("file")
        if not isinstance(name, str) or Path(name).name != name:
            return False
        target = self.path.parent / name
        return target.is_file() and target.stat().st_size == entry.get("size")

    def record(self, url, target=None):
        """`target` is the file holding this URL's content, or None for an image too small to keep."""
        with self.lock:
            self.entries[self._key(url)] = {"file": target.name, "size": target.stat().st_size} if target else {"ignored": True}
            self.unsaved = True
        self.flush(5)  # A crash or kill loses only the last few seconds of records.

    def flush(self, interval=0):
        with self.lock:
            if self.unsaved and time.monotonic() - self.written >= interval:
                write_json(self.path, self.entries)
                self.unsaved = False
                self.written = time.monotonic()


class ThreadClient:
    def __init__(self, cookie_data, log=print, browser_mode=False):
        self.log = log
        self.browser_mode = browser_mode
        self.http_works = None if browser_mode else True  # None: not tried yet, the browser has to sign in first
        self.cookie_data = cookie_data
        self.session = requests.Session()
        # File-host CDN nodes (notably Bunkr's) answer with sporadic 502s; the final response still reaches callers.
        # Retry-After is ignored because Stop cannot interrupt a wait the server chose; the backoff is at most 8 seconds.
        retry = Retry(total=4, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), raise_on_status=False,
                      respect_retry_after_header=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "User-Agent": cookie_data.get("user_agent") or DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })
        for name, value in parse_cookies(cookie_data).items():
            self.session.cookies.set(name, value, domain="simpcity.cr", path="/", secure=True)
        self.playwright = self.browser = self.context = self.page = None
        self.video_downloader = VideoDownloader(self.session, log)
        self.indexes = {}
        self.index_lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            for index in self.indexes.values():
                index.flush()
        finally:
            try:
                if self.browser:
                    self.browser.close()
            finally:
                try:
                    if self.playwright:
                        self.playwright.stop()
                finally:
                    self.session.close()

    def _index(self, directory):
        directory = Path(directory)
        with self.index_lock:
            if directory not in self.indexes:
                # Nothing downloads into this folder before its index exists, so these are leftovers of a killed run.
                for stale in directory.glob(".simpdl-video-*"):
                    shutil.rmtree(stale, ignore_errors=True)
                self.indexes[directory] = MediaIndex(directory)
            return self.indexes[directory]

    def _browser_page(self, url, cancelled):
        if not self.page:
            from playwright.sync_api import sync_playwright

            self.playwright = self.playwright or sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=not self.browser_mode)
            options = {}
            if self.cookie_data.get("user_agent"):
                options["user_agent"] = self.cookie_data["user_agent"]
            self.context = self.browser.new_context(**options)
            self.context.add_cookies([
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path, "secure": c.secure}
                for c in session_cookies(self.session)
            ])
            self.page = self.context.new_page()
            self.session.headers["User-Agent"] = self.page.evaluate("navigator.userAgent")
            if self.browser_mode:
                self.log("Browser opened. Complete login/verification there if prompted (up to 120 seconds).")
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        status = response.status if response else 200
        # Browser mode lets the user finish login/verification in the visible window.
        deadline = time.monotonic() + (120 if self.browser_mode else 5)
        while not self.page.locator(POST_SELECTOR).count() and time.monotonic() < deadline:
            if cancelled():
                raise InterruptedError("Download cancelled")
            self.page.wait_for_timeout(500)
        html = self.page.content()
        # A completed browser navigation can replace the original challenge response.
        if self.page.locator(POST_SELECTOR).count():
            status = 200
        parse_media_page(html, self.page.url, status)
        # Added, never cleared: downloads running on other threads keep using the session meanwhile.
        for cookie in self.context.cookies():
            self.session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"], secure=cookie.get("secure", False))
        return html, self.page.url

    def fetch_page(self, url, cancelled=lambda: False):
        if self.http_works:
            try:
                with self.session.get(url, timeout=(15, 45)) as response:
                    html = response.text
                    parse_media_page(html, response.url, response.status_code)
                if self.browser:  # Signed in and plain HTTP gets through: the window has done its job.
                    self.browser.close()
                    self.browser = self.context = self.page = None
                return html, response.url
            except (requests.RequestException, ValueError) as error:
                self.log(f"HTTP fetch could not read posts: {error}")
                self.log("Trying the browser for this page...")
        page = self._browser_page(url, cancelled)
        # After a browser login the next page tries plain HTTP with its cookies. Once the browser has had to
        # step in for a failed HTTP fetch, every later page goes straight to it instead of failing first.
        self.http_works = self.http_works is None
        return page

    def save_image(self, url, referer, directory, cancelled=lambda: False, transfer=lambda *args: None):
        """Fetch once, verify actual image bytes, and atomically save by content hash.

        Returns the new file, or None when nothing new was kept (known URL, duplicate content, tiny image).
        """
        index = self._index(directory)
        if index.known(url):
            return None
        source = url
        if bunkr_route(url):
            source, referer = resolve_bunkr(self.session, url)
        content = bytearray()
        with self.session.get(source, headers={"Referer": referer}, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            total = content_length(response)
            for chunk in response.iter_content(64 * 1024):
                if cancelled():
                    raise InterruptedError("Download cancelled")
                content.extend(chunk)
                if len(content) > 100 * 1024 * 1024:
                    raise ValueError("Image exceeds the 100 MiB download limit")
                transfer(len(content), total)
        with Image.open(BytesIO(content)) as image:
            extension = FORMATS.get(image.format)
            if extension is None:
                raise ValueError("Unsupported image format")
            if min(image.size) < 256:
                index.record(url)
                return None
            image.verify()
        destination = Path(directory) / (sha256(content).hexdigest() + extension)
        new = not destination.exists()
        if new:
            # Two URLs with identical content may finish together, so the partial name is per thread.
            partial = destination.with_name(f".simpdl-{threading.get_ident()}.part")
            try:
                partial.write_bytes(content)
                partial.replace(destination)
            finally:
                partial.unlink(missing_ok=True)
        index.record(url, destination)
        return destination if new else None

    def save_video(self, url, referer, directory, cancelled=lambda: False, embedded=False, transfer=lambda *args: None):
        """Returns the new file, or None when the video was already there."""
        index = self._index(directory)
        if index.known(url):
            return None
        target, new = self.video_downloader.save(url, referer, directory, cancelled, embedded, transfer)
        index.record(url, target)
        return target if new else None


def expand_hosts(client, media, log):
    """Replace Bunkr album/file links with the files they contain. Returns (media, number of links that failed)."""
    expanded = []
    failures = 0
    for item in media:
        if not bunkr_route(item.url):
            expanded.append(item)
            continue
        try:
            files = bunkr_items(client.session, item.url)
            log(f"Bunkr link has {len(files)} images/videos: {item.url}")
            expanded += files
        except Exception as error:
            failures += 1
            log(f"Bunkr link failed ({item.url}): {error}")
    return list(dict.fromkeys(expanded)), failures


def download_threads(client, urls, output_directory, log=print, progress=lambda result: None, cancelled=lambda: False,
                     follow_pagination=True, delay=1.0, media_types=("image", "video"), skip=(),
                     transfer=lambda *args: None, workers=WORKERS):
    """Read thread pages in order while a pool of workers downloads the files found so far.

    `progress(result)` gets a snapshot after every page and file. `transfer(task, label, done, total)` reports one
    file's bytes; done is None once that file has ended. Files are numbered from 1 in thread order, and adding a
    number to the caller's `skip` set abandons only that file.
    """
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
    lock = threading.Lock()  # Guards result; progress is called under it so snapshots arrive in order.
    new_files = {}
    started = time.time()

    def fetch(task, item, referer, directory):
        kind = "image" if item.kind == "image" else "video"
        label = f"{kind.capitalize()} · {urlsplit(item.url).hostname}"
        stopped = lambda: cancelled() or task in skip
        report = lambda done, total: transfer(task, label, done, total)
        path = error = None
        try:
            if stopped():
                raise InterruptedError("Download cancelled")
            report(0, 0)
            if kind == "image":
                path = client.save_image(item.url, referer, directory, stopped, transfer=report)
            else:
                path = client.save_video(item.url, referer, directory, stopped, embedded=item.kind == "embed", transfer=report)
        except InterruptedError:
            if cancelled():
                return
            log(f"Skipped at your request: {item.url}")
        except Exception as failure:
            error = failure
            log(f"{kind.capitalize()} failed ({item.url}): {error}")
        finally:
            report(None, 0)
        with lock:
            if error:
                result.errors += 1
            elif path:
                result.saved += 1
                if kind == "image":
                    result.images += 1
                else:
                    result.videos += 1
                if isinstance(path, Path):
                    new_files[task] = path
            else:
                result.skipped += 1
            result.done += 1
            progress(replace(result))

    task = 0
    with ThreadPoolExecutor(workers, thread_name_prefix="simpdl") as pool:  # Leaving the block waits for the files.
        while queue and not cancelled():
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if result.pages:
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline and not cancelled():
                    time.sleep(min(0.1, max(0, deadline - time.monotonic())))
            if cancelled():
                break
            log(f"Reading {url}")
            try:
                html, final_url = client.fetch_page(url, cancelled)
                key = thread_key(url)
                if thread_key(final_url) != key:
                    raise ValueError("Thread redirected to a different thread; check the URL")
                media, following = parse_media_page(html, final_url)
                media, failures = expand_hosts(client, media, log)
                media = [item for item in media if ("image" if item.kind == "image" else "video") in media_types]
                visited.add(thread_url(final_url))
                directory = Path(output_directory) / folders[key]
                directory.mkdir(parents=True, exist_ok=True)
                fresh = []
                for item in media:
                    media_key = (key, video_identity(item.url))
                    if media_key not in seen_media:
                        seen_media.add(media_key)
                        fresh.append(item)
                with lock:
                    result.pages += 1
                    result.errors += failures
                    result.found += len(media)
                    result.skipped += len(media) - len(fresh)
                    result.done += len(media) - len(fresh)
                    progress(replace(result))
                log(f"Found {len(media)} files on page {result.pages}")
                for item in fresh:
                    task += 1
                    pool.submit(fetch, task, item, final_url, directory)
                if following and key in follow_threads and following not in visited:
                    queue.append(following)
            except InterruptedError:
                break
            except Exception as error:
                with lock:
                    result.errors += 1
                    progress(replace(result))
                log(f"Page failed: {error}")
    # Workers finish out of order; spread the new files' timestamps over the run in thread order,
    # so sorting the folder by date modified still follows the thread.
    ended = time.time()
    for position, number in enumerate(sorted(new_files), 1):
        stamp = started + (ended - started) * position / len(new_files)
        try:
            os.utime(new_files[number], (stamp, stamp))
        except OSError:
            pass
    result.cancelled = cancelled()
    return result
