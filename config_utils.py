import json
import os
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
from tkinter import filedialog

def build_config_frame(parent, config_path):
    """Ultra-sleek settings interface."""
    frame = tk.Frame(parent, bg='#0a0e27', relief='flat', bd=0)

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {"output_directory": ""}

    # Card
    card = tk.Frame(frame, bg='#1e293b', relief='flat', bd=0)
    card.pack(fill="both", expand=True)

    content = tk.Frame(card, bg='#1e293b', relief='flat', bd=0)
    content.pack(padx=50, pady=45, fill="both", expand=True)

    # Title
    title_label = tk.Label(
        content,
        text="Download Path",
        font=("SF Pro Display", 18, "bold"),
        foreground="#ffffff",
        bg='#1e293b'
    )
    title_label.pack(anchor="w", pady=(0, 8))

    subtitle_label = tk.Label(
        content,
        text="Configure where your files will be saved",
        font=("SF Pro Display", 11),
        foreground="#64748b",
        bg='#1e293b'
    )
    subtitle_label.pack(anchor="w", pady=(0, 35))

    # Current path
    current_frame = tk.Frame(content, bg='#334155', relief='flat', bd=0)
    current_frame.pack(fill="x", pady=(0, 30))

    current_content = tk.Frame(current_frame, bg='#334155', relief='flat', bd=0)
    current_content.pack(padx=25, pady=22)

    current_label = tk.Label(
        current_content,
        text="CURRENT",
        font=("SF Pro Display", 9, "bold"),
        foreground="#475569",
        bg='#334155'
    )
    current_label.pack(anchor="w")

    current_path = config.get('output_directory', '')
    current_dir_label = tk.Label(
        current_content,
        text=current_path if current_path else "Not configured",
        font=("SF Pro Display", 12),
        foreground="#10b981" if current_path else "#ef4444",
        bg='#334155',
        wraplength=850
    )
    current_dir_label.pack(anchor="w", pady=(6, 0))

    # Input section
    input_label = tk.Label(
        content,
        text="New Path",
        font=("SF Pro Display", 12, "bold"),
        foreground="#cbd5e1",
        bg='#1e293b'
    )
    input_label.pack(anchor="w", pady=(0, 12))

    input_container = tk.Frame(content, bg='#0f172a', relief='flat', bd=0)
    input_container.pack(fill="x", pady=(0, 25))

    path_entry = tk.Entry(
        input_container,
        font=("SF Pro Display", 11),
        bg='#0f172a',
        fg='#cbd5e1',
        relief='flat',
        bd=0,
        insertbackground='#6366f1'
    )
    path_entry.insert(0, config.get("output_directory", ""))
    path_entry.pack(side="left", fill="x", expand=True, padx=18, ipady=12)

    def browse_folder():
        folder = filedialog.askdirectory(
            title="Select Download Folder",
            initialdir=config.get("output_directory", os.path.expanduser("~"))
        )
        if folder:
            path_entry.delete(0, tk.END)
            path_entry.insert(0, folder)

    browse_frame = tk.Frame(input_container, bg='#312e81', relief='flat', bd=0, cursor='hand2')
    browse_frame.pack(side="right")
    browse_frame.bind("<Button-1>", lambda e: browse_folder())

    browse_label = tk.Label(
        browse_frame,
        text="Browse",
        font=("SF Pro Display", 11, "bold"),
        foreground="#6366f1",
        bg='#312e81',
        cursor='hand2'
    )
    browse_label.pack(padx=20, pady=12)
    browse_label.bind("<Button-1>", lambda e: browse_folder())

    # Status
    status_label = tk.Label(
        content,
        text="",
        font=("SF Pro Display", 10),
        bg='#1e293b'
    )
    status_label.pack(anchor="w", pady=(0, 25))

    # Save button
    def save_config():
        new_path = path_entry.get().strip()
        
        if not new_path:
            status_label.config(text="⚠ Please enter a valid path", foreground="#f59e0b")
            return
        
        config["output_directory"] = new_path
        
        if not os.path.exists(new_path):
            try:
                os.makedirs(new_path)
                status_label.config(text="✓ Directory created and saved", foreground="#10b981")
            except Exception as e:
                status_label.config(text=f"✗ Error: {str(e)}", foreground="#ef4444")
                return
        else:
            status_label.config(text="✓ Configuration saved", foreground="#10b981")
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        
        current_dir_label.config(text=new_path, foreground="#10b981")

    save_frame = tk.Frame(content, bg='#10b981', relief='flat', bd=0, cursor='hand2')
    save_frame.pack(anchor="w")
    save_frame.bind("<Button-1>", lambda e: save_config())

    save_label = tk.Label(
        save_frame,
        text="Save Configuration",
        font=("SF Pro Display", 11, "bold"),
        foreground="#ffffff",
        bg='#10b981',
        cursor='hand2'
    )
    save_label.pack(padx=26, pady=13)
    save_label.bind("<Button-1>", lambda e: save_config())

    return frame


