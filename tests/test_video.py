from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from download_engine import ThreadClient, download_threads
from site_utils import parse_media_page
from video_utils import turbo_id, video_extension, video_identity

URL = "https://simpcity.cr/threads/example.123/"


def post(html):
    return f'<div class="message-body"><div class="bbWrapper">{html}</div></div>'


@contextmanager
def server_for(directory):
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(directory)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


class VideoParsingTests(unittest.TestCase):
    def test_native_sources_links_and_embeds(self):
        html = '<video src="/advert.mp4"></video>' + post('''
            <video poster="/poster.jpg"><source src="/clip.mp4"><source src="/clip.webm"></video>
            <video src="blob:123" data-src="//cdn.example/second.webm"></video>
            <a href="/attachments/film-mp4.42/">attachment</a>
            <a href="https://turbo.cr/d/abcd">video</a>
            <iframe data-src="https://turbo.cr/embed/another"></iframe>
            <a href="/playlist.m3u8?token=123">stream</a>
            <a href="https://example.com/article">unrelated article</a>
        ''')
        media, _ = parse_media_page(html, URL)
        self.assertEqual([(m.kind, m.url) for m in media], [
            ("video", "https://simpcity.cr/clip.mp4"),
            ("video", "https://cdn.example/second.webm"),
            ("video", "https://simpcity.cr/attachments/film-mp4.42/"),
            ("embed", "https://turbo.cr/d/abcd"),
            ("embed", "https://turbo.cr/embed/another"),
            ("video", "https://simpcity.cr/playlist.m3u8?token=123"),
        ])

    def test_video_attachment_is_not_also_an_image(self):
        media, _ = parse_media_page(post('<video src="/attachments/clip.42/"></video><a href="/attachments/clip.42/">file</a>'), URL)
        self.assertEqual([(m.kind, m.url) for m in media], [("video", "https://simpcity.cr/attachments/clip.42/")])

    def test_turbo_routes_share_identity(self):
        for path in ("d", "v", "embed"):
            self.assertEqual(turbo_id(f"https://turbo.cr/{path}/abcd?x=1"), "abcd")
            self.assertEqual(video_identity(f"https://turbo.cr/{path}/abcd"), "https://turbo.cr/embed/abcd")
        self.assertIsNone(turbo_id("https://turbo.cr.evil.example/d/abcd"))

    def test_media_filter_and_cross_route_duplicates(self):
        client = Mock()
        client.fetch_page.return_value = (post('<img src="/a.jpg"><a href="https://turbo.cr/d/abcd">one</a><iframe src="https://turbo.cr/embed/abcd"></iframe>'), URL)
        client.save_video.return_value = True
        with tempfile.TemporaryDirectory() as directory:
            result = download_threads(client, [URL], directory, media_types=("video",), log=lambda _: None)
        self.assertEqual((result.images, result.videos, result.saved, result.skipped), (0, 1, 1, 1))
        client.save_image.assert_not_called()
        self.assertEqual(client.save_video.call_count, 1)

    def test_video_failure_does_not_prevent_next_file(self):
        client = Mock()
        client.fetch_page.return_value = (post('<video src="/one.mp4"></video><video src="/two.mp4"></video>'), URL)
        client.save_video.side_effect = [ValueError("Unavailable"), True]
        with tempfile.TemporaryDirectory() as directory:
            result = download_threads(client, [URL], directory, log=lambda _: None)
        self.assertEqual((result.videos, result.errors), (1, 1))

    def test_signatures_reject_error_pages_and_images(self):
        self.assertEqual(video_extension(b"\x00\x00\x00\x20ftypisom"), ".mp4")
        self.assertEqual(video_extension(b"\x1a\x45\xdf\xa3....webm"), ".webm")
        for content in (b"<html>Log in</html>", b"\x89PNG\r\n", b"\x00\x00\x00\x20ftypavif"):
            with self.assertRaises(ValueError):
                video_extension(content)


