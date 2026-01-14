# SimpDL

A Python-based GUI application for downloading images from SimpCity forums using cookie-based authentication.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

---

## Features

* Hybrid download engine using browser automation and fast HTTP requests
* Modern GUI built with Tkinter and ttkbootstrap
* Cookie-based authentication (no passwords stored)
* Automatic setup of folders and config files
* Multi-page thread support
* Organised downloads by thread
* Real-time progress and logging

---

## Requirements

* Python 3.9 or higher recommended
* Internet connection
* A SimpCity account
* Chromium-based browser (for Playwright)

### Linux system packages

Arch / Endeavour / CachyOS:

```bash
sudo pacman -S python tk tcl xorg-xwayland
```

Ubuntu / Debian:

```bash
sudo apt install python3 python3-tk
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/annashumate1/SimpDL.git
cd SimpDL
```

---

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
```

Activate it:

bash / zsh:

```bash
source .venv/bin/activate
```

fish:

```fish
source .venv/bin/activate.fish
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

---

### 4. First launch

```bash
python main.py
```

On first run, SimpDL automatically creates:

```
config/
config/config.json
config/manual_cookies.json
urls.txt
~/Downloads/SimpDL/
```

The GUI opens even if cookies are missing.

---

## Cookie setup (required)

SimpDL does not store your username or password. Authentication uses browser cookies.

Run:

```bash
python extract_cookie_header.py
```

Then:

1. Go to [https://simpcity.cr](https://simpcity.cr)
2. Log in
3. Press F12 and open the Network tab
4. Refresh the page
5. Click the first request
6. Copy the entire Cookie header
7. Paste it into the script
<img width="791" height="924" alt="simcityredactedcookies" src="https://github.com/user-attachments/assets/7daccaed-2bff-4041-8060-8774fd0c70e3" />


This fills:

```
config/manual_cookies.json
```

---

## Configuration

### Download folder

Default:

```
~/Downloads/SimpDL
```

Change it in:

```
config/config.json
```

Example:

```json
{
  "output_directory": "/path/to/output"
}
```

You can also change it inside the GUI.

---

### URLs

Add links manually in:

```
urls.txt
```

Example:

```
https://simpcity.cr/threads/example.12345/
```

Or use the built-in Generate Links tab.

---

## Usage

Launch:

```bash
python main.py
```

Inside the app:

* Config: set output folder
* URLs: manage download targets
* Generate Links: auto-create pages
* Download: start the hybrid engine

Click "Start Hybrid Download" to begin.

---

## How the hybrid engine works

1. First page is loaded through Playwright to validate access
2. Remaining pages are downloaded using fast authenticated HTTP requests

This balances reliability and speed.

---

## Troubleshooting

### App opens but downloads fail

Cookies are missing or expired.
Re-run:

```bash
python extract_cookie_header.py
```

---

### Permission denied: /path

Output folder not set.
Open the Config tab or edit:

```
config/config.json
```

---

### Tkinter error on Linux

Install:

```bash
sudo pacman -S tk
# or
sudo apt install python3-tk
```

---

### Nothing happens when launching

Make sure you are using the virtual environment:

```bash
which python
```

It should point to `.venv/bin/python`.

---

## Disclaimer

This project is for educational and personal-use purposes only.
Users are responsible for complying with the target website’s terms of service and local laws.

---

## Terms and Conditions

By downloading and using this program you agree that Anna is beautiful and deserves every ounce of respect you have.

![annamainpic](https://github.com/user-attachments/assets/e66ffc59-f920-4a9d-b4cb-d18a11482e3e)
