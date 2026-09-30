"""Forum URL, cookie and HTML handling, independent of the GUI/network."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

BASE_URL = "https://simpcity.cr"
POST_SELECTOR = ".message-body .bbWrapper, .message-content .bbWrapper, .message-body, .message-attachments, [itemprop='articleBody']"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".m4v", ".webm", ".mov", ".mkv", ".avi", ".ogv", ".mpeg", ".mpg")
STREAM_EXTENSIONS = (".m3u8", ".mpd")
VIDEO_HOSTS = ("turbo.cr", "cyberdrop.cr", "cyberdrop.me", "cyberdrop.to", "bunkr.cr", "bunkr.su", "bunkr.ru", "bunkr.si", "bunkr.site", "youtu.be", "youtube.com", "youtube-nocookie.com", "vimeo.com", "twitch.tv", "giphy.com", "redgifs.com", "streamable.com")


@dataclass(frozen=True)
class MediaItem:
    url: str
    kind: str


def is_video_url(url):
    parts = urlsplit(url)
    route = parts.query.split("&", 1)[0] if parts.path.endswith("index.php") else parts.path
    return route.lower().endswith(VIDEO_EXTENSIONS + STREAM_EXTENSIONS) or bool(
        re.search(r"[.-](?:mp4|m4v|webm|mov|mkv|avi|ogv|mpeg|mpg)\.[0-9]+/?$", route, re.I)
    )


def is_video_host(url):
    parts = urlsplit(url)
    return bool(parts.path.strip("/")) and any(
        parts.hostname == host or (parts.hostname or "").endswith("." + host) for host in VIDEO_HOSTS
    )


def thread_url(url, page=None):
    """Normalize XenForo friendly and index.php?threads/... routes."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or parts.hostname not in ("simpcity.cr", "www.simpcity.cr"):
        raise ValueError("Enter a thread URL on https://simpcity.cr")
    query_route = parts.path.rstrip("/") == "/index.php"
    route = parts.query.split("&", 1)[0] if query_route else parts.path.lstrip("/")
    match = re.fullmatch(r"threads/([^/]+\.[0-9]+|[0-9]+)(?:/(?:page-([0-9]+)|unread|latest))?/?", route)
    if not match:
        raise ValueError("Expected a thread URL: https://simpcity.cr/threads/name.123/")
    tail = parts.query.split("&", 1)[1] if query_route and "&" in parts.query else ""
    params = dict(parse_qsl(tail if query_route else parts.query))
    number = page if page is not None else int(match[2] or params.get("page", "1"))
    if number < 1:
        raise ValueError("Page number must be at least 1")
    route = f"threads/{match[1]}/" + (f"page-{number}" if number > 1 else "")
    return f"{BASE_URL}/index.php?{route}" if query_route else f"{BASE_URL}/{route}"


def generate_links(base_link, num_pages):
    if num_pages < 1:
        raise ValueError("Number of pages must be at least 1")
    return [thread_url(base_link, page) for page in range(1, num_pages + 1)]


def thread_key(url):
    route = thread_url(url, 1).split("threads/", 1)[1].strip("/")
    return route.rsplit(".", 1)[-1]


def thread_folder(url):
    route = thread_url(url, 1).split("threads/", 1)[1].strip("/")
    return re.sub(r"[^\w.-]+", "_", route)[:160].strip(".") or "thread"


def parse_cookies(data):
    """Accept the header format, parsed_cookies and legacy name/value JSON."""
    if not isinstance(data, dict):
        raise ValueError("Cookie file must contain a JSON object")
    cookies = {}
    parsed = data.get("parsed_cookies", {})
    if isinstance(parsed, dict):
        cookies.update({k: str(v) for k, v in parsed.items() if v})
    header = data.get("cookie_header", "") or ""
    if not isinstance(header, str):
        raise ValueError("cookie_header must be a string")
    header = re.sub(r"^cookie:\s*", "", header.strip(), flags=re.I)
    for pair in header.split(";"):
        if "=" in pair:
            key, value = pair.strip().split("=", 1)
            if key and value:
                cookies[key] = value
    if "cookie_header" not in data and "parsed_cookies" not in data:
        cookies.update({k: str(v) for k, v in data.items() if isinstance(v, str) and v and k not in ("notes", "user_agent")})
    return cookies