class VideoDownloadTests(unittest.TestCase):
    def response(self, content=None, payload=None):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {}
        response.iter_content.return_value = content or []
        response.json.return_value = payload
        return response

    def test_turbo_signing_and_domain_scoped_cookies(self):
        with ThreadClient({"cookie_header": "forum=secret"}) as client:
            responses = [self.response(), self.response(payload={"success": True, "url": "https://cdn.example/video.mp4?signature=temporary"})]
            with patch.object(client.session, "get", side_effect=responses) as get:
                resolved, referer = client.video_downloader.resolve_turbo("https://turbo.cr/d/abcd")
            self.assertEqual(resolved, "https://cdn.example/video.mp4?signature=temporary")
            self.assertEqual(referer, "https://turbo.cr/embed/abcd")
            self.assertEqual(get.call_args.kwargs["params"], {"v": "abcd"})
            self.assertNotIn("Cookie", get.call_args.kwargs["headers"])

    def test_cancel_removes_partial_video_and_does_not_mark_complete(self):
        cancelled = threading.Event()

        def chunks():
            yield b"\x00\x00\x00\x20ftypisom" + b"x" * 8192
            cancelled.set()
            yield b"remaining data"

        with tempfile.TemporaryDirectory() as directory, ThreadClient({}) as client:
            response = self.response()
            response.iter_content.return_value = chunks()
            with patch.object(client.session, "get", return_value=response), self.assertRaises(InterruptedError):
                client.save_video("https://cdn.example/video.mp4", URL, directory, cancelled.is_set)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_error_page_is_not_saved_as_mp4(self):
        with tempfile.TemporaryDirectory() as directory, ThreadClient({}) as client:
            with patch.object(client.session, "get", return_value=self.response([b"<html>Denied</html>"])):
                with self.assertRaises(ValueError):
                    client.save_video("https://cdn.example/video.mp4", URL, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_changed_or_missing_file_is_downloaded_again(self):
        content = b"\x00\x00\x00\x20ftypisom" + b"x" * 8192
        with tempfile.TemporaryDirectory() as directory, ThreadClient({}) as client:
            with patch.object(client.session, "get", side_effect=lambda *args, **kwargs: self.response([content])) as get:
                self.assertTrue(client.save_video("https://cdn.example/video.mp4", URL, directory))
                self.assertFalse(client.save_video("https://cdn.example/video.mp4", URL, directory))
                self.assertEqual(get.call_count, 1)
                next(Path(directory).glob("*.mp4")).write_bytes(b"truncated")
                self.assertTrue(client.save_video("https://cdn.example/video.mp4", URL, directory))
                self.assertEqual(next(Path(directory).glob("*.mp4")).read_bytes(), content)
                next(Path(directory).glob("*.mp4")).unlink()
                self.assertTrue(client.save_video("https://cdn.example/video.mp4", URL, directory))
                self.assertEqual(get.call_count, 3)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is needed to generate a test video")
    def test_real_direct_embed_and_hls_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "clip.mp4")], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(root / "clip.mp4"), "-c", "copy", "-hls_time", "1", "-hls_list_size", "0", str(root / "clip.m3u8")], check=True)
            (root / "player.html").write_text('<html><head><title>Test video</title></head><body><video controls src="clip.mp4"></video></body></html>')
            with server_for(root) as base, ThreadClient({}, log=lambda _: None) as client:
                for name, embedded in (("clip.mp4", False), ("player.html", True), ("clip.m3u8", False)):
                    with self.subTest(name=name):
                        output = root / name.replace(".", "_")
                        self.assertTrue(client.save_video(f"{base}/{name}", URL, output, embedded=embedded))
                        video = next(output.glob("*.mp4"))
                        result = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(video)], text=True)
                        self.assertEqual(result.strip(), "h264")


if __name__ == "__main__":
    unittest.main()
