"""A single-window interface for the thread downloader."""

from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, font, ttk

from config_utils import read_json, update_config, write_json
from download_engine import ThreadClient, download_threads
from site_utils import parse_cookies, thread_url

BACKGROUND = "#f7f7f5"
FOREGROUND = "#242424"
MUTED = "#666663"
MEDIA_CHOICES = {"Images and videos": ("image", "video"), "Images only": ("image",), "Videos only": ("video",)}


def configure_style(window):
    window.configure(background=BACKGROUND)
    style = ttk.Style(window)
    style.theme_use("clam")
    font.nametofont("TkDefaultFont").configure(size=10)
    font.nametofont("TkTextFont").configure(size=10)
    style.configure(".", background=BACKGROUND, foreground=FOREGROUND, font="TkDefaultFont")
    style.configure("TLabel", background=BACKGROUND)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
    style.configure("Section.TLabel", font=("TkDefaultFont", 10, "bold"))
    style.configure("TButton", padding=(12, 7), background="#eeeeeb", bordercolor="#d8d8d3", lightcolor="#eeeeeb", darkcolor="#eeeeeb")
    style.map("TButton", background=[("active", "#e2e2dd")], foreground=[("disabled", "#90908b")])
    style.configure("Primary.TButton", background=FOREGROUND, foreground="white", bordercolor=FOREGROUND, lightcolor=FOREGROUND, darkcolor=FOREGROUND)
    style.map("Primary.TButton", background=[("disabled", "#d6d6d1"), ("active", "#454542")], foreground=[("disabled", "#777772"), ("!disabled", "white")])
    style.configure("TEntry", fieldbackground="white", bordercolor="#c9c9c3", padding=6)
    style.configure("TCombobox", fieldbackground="white", background="#eeeeeb", bordercolor="#c9c9c3", lightcolor="white", darkcolor="white", padding=6, arrowsize=12)
    style.map("TCombobox", fieldbackground=[("readonly", "white")], selectbackground=[("readonly", "white")], selectforeground=[("readonly", FOREGROUND)])
    style.configure("TCheckbutton", padding=3)
    style.configure("Horizontal.TProgressbar", background=FOREGROUND, troughcolor="#e5e5df", bordercolor=BACKGROUND, lightcolor=FOREGROUND, darkcolor=FOREGROUND, borderwidth=0, thickness=5)
    return style


