"""GUI workflow tests. Skipped automatically on machines without a display."""

import json
import gc
from pathlib import Path
import tempfile
import time
import tkinter as tk

import customtkinter as ctk
import unittest
from unittest.mock import Mock, patch

from app_ui import DownloadApp, configure_style, transfer_label

URL = "https://simpcity.cr/threads/example.123/"


class TransferLabelTests(unittest.TestCase):
    def test_speed_and_time_left(self):
        self.assertEqual(transfer_label(10 * 2**20, 50 * 2**20), "10.0 MB of 50.0 MB")
        self.assertEqual(transfer_label(10 * 2**20, 50 * 2**20, 4 * 2**20), "10.0 MB of 50.0 MB · 4.0 MB/s · 0:10 left")
        self.assertEqual(transfer_label(3 * 2**20, 0, 2**20), "3.0 MB downloaded · 1.0 MB/s")


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = ctk.CTk()
        except tk.TclError as error:
            self.skipTest(f"No graphical display: {error}")
        self.root.withdraw()
        configure_style(self.root)
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.config = self.directory / "config.json"
        self.urls = self.directory / "urls.txt"
        self.config.write_text(json.dumps({"output_directory": str(self.directory / "downloads"), "retained_setting": "unchanged"}))
        self.urls.write_text(URL)
        self.app = DownloadApp(self.root, self.config, self.urls)
        self.app.pack(fill="both", expand=True)

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()
        self.app = self.root = None
        gc.collect()  # Tcl objects must be finalized on the GUI thread.

    def pump_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("GUI did not reach the expected state")

    def client(self, html):
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.fetch_page.return_value = (f'<div class="message-body">{html}</div>', URL)
        client.save_image.return_value = client.save_video.return_value = True
        return client

    def test_download_workflow_restores_controls_and_preserves_settings(self):
        client = self.client('<img src="/image.png"><video src="/video.mp4"></video>')
        with patch("app_ui.ThreadClient", return_value=client):
            self.app.start()
            self.assertTrue(self.app.running)
            self.assertEqual(self.app.start_button.cget("state"), "disabled")
            self.pump_until(lambda: not self.app.running)
        self.assertEqual(self.app.status.get(), "Finished")
        self.assertIn("1 images and 1 videos saved", self.app.summary.get())
        self.assertEqual(self.app.start_button.cget("state"), "normal")
        self.assertEqual(self.app.media_menu.cget("state"), "normal")
        self.assertEqual((self.app.counts["Images"].get(), self.app.counts["Videos"].get()), ("1", "1"))
        self.assertEqual(json.loads(self.config.read_text())["retained_setting"], "unchanged")

    def test_invalid_url_shows_inline_error(self):
        self.app.urls.delete("1.0", "end")
        self.app.urls.insert("1.0", "invalid")
        with patch("app_ui.ThreadClient") as client:
            self.app.start()
            client.assert_not_called()
        self.assertFalse(self.app.running)
        self.assertEqual(self.app.status.get(), "Could not start")
        self.assertEqual(self.app.start_button.cget("state"), "normal")

    def test_stop_video_download(self):
        client = self.client('<video src="/video.mp4"></video>')

        def save(url, referer, directory, cancelled, **kwargs):
            while not cancelled():
                time.sleep(0.01)
            raise InterruptedError("Cancelled")

        client.save_video.side_effect = save
        with patch("app_ui.ThreadClient", return_value=client):
            self.app.start()
            self.pump_until(lambda: client.save_video.called)
            self.app.stop()
            self.pump_until(lambda: not self.app.running)
        self.assertEqual(self.app.status.get(), "Stopped")
        self.assertIn("0 errors", self.app.summary.get())

    def test_skip_button_moves_on_to_next_file(self):
        client = self.client('<video src="/stuck.mp4"></video><video src="/next.mp4"></video>')

        def save(url, referer, directory, cancelled, **kwargs):
            if url.endswith("stuck.mp4"):
                while not cancelled():
                    time.sleep(0.01)
                raise InterruptedError("Cancelled")
            return True

        client.save_video.side_effect = save
        with patch("app_ui.ThreadClient", return_value=client):
            self.app.start()
            self.assertEqual(self.app.skip_button.cget("state"), "normal")
            self.pump_until(lambda: client.save_video.called)
            self.app.skip()
            self.pump_until(lambda: not self.app.running)
        self.assertEqual(self.app.status.get(), "Finished")
        self.assertIn("1 videos saved · 1 skipped · 0 errors", self.app.summary.get())
        self.assertEqual(self.app.skip_button.cget("state"), "disabled")

    def test_browser_login_does_not_require_valid_cookie_file(self):
        self.app.cookie_path.write_text("invalid json")
        self.app.access.set("Browser login")
        with patch("app_ui.ThreadClient", return_value=self.client("text")) as factory:
            self.app.start()
            self.pump_until(lambda: not self.app.running)
            self.assertEqual(factory.call_args.args[0], {})

    def test_log_updates_and_stays_read_only(self):
        self.app._append_log("First message")
        self.app._append_log("Second message")
        self.assertIn("Second message", self.app.log_text.get("1.0", "end"))
        self.assertNotIn("will appear here", self.app.log_text.get("1.0", "end"))
        self.assertEqual(self.app.log_text.cget("state"), "disabled")

    def test_media_toggle_saves_engine_choice(self):
        self.app.media_menu.set("Videos")
        self.app.media_menu._command("Videos")
        self.app._persist()
        self.assertEqual(json.loads(self.config.read_text())["media_choice"], "Videos only")

    def test_paste_adds_links_once_and_counts_them(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(f"{URL}\nnot a link\nhttps://simpcity.cr/threads/other.9/")
        self.app.paste()
        self.assertEqual(self.app._url_lines(), [URL, "https://simpcity.cr/threads/other.9/"])
        self.assertEqual(self.app.thread_count.cget("text"), "2 links")

    def test_resize_repaint_runs(self):
        self.app._schedule_repaint(Mock(widget=self.root))
        self.pump_until(lambda: self.app._repaint_id is None)


if __name__ == "__main__":
    unittest.main()
