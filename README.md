# SimpDL

A desktop application for downloading images and videos from SimpCity threads.

Paste thread links, choose a folder, and start downloading. The single-window interface includes media selection, page ranges, browser login, progress, and a download log.

## Features

- Download images, videos, or both.
- Follow thread pagination or select a page range.
- Extract post images, lazy-loaded images, and full-size attachments.
- Download direct videos and resolve Turbo player links.
- Handle supported external players and streams through [yt-dlp](https://github.com/yt-dlp/yt-dlp).
- Organize files into separate thread folders and skip completed downloads.
- Stop a running download and inspect failures in the log.

## Requirements

- Python 3.10 or newer
- Tkinter
- Playwright Chromium
- An internet connection and access to the threads you want to download
- ffmpeg, recommended for streams and videos with separate audio tracks

Direct video downloads, including Turbo MP4 files, do not require ffmpeg.

## Installation

Download the repository and open a terminal in its directory.

### 1. Install system packages

On Ubuntu or Debian:

```bash
sudo apt install python3-venv python3-tk ffmpeg
```

On Arch Linux and derivatives:

```bash
sudo pacman -S python tk ffmpeg
```

On Windows or macOS, install Python with Tkinter support. If you install ffmpeg, make sure its executable is available on your PATH.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Or in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies and launch

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

On Linux, if Playwright reports missing browser libraries, run `python -m playwright install --with-deps chromium`.

## Usage

1. Paste one thread URL per line into **Thread links**.
2. Choose the **Save to** folder.
3. Select **Images and videos**, **Images only**, or **Videos only**.
4. Select **Browser login** or **Saved cookies**.
5. Click **Start download**.

Use **Stop** to cancel and **View log** to inspect progress or failed links. Settings and thread links are saved when starting a download or closing the application.

### Thread pages

With **Follow next pages** enabled, a bare thread URL follows the thread's Next links:

```text
https://simpcity.cr/threads/example.123/
```

Use **Page range…** to add specific pages. If explicit page URLs such as `page-2` are listed, only the listed pages are downloaded for that thread. To download only the first page of a bare thread URL, disable **Follow next pages**.

### Authentication

**Browser login** opens a browser window where you can sign in or complete verification. The app waits up to two minutes for the thread to become accessible. This browser session lasts for the current run.

To reuse an existing browser session:

1. Sign in to SimpCity in your browser.
2. Open Developer Tools, select **Network**, and reload the thread.
3. Select the thread's request and copy its **Cookie** request header.
4. Open **Cookie settings…** in SimpDL and paste the header.
5. Optionally enter the matching **User-Agent** header, then save.

You can also run `python extract_cookie_header.py`. Cookies are stored locally; they are credentials and should not be included in issues, screenshots, or uploads.

## Supported media

| Source | Support |
| --- | --- |
| Post images and image attachments | Lazy sources, responsive images, and direct full-size links |
| Native video and direct video links | MP4, WebM, MOV, MKV, AVI, Ogg video, and MPEG containers |
| Turbo links | `/d/`, `/v/`, and `/embed/` routes |
| Supported external players, HLS, and DASH | Through yt-dlp; ffmpeg may be required |
| External albums and live streams | Not expanded |

Host support depends on the source site and yt-dlp. Deleted files, access restrictions, verification requirements, and unsupported players can prevent downloads. Failed media links appear in the log. Support for every host or thread layout is not guaranteed.

Images smaller than 256 × 256 pixels are skipped. Site navigation images and avatars are excluded.

## Download behavior

- Each thread has its own folder.
- Files use content-hash names and their actual extensions.
- Videos stream to disk instead of being held in memory.
- Partial video files are removed after cancellation or failure. Retrying starts that video again.
- Completed videos are recorded in `.simpdl-videos.json` and skipped before downloading again. Turbo's different page routes share the same record.
- Missing or size-changed video files are downloaded again. Image duplicates are checked after fetching their content.

Stopping may take until the current network request finishes or times out.

## Local files

The application creates these files on first launch:

```text
config/config.json          Download folder and preferences
config/urls.txt             Saved thread links
config/manual_cookies.json  Optional authentication cookies
```

The default download folder is `~/Downloads/SimpDL`. Local settings, cookies, browser profiles, logs, and downloads are excluded by `.gitignore`.

To create a source-only copy for sharing, run:

```bash
python tools/prepare_release.py
```

This creates `SimpDL-github/` and `SimpDL-github.zip` beside the project. It copies an explicit list of source files and excludes local configuration, media, environments, caches, and `.git` history. Upload the generated files to a new repository when a fresh history is wanted.

## Troubleshooting

**The app cannot open a thread:** Try Browser login. If the browser itself cannot access the thread, resolve that access problem first. For saved sessions, refresh the cookies and matching User-Agent.

**A video fails:** Check View log for the failed link. Update dependencies with `python -m pip install --upgrade -r requirements.txt`. Install ffmpeg if the host requires merging audio and video.

**No new files are saved:** Check the selected media type, existing downloads, and the minimum image dimensions. External album pages are not expanded.

**Tkinter is missing:** Install the Tkinter package for your Python installation.

## Development

Run the test suite from the project directory:

```bash
python -m unittest discover -s tests -v
```

Tests cover parsing, pagination, cookie isolation, media selection, duplicates, cancellation, and GUI workflows. Local HTTP integration tests generate a test video and verify direct MP4, HTML-player, and HLS downloads. They require ffmpeg and ffprobe; GUI tests skip when a graphical display is unavailable.

Tests use synthetic thread HTML and generated media. Passing tests does not guarantee compatibility with every live thread or third-party host.

## License

Distributed under the GNU General Public License, version 3. See [LICENSE](LICENSE).

## Terms and Conditions

By downloading and using this program you agree that Anna is beautiful and deserves every ounce of respect you have.

![annamainpic](https://github.com/user-attachments/assets/e66ffc59-f920-4a9d-b4cb-d18a11482e3e)
