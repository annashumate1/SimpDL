"""Resolve video players and stream videos to disk without buffering them in RAM."""

from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from site_utils import STREAM_EXTENSIONS, http_url


def turbo_id(url):
    parts = urlsplit(url)
    if parts.hostname not in ("turbo.cr", "www.turbo.cr"):
        return None
    match = re.fullmatch(r"/(?:d|v|embed)/([A-Za-z0-9_-]+)/?", parts.path)
    return match[1] if match else None


def video_identity(url):
    identifier = turbo_id(url)
    return f"https://turbo.cr/embed/{identifier}" if identifier else url


def video_extension(header):
    """Check container signatures; an HTTP-200 error page is never a video."""
    if len(header) >= 12 and header[4:8] == b"ftyp":
        if header[8:12] in (b"avif", b"avis", b"heic", b"heix", b"mif1"):
            raise ValueError("The server returned an image, not a video")
        return ".mov" if header[8:12] == b"qt  " else ".mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm" if b"webm" in header.lower() else ".mkv"
    if header.startswith(b"OggS"):
        return ".ogv"
    if header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return ".avi"
    if header.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):
        return ".mpeg"
    if len(header) >= 8 and header[4:8] in (b"wide", b"moov", b"mdat"):
        return ".mov"
    raise ValueError("The server did not return a supported video file (it may require login)")


class VideoDownloader:
    def __init__(self, session, log=print, transfer=lambda *args: None):
        self.session = session
        self.log = log
        self.transfer = transfer

    def resolve_turbo(self, url):
        identifier = turbo_id(url)
        if not identifier:
            raise ValueError("Unrecognized Turbo video URL")
        player_url = f"https://turbo.cr/embed/{identifier}"
        # This is the same public signing request made by Turbo's embedded player.
        with self.session.get(player_url, timeout=(15, 30)) as response:
            response.raise_for_status()
        with self.session.get("https://turbo.cr/api/sign", params={"v": identifier},
                              headers={"Referer": player_url}, timeout=(15, 30)) as response:
            response.raise_for_status()
            data = response.json()
        media_url = http_url(data.get("url"), player_url)
        if not data.get("success") or not media_url:
            raise ValueError("Turbo could not provide a video URL. The file may be unavailable or require verification.")
        return media_url, player_url

    def save(self, url, referer, directory, cancelled=lambda: False, embedded=False):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        identity = sha256(video_identity(url).encode()).hexdigest()
        index_path = directory / ".simpdl-videos.json"
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(index, dict):
                index = {}
        except (FileNotFoundError, ValueError):
            index = {}
        previous = index.get(identity, {})
        if isinstance(previous, dict):
            filename = previous.get("file", "")
            if filename and Path(filename).name == filename:
                target = directory / filename
                if target.is_file() and target.stat().st_size == previous.get("size"):
                    return False
        if cancelled():
            raise InterruptedError("Download cancelled")
        if turbo_id(url):
            self.log("Resolving Turbo video…")
            url, referer = self.resolve_turbo(url)
            embedded = False
        streaming = urlsplit(url).path.lower().endswith(STREAM_EXTENSIONS)
        with tempfile.TemporaryDirectory(prefix=".simpdl-video-", dir=directory) as working:
            working = Path(working)
            if embedded or streaming:
                source = self._download_player(url, referer, working, cancelled)
            else:
                source = self._download_direct(url, referer, working, cancelled)
            if cancelled():
                raise InterruptedError("Download cancelled")
            digest = sha256()
            with source.open("rb") as handle:
                extension = video_extension(handle.read(4096))
                handle.seek(0)
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    if cancelled():
                        raise InterruptedError("Download cancelled")
                    digest.update(chunk)
            target = directory / (digest.hexdigest() + extension)
            saved = not target.exists() or target.stat().st_size != source.stat().st_size
            if saved:
                source.replace(target)
            index[identity] = {"file": target.name, "size": target.stat().st_size}
            temporary_index = working / "index.json"
            temporary_index.write_text(json.dumps(index, indent=2), encoding="utf-8")
            temporary_index.replace(index_path)
        return saved

    def _download_direct(self, url, referer, working, cancelled):
        path = working / "video.part"
        headers = {"Referer": referer, "Accept-Encoding": "identity"}
        with self.session.get(url, headers=headers, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            try:
                total = int(response.headers.get("Content-Length", 0))
            except ValueError:
                total = 0
            received = 0
            prefix = bytearray()
            with path.open("wb") as handle:
                for chunk in response.iter_content(256 * 1024):
                    if cancelled():
                        raise InterruptedError("Download cancelled")
                    if not chunk:
                        continue
                    if len(prefix) < 4096:
                        prefix.extend(chunk[:4096 - len(prefix)])
                        if len(prefix) >= 4096:
                            video_extension(prefix)
                    handle.write(chunk)
                    received += len(chunk)
                    self.transfer(received, total)
            if total and received != total and not response.headers.get("Content-Encoding"):
                raise ValueError("Video download was incomplete; retry this thread")
            video_extension(prefix)
        return path

    def _download_player(self, url, referer, working, cancelled):
        import yt_dlp

        owner = self

        class Logger:
            def debug(self, message):
                pass

            def warning(self, message):
                owner.log(str(message))

            def error(self, message):
                owner.log(str(message))

        def progress(info):
            if cancelled():
                raise InterruptedError("Download cancelled")
            self.transfer(info.get("downloaded_bytes", 0), info.get("total_bytes") or info.get("total_bytes_estimate") or 0)

        def reject_live(info, *, incomplete=False):
            if cancelled():
                raise InterruptedError("Download cancelled")
            if info.get("is_live"):
                return "Live streams are not downloaded"

        options = {
            "paths": {"home": str(working)}, "outtmpl": "video.%(ext)s",
            "format": "bestvideo+bestaudio/best" if shutil.which("ffmpeg") else "best",
            "noplaylist": True, "playlist_items": "1", "quiet": True,
            "logger": Logger(), "progress_hooks": [progress], "match_filter": reject_live,
            "socket_timeout": 30, "retries": 2, "fragment_retries": 2,
            "http_headers": {"Referer": referer, "User-Agent": self.session.headers["User-Agent"]},
            "cachedir": False,
        }
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                for cookie in self.session.cookies:
                    downloader.cookiejar.set_cookie(cookie)
                downloader.extract_info(url, download=True)
        except Exception:
            if cancelled():
                raise InterruptedError("Download cancelled") from None
            raise
        files = [path for path in working.iterdir() if path.is_file() and path.suffix.lower() in
                 (".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".ogv", ".mpeg", ".mpg")]
        if len(files) != 1:
            raise ValueError("No single playable video was produced. This host may be unsupported or need ffmpeg.")
        return files[0]
