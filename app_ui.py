"""A single-window interface for the thread downloader."""

from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps

from config_utils import read_json, update_config, write_json
from download_engine import ThreadClient, download_threads
from site_utils import parse_cookies, thread_url

# (light, dark) pairs; CustomTkinter switches them with the appearance mode.
WINDOW = ("#f3f3f6", "#111215")
CARD = ("#ffffff", "#1b1c21")
FIELD = ("#f6f6f9", "#24252c")
BORDER = ("#e2e2e8", "#2c2d35")
TEXT = ("#1c1c22", "#ececf1")
MUTED = ("#6b6b78", "#9898a6")
ACCENT = ("#6b4dff", "#7b61ff")
ACCENT_HOVER = ("#5a3df0", "#6a4ff0")
SUBTLE = ("#ececf1", "#2a2b33")
SUBTLE_HOVER = ("#e0e0e7", "#34353e")
DANGER = ("#c93838", "#ff6b6b")
SUCCESS = ("#1f8f4e", "#4ade80")
MEDIA_CHOICES = {"Images and videos": ("image", "video"), "Images only": ("image",), "Videos only": ("video",)}
MEDIA_LABELS = {"Images and videos": "Both", "Images only": "Images", "Videos only": "Videos"}
ACCESS_CHOICES = ("Saved cookies", "Browser login")
APPEARANCES = ("System", "Light", "Dark")
LOG_LINES = 3000


def configure_style(window, appearance="System"):
    ctk.set_appearance_mode(appearance if appearance in APPEARANCES else "System")
    window.configure(fg_color=WINDOW)


