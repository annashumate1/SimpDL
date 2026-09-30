from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.prepare_release import SOURCE_FILES, prepare_release


class ReleaseTests(unittest.TestCase):
    def make_source(self, root):
        for name in SOURCE_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test source\n", encoding="utf-8")

    def test_only_allowlisted_source_and_no_archive_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "working"
            self.make_source(source)
            for name in (".git/config", "config/manual_cookies.json", "config/urls.txt", ".venv/pyvenv.cfg", "assets/portrait.png", "tests/private.txt"):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private fixture data")
            folder, archive = prepare_release(source, root / "release")
            self.assertEqual({str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_file()}, set(SOURCE_FILES))
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), {"SimpDL/" + name for name in SOURCE_FILES})
                for item in bundle.infolist():
                    self.assertEqual(item.date_time, (2020, 1, 1, 0, 0, 0))
                    self.assertEqual(item.extra, b"")
                    self.assertEqual(item.comment, b"")
                    self.assertNotIn(b"private fixture data", bundle.read(item))
            self.assertTrue((source / "config/manual_cookies.json").exists())

    def test_existing_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root / "working")
            (root / "release").mkdir()
            with self.assertRaises(FileExistsError):
                prepare_release(root / "working", root / "release")

    def test_symlink_cannot_smuggle_in_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "working"
            self.make_source(source)
            secret = root / "private.txt"
            secret.write_text("private fixture data")
            (source / "main.py").unlink()
            try:
                (source / "main.py").symlink_to(secret)
            except OSError:
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ValueError):
                prepare_release(source, root / "release")


if __name__ == "__main__":
    unittest.main()
