import json
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame

def build_config_frame(parent, config_path):
    """
    Creates a Frame for modifying the config inside the main window.
    """
    frame = tb.Frame(parent, bootstyle="dark")

    title_label = tb.Label(frame, text="Modify Config", font=("Helvetica", 18, "bold"))
    title_label.pack(pady=10)

   
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}

    
    container = ScrolledFrame(frame, autohide=True, bootstyle="round")
    container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    content = container

    entries = {}
    for key, val in config.items():
        row = tb.Frame(content, bootstyle="dark")
        row.pack(fill="x", pady=5)

        lbl = tb.Label(row, text=f"{key}:", width=20, anchor="w")
        lbl.pack(side="left")

        entry = tb.Entry(row)
        entry.insert(0, str(val))
        entry.pack(side="left", fill="x", expand=True)
        entries[key] = entry

    def save_config():
        for key, entry in entries.items():
            config[key] = entry.get()
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)

    save_button = tb.Button(frame, text="Save", bootstyle="success", command=save_config)
    save_button.pack(pady=10)

    return frame


def build_urls_frame(parent, urls_file):
    """
    Creates a Frame for changing the URL file inside the main window.
    Always re-reads the file each time we refresh the list, ensuring the UI
    is in sync with the current state of urls.txt.
    """
    frame = tb.Frame(parent, bootstyle="dark")

    title_label = tb.Label(frame, text="Change URL File", font=("Helvetica", 18, "bold"))
    title_label.pack(pady=10)

   
    container = ScrolledFrame(frame, autohide=True, bootstyle="round")
    container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    content = container  

    row_frames = []

    def get_urls_from_file():
        """Read the current URLs from disk, stripping empty lines."""
        try:
            with open(urls_file, "r") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def refresh_list():
        
        
        for rf in row_frames:
            rf.destroy()
        row_frames.clear()

        loaded_urls = get_urls_from_file()

        
        for i, url in enumerate(loaded_urls):
            row = tb.Frame(content, bootstyle="dark")
            row.pack(fill="x", pady=3)
            row_frames.append(row)

            lbl = tb.Label(row, text=url, anchor="w")
            lbl.pack(side="left", padx=5, fill="x", expand=True)

            delete_btn = tb.Button(
                row,
                text="Delete Link",
                bootstyle="danger",
                command=lambda idx=i: remove_url(idx)
            )
            delete_btn.pack(side="right", padx=5)

    def remove_url(index):
        
        loaded_urls = get_urls_from_file()
        if 0 <= index < len(loaded_urls):
            loaded_urls.pop(index)
            with open(urls_file, "w") as f:
                for u in loaded_urls:
                    f.write(u + "\n")
        refresh_list()

    def add_url():
        
        new_url = new_url_entry.get().strip()
        if new_url:
            loaded_urls = get_urls_from_file()
            loaded_urls.append(new_url)
            with open(urls_file, "w") as f:
                for u in loaded_urls:
                    f.write(u + "\n")
            new_url_entry.delete(0, "end")
        refresh_list()


    add_row = tb.Frame(frame, bootstyle="dark")
    add_row.pack(fill="x", pady=(0, 10))

    add_label = tb.Label(add_row, text="Add New URL:", anchor="w")
    add_label.pack(side="left", padx=5)

    new_url_entry = tb.Entry(add_row)
    new_url_entry.pack(side="left", fill="x", expand=True, padx=5)
  
    new_url_entry.bind("<Return>", lambda event: add_url())

    add_button = tb.Button(add_row, text="Add", bootstyle="info", command=add_url)
    add_button.pack(side="right", padx=5)

   
    refresh_list()

    
    frame.refresh_list = refresh_list

    return frame