def size_text(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024


def transfer_label(done, total, rate=0):
    """'12.0 MB of 50.0 MB · 4.0 MB/s · 0:10 left'; speed and time appear once a rate is known."""
    text = f"{size_text(done)} of {size_text(total)}" if total else f"{size_text(done)} downloaded"
    if rate > 0:
        text += f" · {size_text(rate)}/s"
        if total > done:
            seconds = int((total - done) / rate)
            text += f" · {seconds // 60}:{seconds % 60:02d} left"
    return text


def needs_repaint_workaround(widget):
    # Unpainted CustomTkinter labels after a resize only happen on X11 (including XWayland).
    # On Windows the full redraw re-shows the window to recolor its title bar, so it must not run there.
    return widget.tk.call("tk", "windowingsystem") == "x11"


def font(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)


def button(master, text, command, primary=False, **options):
    colors = {"fg_color": ACCENT, "hover_color": ACCENT_HOVER, "text_color": "#ffffff"} if primary else \
        {"fg_color": SUBTLE, "hover_color": SUBTLE_HOVER, "text_color": TEXT}
    defaults = {"corner_radius": 10, "height": 36, "font": font(13, "bold" if primary else "normal"), "text_color_disabled": MUTED}
    return ctk.CTkButton(master, text=text, command=command, **{**defaults, **colors, **options})


def segmented(master, values, variable=None, command=None):
    return ctk.CTkSegmentedButton(master, values=values, variable=variable, command=command, height=34, corner_radius=10, font=font(13),
                                  fg_color=SUBTLE, unselected_color=SUBTLE, unselected_hover_color=SUBTLE_HOVER,
                                  selected_color=ACCENT, selected_hover_color=ACCENT_HOVER, text_color=TEXT, text_color_disabled=MUTED)


def card(master):
    return ctk.CTkFrame(master, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER)


def label(master, text="", size=13, weight="normal", color=TEXT, **options):
    return ctk.CTkLabel(master, text=text, font=font(size, weight), text_color=color, anchor="w", justify="left", **options)


class DownloadApp(ctk.CTkFrame):
    def __init__(self, parent, config_path, urls_file):
        super().__init__(parent, fg_color="transparent")
        self.window = self.winfo_toplevel()
        self.config_path = Path(config_path)
        self.urls_file = Path(urls_file)
        self.cookie_path = self.config_path.parent / "manual_cookies.json"
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.skip_event = threading.Event()
        self.running = self.closing = False
        self.messages = []
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
        if self.access.get() not in ACCESS_CHOICES:
            self.access.set("Browser login")
        self.appearance = tk.StringVar(value=config.get("appearance", "System") if config.get("appearance") in APPEARANCES else "System")
        self.status = tk.StringVar(value="Ready")
        self.summary = tk.StringVar(value="Add a thread link, then press Start download.")
        self.transfer_text = tk.StringVar()
        self.transfer_started = None  # (monotonic time, bytes) of the current file's first update
        self.counts = {name: tk.StringVar(value="0") for name in ("Pages", "Images", "Videos", "Errors")}
        self._load_logo()
        self._build()
        self.window.bind("<Control-Return>", lambda event: self.start())
        if needs_repaint_workaround(self.window):
            self.window.bind("<Configure>", self._schedule_repaint, add="+")
        self._repaint_id = self._repaint_size = None
        self._destroyed = False
        self._poll_id = self.after(80, self._poll)

    def _schedule_repaint(self, event):
        # Tiling/Wayland window managers resize the window after it maps and some CustomTkinter
        # labels are left unpainted (white boxes); a full redraw once resizing settles fixes it.
        # Only size changes count: window moves also fire <Configure> and need no redraw.
        size = (event.width, event.height)
        if event.widget is self.window and size != self._repaint_size and not self._destroyed:
            self._repaint_size = size
            if self._repaint_id:
                self.after_cancel(self._repaint_id)
            self._repaint_id = self.after(200, self._repaint)

    def _repaint(self):
        self._repaint_id = None
        ctk.AppearanceModeTracker.update_callbacks()

    def _load_logo(self):
        """A round header logo plus the native window icon; the app still runs if the file is missing."""
        logo_path = Path(__file__).resolve().parent / "assets" / "anna.png"
        self.logo_image = None
        try:
            self.window_logo_image = tk.PhotoImage(file=logo_path)
            self.window.iconphoto(False, self.window_logo_image)
            picture = ImageOps.fit(Image.open(logo_path).convert("RGBA"), (96, 96))
            mask = Image.new("L", picture.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, *picture.size), fill=255)
            picture.putalpha(mask)
            self.logo_image = ctk.CTkImage(picture, picture, size=(42, 42))
        except (tk.TclError, OSError):
            pass

    def _build(self):
        self.grid_columnconfigure(0, weight=5, uniform="columns")
        self.grid_columnconfigure(1, weight=4, uniform="columns")
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 14))
        if self.logo_image is not None:
            ctk.CTkLabel(header, image=self.logo_image, text="").pack(side="left", padx=(0, 12))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        label(titles, "SimpDL", 22, "bold").pack(anchor="w")
        label(titles, "Download full-quality images and videos from threads", 12, color=MUTED).pack(anchor="w")
        theme = segmented(header, list(APPEARANCES), self.appearance, self._set_appearance)
        theme.configure(height=30, font=font(12))
        theme.pack(side="right")

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 24))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        self._build_threads(left).grid(row=0, column=0, sticky="nsew", pady=(0, 16))
        self._build_options(left).grid(row=1, column=0, sticky="ew")
        self._build_activity(self).grid(row=1, column=1, sticky="nsew", padx=(8, 24), pady=(0, 24))

    def _build_threads(self, master):
        box = card(master)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        label(top, "Thread links", 15, "bold").pack(side="left")
        self.thread_count = label(top, "", 12, color=MUTED)
        self.thread_count.pack(side="left", padx=(10, 0))
        for text, command in (("Clear", self.clear_urls), ("Page range…", self.page_range), ("Paste", self.paste)):
            widget = button(top, text, command, width=0, height=32)
            widget.pack(side="right", padx=(6, 0))
            self.editable.append(widget)
        self.urls = ctk.CTkTextbox(box, wrap="none", undo=True, font=font(13), corner_radius=10, border_width=1,
                                   fg_color=FIELD, border_color=BORDER, text_color=TEXT, height=110)
        self.urls.grid(row=1, column=0, sticky="nsew", padx=20)
        if self.urls_file.exists():
            self.urls.insert("1.0", self.urls_file.read_text(encoding="utf-8").strip() + "\n")
        self.urls.bind("<KeyRelease>", lambda event: self._count_threads())
        label(box, "One thread per line · files already downloaded are skipped", 12, color=MUTED).grid(row=2, column=0, sticky="w", padx=20, pady=(8, 16))
        self._count_threads()
        return box

    def _build_options(self, master):
        box = card(master)
        box.grid_columnconfigure(1, weight=1)
        label(box, "Options", 15, "bold").grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 12))

        label(box, "Save to", color=MUTED).grid(row=1, column=0, sticky="w", padx=(20, 14), pady=6)
        folder_row = ctk.CTkFrame(box, fg_color="transparent")
        folder_row.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=6)
        folder_entry = ctk.CTkEntry(folder_row, textvariable=self.folder, height=36, corner_radius=10, border_width=1,
                                    fg_color=FIELD, border_color=BORDER, text_color=TEXT, font=font(13))
        folder_entry.pack(side="left", fill="x", expand=True)
        browse = button(folder_row, "Browse…", self.browse, width=0)
        browse.pack(side="left", padx=(8, 0))
        button(folder_row, "Open", self.open_folder, width=0).pack(side="left", padx=(8, 0))
        self.editable.extend([folder_entry, browse])

        label(box, "Download", color=MUTED).grid(row=2, column=0, sticky="w", padx=(20, 14), pady=6)
        media_row = ctk.CTkFrame(box, fg_color="transparent")
        media_row.grid(row=2, column=1, sticky="ew", padx=(0, 20), pady=6)
        self.media_label = tk.StringVar(value=MEDIA_LABELS[self.media.get()])
        self.media_menu = segmented(media_row, list(MEDIA_LABELS.values()), self.media_label,
                                    lambda value: self.media.set(next(k for k, v in MEDIA_LABELS.items() if v == value)))
        self.media_menu.pack(side="left")

        label(box, "Pages", color=MUTED).grid(row=3, column=0, sticky="w", padx=(20, 14), pady=6)
        follow = ctk.CTkSwitch(box, text="Follow next pages automatically", variable=self.follow, onvalue=True, offvalue=False, font=font(13),
                               progress_color=ACCENT, text_color=TEXT, text_color_disabled=MUTED)
        follow.grid(row=3, column=1, sticky="w", pady=6)
        self.editable.append(follow)

        label(box, "Access", color=MUTED).grid(row=4, column=0, sticky="w", padx=(20, 14), pady=6)
        access_row = ctk.CTkFrame(box, fg_color="transparent")
        access_row.grid(row=4, column=1, sticky="ew", padx=(0, 20), pady=6)
        self.access_menu = segmented(access_row, list(ACCESS_CHOICES), self.access, lambda value: self._access_hint())
        self.access_menu.pack(side="left")
        cookies = button(access_row, "Cookies…", self.cookie_settings, width=0)
        cookies.pack(side="left", padx=(8, 0))
        self.editable.append(cookies)
        self.access_note = label(box, "", 12, color=MUTED)
        self.access_note.grid(row=5, column=1, sticky="w", padx=(0, 20), pady=(2, 18))
        self._access_hint()
        return box

    def _build_activity(self, master):
        box = card(master)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(4, weight=1)
        self.status_label = label(box, textvariable=self.status, size=17, weight="bold")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 2))
        self.summary_label = label(box, textvariable=self.summary, size=12, color=MUTED, wraplength=360)
        self.summary_label.grid(row=1, column=0, sticky="ew", padx=20)
        box.bind("<Configure>", lambda event: self.summary_label.configure(wraplength=max(200, event.width - 50)))

        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(14, 0))
        self.progress = ctk.CTkProgressBar(bar, height=8, corner_radius=4, progress_color=ACCENT, fg_color=SUBTLE)
        self.progress.set(0)
        self.progress.pack(fill="x")
        label(bar, textvariable=self.transfer_text, size=12, color=MUTED).pack(anchor="w", pady=(4, 0))

        stats = ctk.CTkFrame(box, fg_color="transparent")
        stats.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 12))
        for column, (name, value) in enumerate(self.counts.items()):
            stats.grid_columnconfigure(column, weight=1, uniform="stats")
            tile = ctk.CTkFrame(stats, fg_color=FIELD, corner_radius=12)
            tile.grid(row=0, column=column, sticky="ew", padx=6)
            label(tile, textvariable=value, size=20, weight="bold", color=DANGER if name == "Errors" else TEXT).pack(anchor="w", padx=12, pady=(8, 0))
            label(tile, name, 11, color=MUTED).pack(anchor="w", padx=12, pady=(0, 8))

        self.log_text = ctk.CTkTextbox(box, wrap="word", font=ctk.CTkFont(family="monospace", size=11), corner_radius=10,
                                       fg_color=FIELD, text_color=MUTED, border_width=0, height=120)
        self.log_text.grid(row=4, column=0, sticky="nsew", padx=20)
        self.log_text.insert("end", "Download activity will appear here.\n")
        self.log_text.configure(state="disabled")

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=20, pady=(14, 20))
        actions.grid_columnconfigure(2, weight=1)
        self.stop_button = button(actions, "Stop", self.stop, state="disabled", width=80, height=44)
        self.stop_button.grid(row=0, column=0, sticky="w")
        self.skip_button = button(actions, "Skip file", self.skip, state="disabled", width=96, height=44)
        self.skip_button.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.start_button = button(actions, "Start download", self.start, primary=True, height=44, font=font(15, "bold"))
        self.start_button.grid(row=0, column=2, sticky="ew", padx=(10, 0))
        return box

    def _set_appearance(self, value):
        ctk.set_appearance_mode(value)
        try:
            update_config(self.config_path, {"appearance": value})
        except (ValueError, OSError) as error:
            self._append_log(f"Could not save settings: {error}")

    def _access_hint(self):
        self.access_note.configure(text="A browser window opens so you can sign in." if self.access.get() == "Browser login"
                                   else "Uses the cookies you saved with the Cookies… button.")

    def _url_lines(self):
        return [line.strip() for line in self.urls.get("1.0", "end-1c").splitlines() if line.strip() and not line.lstrip().startswith("#")]

    def _count_threads(self):
        count = len(self._url_lines())
        self.thread_count.configure(text=f"{count} link{'s' if count != 1 else ''}" if count else "")

    def _add_urls(self, lines):
        existing = self.urls.get("1.0", "end-1c").strip().splitlines()
        self.urls.delete("1.0", "end")
        self.urls.insert("1.0", "\n".join(dict.fromkeys(line for line in existing + lines if line.strip())) + "\n")
        self._count_threads()

    def paste(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = ""
        lines = [line.strip() for line in text.split() if line.strip().startswith("http")]
        if lines:
            self._add_urls(lines)
        else:
            self._error("The clipboard has no links.", "Nothing to paste")

    def clear_urls(self):
        self.urls.delete("1.0", "end")
        self._count_threads()

    def browse(self):
        path = ctk.filedialog.askdirectory(parent=self.window, initialdir=self.folder.get(), title="Download folder")
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
        dialog = ctk.CTkToplevel(self.window, fg_color=WINDOW)
        dialog.title(title)
        dialog.transient(self.window)
        dialog.resizable(False, False)
        dialog.bind("<Escape>", lambda event: dialog.destroy())

        def grab():
            # A grab on a window that is not mapped yet raises on Linux.
            try:
                if dialog.winfo_exists():
                    dialog.grab_set()
            except tk.TclError:
                pass

        dialog.after(150, grab)
        content = card(dialog)
        content.pack(fill="both", expand=True, padx=16, pady=16)
        return dialog, content

    def _field(self, master, **options):
        return ctk.CTkEntry(master, height=36, corner_radius=10, border_width=1, fg_color=FIELD, border_color=BORDER,
                            text_color=TEXT, font=font(13), **options)

    def page_range(self):
        dialog, body = self._dialog("Add a page range")
        label(body, "Add a page range", 15, "bold").grid(row=0, column=0, columnspan=4, sticky="w", padx=20, pady=(18, 4))
        label(body, "Only the chosen pages are downloaded.", 12, color=MUTED).grid(row=1, column=0, columnspan=4, sticky="w", padx=20, pady=(0, 12))
        entry = self._field(body, width=460, placeholder_text="https://simpcity.cr/threads/…")
        entry.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 12))
        lines = self._url_lines()
        if lines:
            entry.insert(0, lines[-1])
        label(body, "From page", color=MUTED).grid(row=3, column=0, sticky="w", padx=(20, 8))
        first = self._field(body, width=80)
        first.insert(0, "1")
        first.grid(row=3, column=1, sticky="w")
        label(body, "To page", color=MUTED).grid(row=3, column=2, sticky="e", padx=(16, 8))
        last = self._field(body, width=80)
        last.insert(0, "5")
        last.grid(row=3, column=3, sticky="w", padx=(0, 20))
        error = label(body, "", 12, color=DANGER, wraplength=440)
        error.grid(row=4, column=0, columnspan=4, sticky="w", padx=20, pady=8)

        def add():
            try:
                try:
                    start, end = int(first.get()), int(last.get())
                except ValueError:
                    raise ValueError("Page numbers must be whole numbers.") from None
                if not 1 <= start <= end <= 100000 or end - start > 9999:
                    raise ValueError("Choose a valid range of up to 10,000 pages.")
                self._add_urls([thread_url(entry.get(), number) for number in range(start, end + 1)])
                if start == end == 1:
                    self.follow.set(False)
                dialog.destroy()
            except ValueError as exc:
                error.configure(text=str(exc))

        button(body, "Add pages", add, primary=True).grid(row=5, column=0, columnspan=4, sticky="e", padx=20, pady=(0, 18))
        dialog.bind("<Return>", lambda event: add())
        entry.focus_set()

    def cookie_settings(self):
        dialog, body = self._dialog("Cookies")
        label(body, "Use an existing browser session", 15, "bold").pack(anchor="w", padx=20, pady=(18, 4))
        label(body, "Sign in to SimpCity in your browser, open Developer Tools → Network, reload a thread\n"
                    "and copy the request's Cookie header. Or choose Browser login instead.", 12, color=MUTED).pack(anchor="w", padx=20, pady=(0, 14))
        label(body, "Cookie header", color=MUTED).pack(anchor="w", padx=20, pady=(0, 4))
        header = self._field(body, width=520, show="•")
        header.pack(fill="x", padx=20)
        label(body, "User-Agent (optional, from the same browser)", color=MUTED).pack(anchor="w", padx=20, pady=(12, 4))
        user_agent = self._field(body, width=520)
        user_agent.pack(fill="x", padx=20)
        try:
            current = read_json(self.cookie_path)
            header.insert(0, "; ".join(f"{key}={value}" for key, value in parse_cookies(current).items()))
            user_agent.insert(0, current.get("user_agent", ""))
        except (ValueError, OSError):
            pass
        error = label(body, "", 12, color=DANGER, wraplength=500)
        error.pack(anchor="w", padx=20, pady=8)

        def save():
            try:
                data = {"cookie_header": header.get().strip(), "user_agent": user_agent.get().strip()}
                parsed = parse_cookies(data)
                if not parsed:
                    raise ValueError("Paste a Cookie header containing name=value pairs.")
                data["parsed_cookies"] = parsed
                write_json(self.cookie_path, data)
                self.access.set("Saved cookies")
                self._access_hint()
                dialog.destroy()
            except (ValueError, OSError) as exc:
                error.configure(text=str(exc))

        button(body, "Save cookies", save, primary=True).pack(anchor="e", padx=20, pady=(0, 18))
        dialog.bind("<Return>", lambda event: save())
        header.focus_set()

    def _persist(self):
        update_config(self.config_path, {"output_directory": self.folder.get().strip(), "media_choice": self.media.get(),
                                         "follow_pagination": self.follow.get(), "access_mode": self.access.get()})
        self.urls_file.parent.mkdir(parents=True, exist_ok=True)
        self.urls_file.write_text(self.urls.get("1.0", "end-1c").strip() + "\n", encoding="utf-8")

    def _set_status(self, text, color=TEXT):
        self.status.set(text)
        self.status_label.configure(text_color=color)

    def _error(self, message, title="Could not start"):
        self._set_status(title, DANGER)
        self.summary.set(message)

    def start(self):
        if self.running:
            return
        try:
            urls = [thread_url(line) for line in self._url_lines()]
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
                raise ValueError("Add cookies under Cookies…, or choose Browser login.")
            self._persist()
        except (ValueError, OSError) as error:
            self._error(str(error))
            return
        self.stop_event.clear()
        self.skip_event.clear()
        self._set_running(True)
        self._set_status("Starting download…")
        self.summary.set("Preparing your threads.")
        self.transfer_text.set("")
        self.progress.set(0)
        for value in self.counts.values():
            value.set("0")
        self._append_log("Starting download")
        threading.Thread(target=self._run, args=(self.events, self.stop_event, self.skip_event, urls, output, cookies, browser, self.follow.get(), MEDIA_CHOICES[self.media.get()]), daemon=True).start()

    def _set_running(self, running):
        self.running = running
        state = "disabled" if running else "normal"
        self.start_button.configure(state=state, text="Downloading…" if running else "Start download")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.skip_button.configure(state="normal" if running else "disabled")
        self.urls.configure(state=state)
        for widget in self.editable + [self.media_menu, self.access_menu]:
            widget.configure(state=state)

    @staticmethod
    def _run(events, stop_event, skip_event, urls, output, cookies, browser, follow, media_types):
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
                                          cancelled=stop_event.is_set, follow_pagination=follow, media_types=media_types, skip=skip_event)
            events.put(("done", result))
        except Exception as error:
            events.put(("failed", str(error)))

    def skip(self):
        """Abandon only the file in progress; the run continues with the next one."""
        if self.running and not self.stop_event.is_set():
            self.skip_event.set()
            self._set_status("Skipping current file…")
            self.transfer_text.set("")

    def stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.skip_button.configure(state="disabled")
        self._set_status("Stopping…")
        self.summary.set("Waiting for the current network request to finish.")

    def _bump(self, name):
        self.counts[name].set(str(int(self.counts[name].get()) + 1))

    def _poll(self):
        try:
            self._drain_events()
        except tk.TclError:
            return  # The window is being destroyed.
        if not self.closing or self.running:
            self._poll_id = self.after(80, self._poll)

    def _drain_events(self):
        for _ in range(200):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(payload)
                if payload.startswith("Saved image"):
                    self._bump("Images")
                elif payload.startswith("Saved video"):
                    self._bump("Videos")
                elif " failed" in payload:
                    self._bump("Errors")
                if not self.stop_event.is_set() and payload.startswith(("Reading ", "Downloading ", "Resolving ", "Browser opened", "Bunkr link has")):
                    self._set_status("Opening thread…" if payload.startswith("Reading ") else "Sign in using the browser window." if payload.startswith("Browser opened") else payload.split(":")[0])
                    self.transfer_text.set("")
            elif kind == "progress":
                page, index, total, saved = payload
                self.counts["Pages"].set(str(page))
                self.progress.set(index / max(1, total))
                self.summary.set(f"Page {page} · {index} of {total} files checked · {saved} saved")
                self.transfer_text.set("")
            elif kind == "transfer":
                done, total = payload
                now = time.monotonic()
                if self.transfer_started is None or done < self.transfer_started[1]:
                    self.transfer_started = (now, done)  # A new file started.
                started, base = self.transfer_started
                elapsed = now - started
                self.transfer_text.set(transfer_label(done, total, (done - base) / elapsed if elapsed >= 0.5 else 0))
                if total:
                    self.progress.set(done / total)
            elif kind in ("done", "failed"):
                self._set_running(False)
                self.transfer_text.set("")
                if kind == "failed":
                    self._set_status("Download failed", DANGER)
                    self.summary.set(payload)
                    self._append_log(payload)
                else:
                    status = "Stopped" if payload.cancelled else "Finished with errors" if payload.errors else "Finished" if payload.saved else "No new files"
                    self._set_status(status, SUCCESS if status == "Finished" else DANGER if payload.errors else TEXT)
                    self.summary.set(f"{payload.images} images and {payload.videos} videos saved · {payload.skipped} skipped · {payload.errors} errors")
                    for name, value in (("Pages", payload.pages), ("Images", payload.images), ("Videos", payload.videos), ("Errors", payload.errors)):
                        self.counts[name].set(str(value))
                    self._append_log(f"{status}: {self.summary.get()}")
                    if not payload.cancelled and not payload.errors:
                        self.progress.set(1)
                if self.closing:
                    self.window.destroy()
                    return

    def _append_log(self, message):
        first = not self.messages
        self.messages.append(message)
        del self.messages[:-LOG_LINES]
        self.log_text.configure(state="normal")
        if first:
            self.log_text.delete("1.0", "end")  # Drop the "activity will appear here" placeholder.
        self.log_text.insert("end", message + "\n")
        if int(self.log_text.index("end-1c").split(".")[0]) > LOG_LINES:
            self.log_text.delete("1.0", "2.0")
        self.log_text.see("end")
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
        self._destroyed = True
        for pending in (getattr(self, "_poll_id", None), getattr(self, "_repaint_id", None)):
            if pending:
                self.after_cancel(pending)
        super().destroy()
