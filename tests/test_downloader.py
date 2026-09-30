"""Offline regressions: synthetic forum HTML and generated non-content images."""

from io import BytesIO
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from PIL import Image
import requests

from download_engine import ThreadClient, download_threads
from site_utils import extract_images, generate_links, next_page, parse_cookies, parse_page, thread_url

URL = "https://simpcity.cr/threads/example.123/"


def post(body):
    return f'<article class="message"><div class="message-body"><div class="bbWrapper">{body}</div></div></article>'


class ParserTests(unittest.TestCase):
    def test_normalizes_pages_fragments_and_queries(self):
        self.assertEqual(generate_links(URL + "page-9?foo=bar#post-10", 2), [URL, URL + "page-2"])
        self.assertEqual(thread_url(URL + "?page=3#post-4"), URL + "page-3")
        self.assertEqual(thread_url(URL + "unread"), URL)

    def test_query_routes(self):
        url = "https://simpcity.cr/index.php?threads/example.123/page-3&_xfRequestUri=x"
        self.assertEqual(generate_links(url, 2), [
            "https://simpcity.cr/index.php?threads/example.123/",
            "https://simpcity.cr/index.php?threads/example.123/page-2",
        ])

    def test_rejects_non_threads(self):
        for url in ("https://evil.example/threads/a.123/", "https://simpcity.cr/forums/a.123/", URL + "page-0"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                thread_url(url)

    def test_cookie_formats_and_equals_in_values(self):
        self.assertEqual(parse_cookies({"cookie_header": "Cookie: custom_user=a=b; custom_session=c"}), {"custom_user": "a=b", "custom_session": "c"})
        self.assertEqual(parse_cookies({"cookie_header": "", "parsed_cookies": {"xf_user": "1"}}), {"xf_user": "1"})
        self.assertEqual(parse_cookies({"xf_user": "1", "notes": "ignored"}), {"xf_user": "1"})

    def test_header_overrides_stale_parsed_values(self):
        self.assertEqual(parse_cookies({"cookie_header": "xf_user=new", "parsed_cookies": {"xf_user": "old"}})["xf_user"], "new")

    def test_post_images_only_and_lazy_precedence(self):
        html = '<img src="/logo.png">' + post('''
            <img src="/placeholder.gif" data-src="//cdn.example/full.webp">
            <img src="/smile.png" class="smilie">
            <img src="data:image/gif;base64,AAAA" data-original="/image.png">
            <img src="/low.jpg" srcset="/medium.jpg 400w, /large.jpg 1200w">
        ''')
        self.assertEqual(extract_images(BeautifulSoup(html, "html.parser"), URL), [
            "https://cdn.example/full.webp", "https://simpcity.cr/image.png", "https://simpcity.cr/large.jpg",
        ])

    def test_full_size_attachments_and_deduplication(self):
        html = post('''<a href="/attachments/photo-jpg.456/"><img src="/thumb.jpg"></a>
            <a href="https://cdn.example/full.png"><img src="/thumb2.jpg"></a>
            <a href="https://cdn.example/full.png">again</a>''')
        self.assertEqual(extract_images(BeautifulSoup(html, "html.parser"), URL), [
            "https://simpcity.cr/attachments/photo-jpg.456/", "https://cdn.example/full.png",
        ])

    def test_picture_sources_and_attachment_section(self):
        html = post('<picture><source srcset="/large.webp 2x"><img src="/fallback.jpg"></picture>')
        html += '<div class="message-attachments"><a href="/attachments/image-png.456/">Image</a></div>'
        self.assertEqual(extract_images(BeautifulSoup(html, "html.parser"), URL), [
            "https://simpcity.cr/large.webp", "https://simpcity.cr/attachments/image-png.456/",
        ])

    def test_next_link_must_be_same_thread(self):
        soup = BeautifulSoup('<a rel="next" href="/threads/other.999/page-2">Next</a>', "html.parser")
        self.assertIsNone(next_page(soup, URL))
        soup = BeautifulSoup('<a class="pageNav-jump--next" href="/threads/example.123/page-2">Next</a>', "html.parser")
        self.assertEqual(next_page(soup, URL), URL + "page-2")

    def test_login_challenge_and_missing_markup_fail(self):
        for html, status in [('<title>Just a moment...</title>', 200), ('<input name="password">', 200), ('<h1>Forbidden</h1>', 403), ('<img src="/logo.jpg">', 200)]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, URL, status)

    def test_normal_post_mentioning_challenge_is_not_blocked(self):
        self.assertEqual(parse_page(post("I have a challenge with Cloudflare"), URL), ([], None))


