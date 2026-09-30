"""GUI workflow tests. Skipped automatically on machines without a display."""

import json
import gc
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from app_ui import DownloadApp, configure_style

URL = "https://simpcity.cr/threads/example.123/"


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
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
            self.assertEqual(str(self.app.start_button["state"]), "disabled")
            self.pump_until(lambda: not self.app.running)
        self.assertEqual(self.app.status.get(), "Finished")
        self.assertIn("1 images and 1 videos saved", self.app.summary.get())
        self.assertEqual(str(self.app.start_button["state"]), "normal")
        self.assertEqual(str(self.app.media_menu["state"]), "readonly")
        self.assertEqual(json.loads(self.config.read_text())["retained_setting"], "unchanged")

    def test_invalid_url_shows_inline_error(self):
        self.app.urls.delete("1.0", "end")
        self.app.urls.insert("1.0", "invalid")
        with patch("app_ui.ThreadClient") as client:
            self.app.start()
            client.assert_not_called()
        self.assertFalse(self.app.running)
        self.assertEqual(self.app.status.get(), "Could not start")
        self.assertEqual(str(self.app.start_button["state"]), "normal")

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

    def test_browser_login_does_not_require_valid_cookie_file(self):
        self.app.cookie_path.write_text("invalid json")
        self.app.access.set("Browser login")
        with patch("app_ui.ThreadClient", return_value=self.client("text")) as factory:
            self.app.start()
            self.pump_until(lambda: not self.app.running)
            self.assertEqual(factory.call_args.args[0], {})

    def test_log_opens_and_updates(self):
        self.app._append_log("First message")
        self.app.show_log()
        self.app._append_log("Second message")
        self.assertIn("Second message", self.app.log_text.get("1.0", "end"))
        self.assertEqual(str(self.app.log_text["state"]), "disabled")


if __name__ == "__main__":
    unittest.main()