def build_urls_frame(parent, urls_file):
    """Ultra-sleek URL management."""
    frame = tk.Frame(parent, bg='#0a0e27', relief='flat', bd=0)

    card = tk.Frame(frame, bg='#1e293b', relief='flat', bd=0)
    card.pack(fill="both", expand=True)

    content = tk.Frame(card, bg='#1e293b', relief='flat', bd=0)
    content.pack(padx=50, pady=45, fill="both", expand=True)

    # Title
    title_label = tk.Label(
        content,
        text="URL Queue",
        font=("SF Pro Display", 18, "bold"),
        foreground="#ffffff",
        bg='#1e293b'
    )
    title_label.pack(anchor="w", pady=(0, 8))

    subtitle_label = tk.Label(
        content,
        text="Manage your download queue",
        font=("SF Pro Display", 11),
        foreground="#64748b",
        bg='#1e293b'
    )
    subtitle_label.pack(anchor="w", pady=(0, 30))

    # Add URL
    add_container = tk.Frame(content, bg='#0f172a', relief='flat', bd=0)
    add_container.pack(fill="x", pady=(0, 35))

    url_entry = tk.Entry(
        add_container,
        font=("SF Pro Display", 11),
        bg='#0f172a',
        fg='#cbd5e1',
        relief='flat',
        bd=0,
        insertbackground='#6366f1'
    )
    url_entry.pack(side="left", fill="x", expand=True, padx=18, ipady=12)

    def add_url():
        new_url = url_entry.get().strip()
        if new_url:
            loaded_urls = get_urls_from_file()
            loaded_urls.append(new_url)
            with open(urls_file, "w") as f:
                for u in loaded_urls:
                    f.write(u + "\n")
            url_entry.delete(0, "end")
            refresh_list()

    url_entry.bind("<Return>", lambda e: add_url())

    add_frame = tk.Frame(add_container, bg='#6366f1', relief='flat', bd=0, cursor='hand2')
    add_frame.pack(side="right")
    add_frame.bind("<Button-1>", lambda e: add_url())

    add_label = tk.Label(
        add_frame,
        text="Add URL",
        font=("SF Pro Display", 11, "bold"),
        foreground="#ffffff",
        bg='#6366f1',
        cursor='hand2'
    )
    add_label.pack(padx=24, pady=12)
    add_label.bind("<Button-1>", lambda e: add_url())

    # Queue header
    queue_header = tk.Frame(content, bg='#1e293b', relief='flat', bd=0)
    queue_header.pack(fill="x", pady=(0, 18))

    queue_label = tk.Label(
        queue_header,
        text="Queue",
        font=("SF Pro Display", 14, "bold"),
        foreground="#ffffff",
        bg='#1e293b'
    )
    queue_label.pack(side="left")

    queue_count = tk.Label(
        queue_header,
        text="",
        font=("SF Pro Display", 11, "bold"),
        foreground="#6366f1",
        bg='#1e293b'
    )
    queue_count.pack(side="right")

    # List
    list_container = tk.Frame(content, bg='#334155', relief='flat', bd=0)
    list_container.pack(fill="both", expand=True)

    container = ScrolledFrame(list_container, autohide=True, bootstyle="rounded")
    container.pack(fill="both", expand=True, padx=2, pady=2)
    content_area = container

    row_frames = []

    def get_urls_from_file():
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
        queue_count.config(text=f"{len(loaded_urls)} URLs")

        if not loaded_urls:
            empty_frame = tk.Frame(content_area, bg='#334155', relief='flat', bd=0)
            empty_frame.pack(pady=100)
            
            empty_label = tk.Label(
                empty_frame,
                text="Queue is empty",
                font=("SF Pro Display", 16, "bold"),
                foreground="#475569",
                bg='#334155'
            )
            empty_label.pack()
            
            empty_hint = tk.Label(
                empty_frame,
                text="Add URLs above to build your queue",
                font=("SF Pro Display", 11),
                foreground="#334155",
                bg='#334155'
            )
            empty_hint.pack(pady=(6, 0))
            
            row_frames.append(empty_frame)
        else:
            for i, url in enumerate(loaded_urls):
                row = tk.Frame(content_area, bg='#0f172a', relief='flat', bd=0)
                row.pack(fill="x", pady=1, padx=1)
                row_frames.append(row)

                row_content = tk.Frame(row, bg='#0f172a', relief='flat', bd=0)
                row_content.pack(fill="x", padx=22, pady=16)

                num_badge = tk.Label(
                    row_content,
                    text=f"{i+1:02d}",
                    font=("SF Pro Display", 10, "bold"),
                    foreground="#6366f1",
                    bg='#0f172a'
                )
                num_badge.pack(side="left", padx=(0, 18))

                url_label = tk.Label(
                    row_content,
                    text=url,
                    font=("SF Pro Display", 10),
                    foreground="#cbd5e1",
                    bg='#0f172a',
                    anchor="w"
                )
                url_label.pack(side="left", fill="x", expand=True)

                delete_frame = tk.Frame(row_content, bg='#7f1d1d', relief='flat', bd=0, cursor='hand2')
                delete_frame.pack(side="right")
                delete_frame.bind("<Button-1>", lambda e, idx=i: remove_url(idx))

                delete_label = tk.Label(
                    delete_frame,
                    text="Remove",
                    font=("SF Pro Display", 9, "bold"),
                    foreground="#ef4444",
                    bg='#7f1d1d',
                    cursor='hand2'
                )
                delete_label.pack(padx=14, pady=6)
                delete_label.bind("<Button-1>", lambda e, idx=i: remove_url(idx))

    def remove_url(index):
        loaded_urls = get_urls_from_file()
        if 0 <= index < len(loaded_urls):
            loaded_urls.pop(index)
            with open(urls_file, "w") as f:
                for u in loaded_urls:
                    f.write(u + "\n")
        refresh_list()

    refresh_list()
    frame.refresh_list = refresh_list

    return frame