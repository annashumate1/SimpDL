"""Build a source-only upload folder and ZIP without local state or Git history."""

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile


SOURCE_FILES = (
    ".gitignore",
    "LICENSE",
    "README.md",
    "assets/anna.png",
    "requirements.txt",
    "main.py",
    "app_ui.py",
    "config_utils.py",
    "download_engine.py",
    "site_utils.py",
    "video_utils.py",
    "extract_cookie_header.py",
    "tests/test_downloader.py",
    "tests/test_video.py",
    "tests/test_ui.py",
    "tests/test_release.py",
    "tools/prepare_release.py",
)


def prepare_release(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    archive = destination.parent / f"{destination.name}.zip"
    if destination == source or source.is_relative_to(destination):
        raise ValueError("The release must be separate from the source directory")
    if destination.exists() or archive.exists():
        raise FileExistsError("Release output already exists; choose another --output directory")
    for name in SOURCE_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents if p != source.parent):
            raise ValueError(f"Missing or unsafe source file: {name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".simpdl-release-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "source"
        staging.mkdir()
        staged_archive = Path(temporary) / "release.zip"
        with zipfile.ZipFile(staged_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in SOURCE_FILES:
                data = (source / name).read_bytes()
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o644)
                # Fixed timestamps and generic permissions avoid local file metadata.
                entry = zipfile.ZipInfo(f"SimpDL/{name}", date_time=(2020, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, data)
        shutil.move(str(staging), str(destination))
        shutil.move(str(staged_archive), str(archive))
    return destination, archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent.parent
    parser.add_argument("--output", type=Path, default=root.parent / "SimpDL-github", help="New output directory (must not exist)")
    args = parser.parse_args()
    try:
        destination, archive = prepare_release(root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Could not prepare release: {error}\n")
    print(f"Source folder: {destination}")
    print(f"ZIP archive: {archive}")
    print(f"Included {len(SOURCE_FILES)} source files. Local data and Git history were excluded.")


if __name__ == "__main__":
    main()
