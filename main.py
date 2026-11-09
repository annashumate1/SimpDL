"""SimpDL desktop entry point."""

from pathlib import Path

import customtkinter as ctk

from app_ui import DownloadApp, configure_style
from config_utils import read_json, write_json


def load_config(path):
    """Settings for the first launch; an unreadable file is set aside rather than stopping the app."""
    try:
        config = read_json(path)
    except (ValueError, OSError):
        try:
            path.replace(path.with_name(path.name + ".bad"))
        except OSError:
            pass
        config = {}
    if (config.get("output_directory") or "").strip() in ("", "/path"):
        config["output_directory"] = str(Path.home() / "Downloads" / "SimpDL")
        write_json(path, config)
    return config


def main_gui():
    script_dir = Path(__file__).resolve().parent
    config = load_config(script_dir / "config" / "config.json")
    app = ctk.CTk()
    app.title("SimpDL")
    app.geometry("1120x760")
    configure_style(app, config.get("appearance", "System"))
    view = DownloadApp(app, script_dir / "config" / "config.json", script_dir / "config" / "urls.txt")
    view.pack(fill="both", expand=True)
    app.update_idletasks()
    app.minsize(760, 600)
    app.protocol("WM_DELETE_WINDOW", view.close)
    app.mainloop()


if __name__ == "__main__":
    main_gui()