def http_url(value, base_url):
    if not value:
        return None
    url = urljoin(base_url, value.strip())
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _direct_image(url):
    if is_video_url(url):
        return False
    parts = urlsplit(url)
    return parts.path.lower().endswith(IMAGE_EXTENSIONS) or (
        parts.hostname in ("simpcity.cr", "www.simpcity.cr")
        and (parts.path.startswith("/attachments/") or parts.query.startswith("attachments/"))
    )


def _srcset(value):
    candidates = []
    for entry in (value or "").split(","):
        fields = entry.split()
        if fields and not fields[0].startswith("data:"):
            try:
                weight = float(fields[1][:-1]) if len(fields) > 1 else 1
            except ValueError:
                weight = 0
            candidates.append((weight, fields[0]))
    return max(candidates, default=(0, None))[1]


def extract_images(soup, page_url):
    """Only post content; prefer full-size links and lazy sources to thumbnails."""
    found = []
    for body in soup.select(POST_SELECTOR):
        for image in body.select("img"):
            if set(image.get("class", [])) & {"smilie", "emoji", "avatar"}:
                continue
            anchor = image.find_parent("a", href=True)
            linked = http_url(anchor.get("href"), page_url) if anchor else None
            sources = [linked if linked and _direct_image(linked) else None]
            sources += [image.get(attr) for attr in ("data-full-url", "data-src", "data-original", "data-lazy-src")]
            sources += [_srcset(image.get("data-srcset") or image.get("srcset"))]
            picture = image.find_parent("picture")
            if picture:
                sources += [_srcset(source.get("data-srcset") or source.get("srcset")) for source in picture.select("source")]
            sources += [image.get("src"), image.get("data-url")]
            for source in sources:
                url = http_url(source, page_url)
                if url:
                    found.append(url)
                    break
        for anchor in body.select("a[href]"):
            url = http_url(anchor.get("href"), page_url)
            if url and _direct_image(url):
                found.append(url)
    return list(dict.fromkeys(found))


def page_error(soup, url, status=200):
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if status in (401, 403, 429, 503) or soup.select_one("#challenge-form, #cf-challenge-running") or title in ("just a moment...", "attention required! | cloudflare"):
        return f"Access blocked or browser verification required (HTTP {status}). Refresh your cookies or use browser mode."
    if status >= 400:
        return f"HTTP {status} while fetching the thread"
    if "/login" in urlsplit(url).path or (not soup.select_one(POST_SELECTOR) and soup.select_one("input[name='password']")):
        return "Login required. Refresh your cookies from a browser that can open this thread."
    if not soup.select_one(POST_SELECTOR):
        return "No forum posts found. The page may require login, be unavailable, or use unsupported markup."
    return None


def next_page(soup, current_url):
    for anchor in soup.select("a[rel~='next'], a.pageNav-jump--next, .pageNavSimple-el--next"):
        url = http_url(anchor.get("href"), current_url)
        try:
            if url and thread_key(url) == thread_key(current_url):
                return thread_url(url)
        except ValueError:
            continue
    return None


def parse_page(html, url, status=200):
    soup = BeautifulSoup(html, "html.parser")
    error = page_error(soup, url, status)
    if error:
        raise ValueError(error)
    return extract_images(soup, url), next_page(soup, url)


def extract_media(soup, page_url):
    videos = {}
    for body in soup.select(POST_SELECTOR):
        for video in body.select("video"):
            values = [video.get("data-src"), video.get("src")]
            for source in video.select("source"):
                values.extend([source.get("data-src"), source.get("src")])
            for value in values:
                url = http_url(value, page_url)
                if url:
                    videos[url] = MediaItem(url, "video")
                    break  # Alternative encodings are the same video.
        for node in body.select("iframe, [data-video-url], a[href]"):
            if node.name == "a":
                value = node.get("href")
                url = http_url(value, page_url)
                if not url or not (is_video_url(url) or is_video_host(url) or node.get("type", "").startswith("video/")):
                    continue
                kind = "video" if is_video_url(url) or node.get("type", "").startswith("video/") else "embed"
            else:
                value = node.get("data-video-url") or node.get("data-src") or node.get("src")
                url = http_url(value, page_url)
                kind = "video" if node.has_attr("data-video-url") or (url and is_video_url(url)) else "embed"
            if url:
                videos[url] = MediaItem(url, kind)
    images = [MediaItem(url, "image") for url in extract_images(soup, page_url) if url not in videos]
    return images + list(videos.values())


def parse_media_page(html, url, status=200):
    soup = BeautifulSoup(html, "html.parser")
    error = page_error(soup, url, status)
    if error:
        raise ValueError(error)
    return extract_media(soup, url), next_page(soup, url)
