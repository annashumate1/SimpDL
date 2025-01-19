# SimpDL

A Python application built with [ttkbootstrap](https://pypi.org/project/ttkbootstrap) and Selenium to **download images** from [SimpCity](https://simpcity.su). The tool supports:

- **Config editing** for credentials and output directory.
- **URL management** (change/add/remove links).
- **Automated login** to SimpCity using Selenium.
- **Downloading** images (in the background, no GUI freeze).
- **Generating** multiple SimpCity links based on a base URL and page count.

This README walks you through **requirements**, **installation**, and **usage** instructions.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Usage](#usage)
  - [1. Configure Application](#1-configure-application)
  - [2. Manage URLs](#2-manage-urls)
  - [3. Generate Links](#3-generate-links)
  - [4. Download Images](#4-download-images)
- [Running the Program](#running-the-program)
- [Troubleshooting](#troubleshooting)

---

## Requirements

The project depends on the following Python packages:

```txt
requests
selenium
Pillow
ttkbootstrap
```

These can be installed via:

```bash
pip install -r requirements.txt
```

> **Note**: You must also have **Chrome** (and the appropriate [ChromeDriver](https://chromedriver.chromium.org/downloads)) installed. On most systems, Selenium can detect your existing Chrome and match driver versions automatically.



## Installation

1. **Clone** this repository:

   ```bash
   git clone https://github.com/annashumate1/SimpDL
   cd SimpDL
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Virtual Environment**:\
   If you prefer, create and activate a [virtual environment](https://docs.python.org/3/tutorial/venv.html), then install dependencies.

4. **Check config folder**:

   - Ensure you have a `config/` folder with:
     - `config.json` (for login credentials, output directory, etc.)
     - `urls.txt` (list of SimpCity links)

---

## Project Structure

```bash
SimpDL/
├─ assets/
│  └─ anna.jpg         # icon (change if you want but keep if you love Anna :) )
├─ config/
│  ├─ config.json      # stores username/password/output_directory
│  └─ urls.txt         # stores links
├─ main.py             # main GUI entry point
├─ config_utils.py     # frames for editing config & URL list
├─ downloader.py       # download frame & logic (multithreaded)
├─ image_utils.py      # helper functions for validating images
├─ link_utils.py       # link generation & frames
├─ login_utils.py      # simpcity login function
├─ requirements.txt    # required packages
└─ README.md           # this file
```

---

## Usage

Once installed, you can run the application and **use the GUI** to edit config, manage URLs, generate links, and download images.

### 1. Configure Application

- Click **“Modify Config”** in the sidebar.
- You’ll see all keys from `config.json`, such as `username`, `password`, `output_directory`.
- Edit them as needed, then **Save**.
- **username** / **password** should match your SimpCity account.
- **output\_directory** is where downloaded images will go
> **Note**: The images will go in a folder in the output directory automatically created by the program.

### 2. Manage URLs

- Click **“Change URL File”** in the sidebar.
- A list of URLs from `urls.txt` is displayed.
- **Add New URL** at the bottom by typing into the entry and pressing **Enter** or clicking **Add**.
- **Delete Link** next to any entry to remove it from the file.

### 3. Generate Links

- Click **“Generate Links”** in the sidebar.
- Enter the **Base Link** (e.g., `https://simpcity.su/threads/nottrebeca_.180370/`) and **Number of Pages** (e.g., 5).
- The tool writes all pages (`page-1`, `page-2`, etc.) into `urls.txt` automatically.
- **Note**: You can edit these again in **Change URL File** if needed.

### 4. Download Images

- Click **“Download Images”** in the sidebar.
- **Start Download** triggers a multithreaded process:
  1. **Logs in** to SimpCity using credentials in `config.json`.
  2. Iterates over each URL in `urls.txt`.
  3. Scrapes and downloads valid images to your `output_directory`.
- During download, you’ll see a **progress bar** and **status**.
- **Log messages** appear in the text box.
- You can switch to other pages in the sidebar while it downloads (the GUI won’t freeze).
> **Note**: Don't be alarmed if the program skips over files marked as "invalid" these files are not the images you are looking for (e.g profile photos, banners etc.) 

---

## Running the Program

```bash
cd SimpDL
python main.py
```

You should see the **SimpDL** window open:

1. **Sidebar** on the left with navigation buttons.
2. **Home** page (default) with a welcome message.
3. Other pages as described above.

---

## Troubleshooting

- **Credentials**: If login fails, confirm your `username` and `password` in `config/config.json` are correct.
- **ChromeDriver**: If Selenium fails to launch Chrome, check that your **Chrome** version matches your **ChromeDriver** version.
- **Images Not Downloading**:
  - Ensure you have valid links in `urls.txt`.
- **Tkinter Issues**:
  - **Windows**: Tkinter is included by default with Python. If you encounter issues, ensure you installed Python with the **Add Python to PATH** option.
  - **Linux**: Install via `sudo pacman -S tk` (Arch) or `sudo apt-get install python3-tk` (Ubuntu).
  - **macOS**: Ensure you have XQuartz or the correct Tcl/Tk environment.

---


**Enjoy using SimpDL!** If you have any issues or suggestions, feel free[ to ](https://github.com/annashumate1/SimpDL/issues)[open an issue](https://github.com/annashumate1/SimpDL/issues) or reach out on [Telegram:](https://t.me/annashumatelover)