class DownloadTests(unittest.TestCase):
    def make_response(self, content):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [content]
        return response

    def image_bytes(self, size=(300, 300), fmt="PNG"):
        buffer = BytesIO()
        Image.new("RGB", size, "blue").save(buffer, format=fmt)
        return buffer.getvalue()

    def test_single_fetch_format_and_dedup(self):
        with tempfile.TemporaryDirectory() as directory, ThreadClient({}) as client:
            with patch.object(client.session, "get", return_value=self.make_response(self.image_bytes())) as get:
                self.assertTrue(client.save_image("https://cdn.example/file", URL, directory))
                self.assertEqual(get.call_count, 1)
                self.assertEqual(next(Path(directory).iterdir()).suffix, ".png")
            with patch.object(client.session, "get", return_value=self.make_response(self.image_bytes())):
                self.assertFalse(client.save_image("https://cdn.example/file", URL, directory))
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_real_http_image_download_through_thread_runner(self):
        content = self.image_bytes()
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(dict(self.headers))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            image_url = f"http://127.0.0.1:{server.server_port}/image"
            with tempfile.TemporaryDirectory() as directory, ThreadClient({"cookie_header": "user=secret"}) as client:
                with patch.object(client, "fetch_page", return_value=(post(f'<img src="{image_url}">'), URL)):
                    result = download_threads(client, [URL], directory, log=lambda _: None, delay=0)
                self.assertEqual((result.saved, result.errors), (1, 0))
                saved = list(Path(directory).glob("example.123/*.png"))
                self.assertEqual(saved[0].read_bytes(), content)
            self.assertEqual(len(received), 1)
            self.assertNotIn("Cookie", received[0])
            self.assertEqual(received[0]["Referer"], URL)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_rejects_html_and_small_images(self):
        with tempfile.TemporaryDirectory() as directory, ThreadClient({}) as client:
            with patch.object(client.session, "get", return_value=self.make_response(b"<html>Login</html>")):
                with self.assertRaises(Exception):
                    client.save_image("https://cdn.example/file", URL, directory)
            with patch.object(client.session, "get", return_value=self.make_response(self.image_bytes((10, 10)))):
                self.assertFalse(client.save_image("https://cdn.example/file", URL, directory))
            self.assertFalse(list(Path(directory).iterdir()))

    def test_cookies_never_sent_to_external_image_hosts(self):
        with ThreadClient({"cookie_header": "custom_user=secret"}) as client:
            own = client.session.prepare_request(requests.Request("GET", URL))
            external = client.session.prepare_request(requests.Request("GET", "https://cdn.example/a.png"))
            self.assertIn("custom_user=secret", own.headers["Cookie"])
            self.assertNotIn("Cookie", external.headers)
            self.assertNotIn("Cookie", client.session.headers)

    def test_http_failure_falls_back_for_any_page(self):
        with ThreadClient({}, log=lambda _: None) as client:
            response = self.make_response(b"")
            response.text, response.url, response.status_code = "Forbidden", URL + "page-12", 403
            with patch.object(client.session, "get", return_value=response), patch.object(client, "_browser_page", return_value=(post("ok"), URL + "page-12")) as browser:
                client.fetch_page(URL + "page-12")
                browser.assert_called_once()

    def test_auto_pagination_and_loop_detection(self):
        client = Mock()
        client.fetch_page.side_effect = [
            (post('<img src="https://cdn.example/one.png">') + f'<a rel="next" href="{URL}page-2">Next</a>', URL),
            (post('<img src="https://cdn.example/one.png">') + f'<a rel="next" href="{URL}">Next</a>', URL + "page-2"),
        ]
        client.save_image.return_value = True
        with tempfile.TemporaryDirectory() as directory:
            result = download_threads(client, [URL], directory, log=lambda _: None, delay=0)
        self.assertEqual((result.pages, result.saved, result.skipped, result.errors), (2, 1, 1, 0))
        self.assertEqual(client.save_image.call_count, 1)

    def test_explicit_pages_do_not_expand_range(self):
        client = Mock()
        client.fetch_page.return_value = (post("text") + f'<a rel="next" href="{URL}page-3">Next</a>', URL + "page-2")
        with tempfile.TemporaryDirectory() as directory:
            result = download_threads(client, [URL + "page-2"], directory, log=lambda _: None, delay=0)
        self.assertEqual(result.pages, 1)
        self.assertEqual(client.fetch_page.call_count, 1)

    def test_threads_get_separate_folders(self):
        client = Mock()
        second = "https://simpcity.cr/threads/second.456/"
        client.fetch_page.side_effect = [(post('<img src="/a.png">'), URL), (post('<img src="/a.png">'), second)]
        with tempfile.TemporaryDirectory() as directory:
            download_threads(client, [URL, second], directory, log=lambda _: None, delay=0)
            self.assertEqual({p.name for p in Path(directory).iterdir()}, {"example.123", "second.456"})

    def test_failures_and_cancellation_are_reported(self):
        client = Mock()
        client.fetch_page.side_effect = ValueError("Blocked")
        with tempfile.TemporaryDirectory() as directory:
            result = download_threads(client, [URL], directory, log=lambda _: None, delay=0)
            self.assertEqual((result.pages, result.errors), (0, 1))
            client.reset_mock()
            result = download_threads(client, [URL], directory, cancelled=lambda: True)
            self.assertTrue(result.cancelled)
            client.fetch_page.assert_not_called()


if __name__ == "__main__":
    unittest.main()