def size_text(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024


class DownloadApp(ttk.Frame):
    def __init__(self, parent, config_path, urls_file):
        super().__init__(parent, padding=(30, 20))
        self.window = self.winfo_toplevel()
        self.logo_image = self._load_logo()
        self.config_path = Path(config_path)
        self.urls_file = Path(urls_file)
        self.cookie_path = self.config_path.parent / "manual_cookies.json"
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.running = self.closing = False
        self.messages = []
        self.log_window = self.log_text = None
        self.editable = []
        config = read_json(self.config_path)
        try:
            has_cookies = bool(parse_cookies(read_json(self.cookie_path)))
        except (ValueError, OSError):
            has_cookies = False
        self.folder = tk.StringVar(value=config.get("output_directory") or str(Path.home() / "Downloads" / "SimpDL"))
        choice = config.get("media_choice", "Images and videos")
        self.media = tk.StringVar(value=choice if choice in MEDIA_CHOICES else "Images and videos")
        self.follow = tk.BooleanVar(value=config.get("follow_pagination", True))
        self.access = tk.StringVar(value=config.get("access_mode", "Saved cookies" if has_cookies else "Browser login"))
        if self.access.get() not in ("Saved cookies", "Browser login"):
            self.access.set("Browser login")
        self.status = tk.StringVar(value="Ready")
        self.summary = tk.StringVar(value="Add a thread to get started.")
        self.transfer_text = tk.StringVar()
        self._build()
        self.window.bind("<Control-Return>", lambda event: self.start())
        self._poll_id = self.after(80, self._poll)

    def _load_logo(self):
        """Load the bundled logo for both the header and native window icon."""
        logo_path = Path(__file__).resolve().parent / "assets" / "anna.png"
        try:
            self.window_logo_image = tk.PhotoImage(file=logo_path)
            self.window.iconphoto(False, self.window_logo_image)
            return self.window_logo_image.subsample(2, 2)
        except tk.TclError:
            return None

    def _build(self):
        header = ttk.Frame(self)
        header.pack(anchor="w")
        if self.logo_image is not None:
            ttk.Label(header, image=self.logo_image).pack(side="left", padx=(0, 10))
        ttk.Label(header, text="SimpDL", style="Title.TLabel").pack(side="left")
        ttk.Label(self, text="Download images and videos from threads.", style="Muted.TLabel").pack(anchor="w", pady=(4, 16))

        thread_heading = ttk.Frame(self)
        thread_heading.pack(fill="x", pady=(0, 7))
        ttk.Label(thread_heading, text="Thread links", style="Section.TLabel").pack(side="left")
        ranges = ttk.Button(thread_heading, text="Page range…", command=self.page_range)
        ranges.pack(side="right")
        self.editable.append(ranges)
        box = ttk.Frame(self)
        box.pack(fill="both", expand=True)
        self.urls = tk.Text(box, height=4, wrap="none", font="TkTextFont", undo=True, relief="flat", bd=0,
                            highlightthickness=1, highlightbackground="#c9c9c3", highlightcolor="#62625e",
                            background="white", foreground=FOREGROUND, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(box, command=self.urls.yview)
        self.urls.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.urls.pack(side="left", fill="both", expand=True)
        if self.urls_file.exists():
            self.urls.insert("1.0", self.urls_file.read_text(encoding="utf-8"))
        ttk.Label(self, text="One thread per line. Completed files are skipped.", style="Muted.TLabel").pack(anchor="w", pady=(6, 14))

        ttk.Label(self, text="Save to", style="Section.TLabel").pack(anchor="w", pady=(0, 7))
        folder_row = ttk.Frame(self)
        folder_row.pack(fill="x", pady=(0, 12))
        folder_entry = ttk.Entry(folder_row, textvariable=self.folder)
        folder_entry.pack(side="left", fill="x", expand=True)
        browse = ttk.Button(folder_row, text="Browse…", command=self.browse)
        browse.pack(side="left", padx=(8, 0))
        ttk.Button(folder_row, text="Open folder", command=self.open_folder).pack(side="left", padx=(8, 0))
        self.editable.extend([folder_entry, browse])

        options = ttk.Frame(self)
        options.pack(fill="x", pady=(0, 10))
        ttk.Label(options, text="Download", width=9).pack(side="left")
        self.media_menu = ttk.Combobox(options, textvariable=self.media, values=list(MEDIA_CHOICES), state="readonly", width=20)
        self.media_menu.pack(side="left")
        follow = ttk.Checkbutton(options, text="Follow next pages", variable=self.follow)
        follow.pack(side="left", padx=(20, 0))
        self.editable.append(follow)

        access_row = ttk.Frame(self)
        access_row.pack(fill="x")
        ttk.Label(access_row, text="Access", width=9).pack(side="left")
        self.access_menu = ttk.Combobox(access_row, textvariable=self.access, values=["Browser login", "Saved cookies"], state="readonly", width=20)
        self.access_menu.pack(side="left")
        cookies = ttk.Button(access_row, text="Cookie settings…", command=self.cookie_settings)
        cookies.pack(side="left", padx=(20, 0))
        self.editable.append(cookies)
        ttk.Label(self, text="Browser login opens a window where you can sign in.", style="Muted.TLabel").pack(anchor="w", pady=(6, 14))

        ttk.Separator(self).pack(fill="x", pady=(0, 14))
        ttk.Label(self, textvariable=self.status, style="Section.TLabel", wraplength=680).pack(anchor="w")
        ttk.Label(self, textvariable=self.summary, style="Muted.TLabel", wraplength=680).pack(anchor="w", pady=(4, 8))
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(self, textvariable=self.transfer_text, style="Muted.TLabel").pack(anchor="w", pady=(4, 8))
        actions = ttk.Frame(self)
        actions.pack(fill="x")
        ttk.Button(actions, text="View log", command=self.show_log).pack(side="left")
        self.start_button = ttk.Button(actions, text="Start download", style="Primary.TButton", command=self.start)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(actions, text="Stop", state="disabled", command=self.stop)
        self.stop_button.pack(side="right", padx=(0, 8))

    def browse(self):
        path = filedialog.askdirectory(parent=self.window, initialdir=self.folder.get(), title="Download folder")
        if path:
            self.folder.set(path)

    def open_folder(self):
        try:
            path = Path(self.folder.get()).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
            self._error(str(error))

    def _dialog(self, title):
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.configure(background=BACKGROUND)
        dialog.transient(self.window)
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        content = ttk.Frame(dialog, padding=24)
        content.pack(fill="both", expand=True)
        return dialog, content

    def page_range(self):
        dialog, body = self._dialog("Add a page range")
        ttk.Label(body, text="Thread URL", style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        entry = ttk.Entry(body, width=62)
        entry.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 16))
        entry.focus_set()
        ttk.Label(body, text="From page").grid(row=2, column=0, sticky="w")
        first = ttk.Spinbox(body, from_=1, to=100000, width=7)
        first.set(1)
        first.grid(row=2, column=1, padx=(8, 18))
        ttk.Label(body, text="To page").grid(row=2, column=2)
        last = ttk.Spinbox(body, from_=1, to=100000, width=7)
        last.set(5)
        last.grid(row=2, column=3, padx=(8, 0))
        error = ttk.Label(body, foreground="#a32d2d", wraplength=490)
        error.grid(row=3, column=0, columnspan=4, sticky="w", pady=12)

        def add():
            try:
                start, end = int(first.get()), int(last.get())
                if not 1 <= start <= end <= 100000 or end - start > 9999:
                    raise ValueError("Choose a valid range of up to 10,000 pages.")
                links = [thread_url(entry.get(), number) for number in range(start, end + 1)]
                existing = self.urls.get("1.0", "end-1c").strip()
                self.urls.delete("1.0", "end")
                self.urls.insert("1.0", "\n".join(dict.fromkeys(existing.splitlines() + links)).strip() + "\n")
                if start == end == 1:
                    self.follow.set(False)
                dialog.destroy()
            except ValueError as exc:
                error.configure(text=str(exc))

        ttk.Button(body, text="Add pages", command=add, style="Primary.TButton").grid(row=4, column=3, sticky="e")

    def cookie_settings(self):
        dialog, body = self._dialog("Cookie settings")
        ttk.Label(body, text="Use an existing browser session", style="Section.TLabel").pack(anchor="w")
        ttk.Label(body, text="After signing in to SimpCity, copy the Cookie request header\nfrom your browser's Network tab. Or use Browser login instead.", style="Muted.TLabel").pack(anchor="w", pady=(8, 18))
        ttk.Label(body, text="Cookie header").pack(anchor="w", pady=(0, 5))
        header = ttk.Entry(body, width=64, show="•")
        header.pack(fill="x")
        ttk.Label(body, text="User-Agent (optional, from the same browser)").pack(anchor="w", pady=(14, 5))
        user_agent = ttk.Entry(body, width=64)
        user_agent.pack(fill="x")
        try:
            current = read_json(self.cookie_path)
            header.insert(0, "; ".join(f"{key}={value}" for key, value in parse_cookies(current).items()))
            user_agent.insert(0, current.get("user_agent", ""))
        except (ValueError, OSError):
            pass
        error = ttk.Label(body, foreground="#a32d2d", wraplength=490)
        error.pack(anchor="w", pady=12)

        def save():
            try:
                data = {"cookie_header": header.get().strip(), "user_agent": user_agent.get().strip()}
                parsed = parse_cookies(data)
                if not parsed:
                    raise ValueError("Paste a Cookie header containing name=value pairs.")
                data["parsed_cookies"] = parsed
                write_json(self.cookie_path, data)
                self.access.set("Saved cookies")
                dialog.destroy()
            except (ValueError, OSError) as exc:
                error.configure(text=str(exc))

        ttk.Button(body, text="Save cookies", command=save, style="Primary.TButton").pack(anchor="e")

    def _persist(self):
        update_config(self.config_path, {"output_directory": self.folder.get().strip(), "media_choice": self.media.get(),
                                       "follow_pagination": self.follow.get(), "access_mode": self.access.get()})
        self.urls_file.parent.mkdir(parents=True, exist_ok=True)
        self.urls_file.write_text(self.urls.get("1.0", "end-1c").strip() + "\n", encoding="utf-8")

    def _error(self, message):
        self.status.set("Could not start")
        self.summary.set(message)

    def start(self):
        if self.running:
            return
        try:
            lines = [line.strip() for line in self.urls.get("1.0", "end-1c").splitlines() if line.strip() and not line.lstrip().startswith("#")]
            urls = [thread_url(line) for line in lines]
            if not urls:
                raise ValueError("Add at least one thread link.")
            if not self.folder.get().strip():
                raise ValueError("Choose a folder for your downloads.")
            output = Path(self.folder.get().strip()).expanduser().resolve()
            output.mkdir(parents=True, exist_ok=True)
            browser = self.access.get() == "Browser login"
            try:
                cookies = read_json(self.cookie_path)
            except (ValueError, OSError):
                if not browser:
                    raise
                cookies = {}
            if not browser and not parse_cookies(cookies):
                raise ValueError("Add cookies in Cookie settings, or choose Browser login.")
            self._persist()
        except (ValueError, OSError) as error:
            self._error(str(error))
            return
        self.stop_event.clear()
        self._set_running(True)
        self.status.set("Starting download…")
        self.summary.set("Preparing your threads.")
        self.transfer_text.set("")
        self.progress.configure(value=0)
        self.events.put(("log", "Starting download"))
        threading.Thread(target=self._run, args=(self.events, self.stop_event, urls, output, cookies, browser, self.follow.get(), MEDIA_CHOICES[self.media.get()]), daemon=True).start()

    def _set_running(self, running):
        self.running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.urls.configure(state="disabled" if running else "normal")
        for widget in self.editable:
            widget.configure(state="disabled" if running else "normal")
        for widget in (self.media_menu, self.access_menu):
            widget.configure(state="disabled" if running else "readonly")

    @staticmethod
    def _run(events, stop_event, urls, output, cookies, browser, follow, media_types):
        last_update = 0

        def transfer(done, total):
            nonlocal last_update
            now = time.monotonic()
            if now - last_update >= 0.15 or done == total:
                last_update = now
                events.put(("transfer", (done, total)))

        try:
            with ThreadClient(cookies, log=lambda message: events.put(("log", message)), browser_mode=browser, transfer=transfer) as client:
                result = download_threads(client, urls, output, log=lambda message: events.put(("log", message)),
                                          progress=lambda *values: events.put(("progress", values)),
                                          cancelled=stop_event.is_set, follow_pagination=follow, media_types=media_types)
            events.put(("done", result))
        except Exception as error:
            events.put(("failed", str(error)))

    def stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Stopping…")
        self.summary.set("Waiting for the current network request to finish.")

    def _poll(self):
        for _ in range(200):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(payload)
                if not self.stop_event.is_set() and payload.startswith(("Reading ", "Downloading ", "Resolving ", "Browser opened")):
                    self.status.set("Opening thread…" if payload.startswith("Reading ") else "Sign in using the browser window." if payload.startswith("Browser opened") else payload)
                    self.transfer_text.set("")
            elif kind == "progress":
                page, index, total, saved = payload
                self.progress.configure(value=100 * index / max(1, total))
                self.summary.set(f"Page {page} · {index} of {total} files checked · {saved} saved")
                self.transfer_text.set("")
            elif kind == "transfer":
                done, total = payload
                self.transfer_text.set(f"{size_text(done)} of {size_text(total)}" if total else f"{size_text(done)} downloaded")
                if total:
                    self.progress.configure(value=100 * done / total)
            elif kind in ("done", "failed"):
                self._set_running(False)
                self.transfer_text.set("")
                if kind == "failed":
                    self.status.set("Download failed")
                    self.summary.set("View the log for details.")
                    self._append_log(payload)
                else:
                    status = "Stopped" if payload.cancelled else "Finished with errors" if payload.errors else "Finished" if payload.saved else "No new files"
                    self.status.set(status)
                    self.summary.set(f"{payload.images} images and {payload.videos} videos saved · {payload.skipped} skipped · {payload.errors} errors")
                    self._append_log(f"{status}: {self.summary.get()}")
                    if not payload.cancelled and not payload.errors:
                        self.progress.configure(value=100)
                if self.closing:
                    self.window.destroy()
                    return
        self._poll_id = self.after(80, self._poll)

    def _append_log(self, message):
        self.messages.append(message)
        if self.log_text is not None and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def show_log(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift()
            return
        self.log_window = tk.Toplevel(self.window)
        self.log_window.title("Download log")
        self.log_window.geometry("780x440")
        self.log_window.transient(self.window)
        self.log_text = tk.Text(self.log_window, wrap="word", background="white", foreground=FOREGROUND, font="TkFixedFont", padx=14, pady=14, relief="flat")
        scrollbar = ttk.Scrollbar(self.log_window, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", "\n".join(self.messages))
        self.log_text.configure(state="disabled")

    def close(self):
        try:
            self._persist()
        except (ValueError, OSError) as error:
            self._append_log(f"Could not save settings: {error}")
        if self.running:
            self.closing = True
            self.stop()
        else:
            self.window.destroy()

    def destroy(self):
        if hasattr(self, "_poll_id"):
            self.after_cancel(self._poll_id)
        super().destroy()
