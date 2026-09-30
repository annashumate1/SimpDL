"""SimpDL desktop entry point."""

import json
import os
import tkinter as tk
from pathlib import Path

from app_ui import DownloadApp, configure_style


def ensure_first_run_defaults(script_dir: str) -> dict:
    """Create sane defaults so the app can launch on a fresh clone.
    Returns the loaded (or created) config dict.
    """
    config_dir = os.path.join(script_dir, "config")
    os.makedirs(config_dir, exist_ok=True)

    config_path = os.path.join(config_dir, "config.json")
    urls_file = os.path.join(config_dir, "urls.txt")
    cookie_file = os.path.join(config_dir, "manual_cookies.json")

    default_output = os.path.join(os.path.expanduser("~"), "Downloads", "SimpDL")

    # --- config.json ---
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f) or {}
        except Exception:
            # If it's corrupted, don't crash startup; keep the bad file around.
            bad_path = config_path + ".bad"
            try:
                os.replace(config_path, bad_path)
            except Exception:
                pass
            config = {}

    changed = False
    out = (config.get("output_directory") or "").strip()
    if not out or out == "/path":
        config["output_directory"] = default_output
        changed = True

    if changed or not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    # --- urls.txt ---
    if not os.path.exists(urls_file):
        with open(urls_file, "w", encoding="utf-8") as f:
            f.write("")

    # --- manual_cookies.json (template) ---
    if not os.path.exists(cookie_file):
        template = {
            "cookie_header": "",
            "parsed_cookies": {},
            "notes": "Paste your Cookie header here. You can generate it by running extract_cookie_header.py"
        }
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)

    # Ensure default output directory exists (safe: inside home)
    try:
        os.makedirs(config.get("output_directory", default_output), exist_ok=True)
    except Exception:
        config["output_directory"] = default_output
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.makedirs(default_output, exist_ok=True)

    return config

def main_gui():
    script_dir = Path(__file__).resolve().parent
    ensure_first_run_defaults(str(script_dir))
    app = tk.Tk()
    app.title("SimpDL")
    app.geometry("860x720")
    configure_style(app)
    view = DownloadApp(app, script_dir / "config" / "config.json", script_dir / "config" / "urls.txt")
    view.pack(fill="both", expand=True)
    app.update_idletasks()
    app.minsize(max(720, view.winfo_reqwidth()), view.winfo_reqheight())
    app.protocol("WM_DELETE_WINDOW", view.close)
    app.mainloop()


if __name__ == "__main__":
    main_gui()
