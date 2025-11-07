import os
import webbrowser
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *

from config_utils import build_config_frame, build_urls_frame
from downloader_hybrid import build_download_frame
from link_utils import build_generate_links_frame

def main_gui():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(script_dir, "config", "config.json")
    urls_file = os.path.join(script_dir, "config", "urls.txt")
    cookie_file = os.path.join(script_dir, "config", "manual_cookies.json")

    # Check if cookies exist, if not show setup wizard
    if not os.path.exists(cookie_file):
        show_cookie_setup_wizard(script_dir)
        # After wizard completes, check again
        if not os.path.exists(cookie_file):
            return  # User cancelled setup

    app = tb.Window(themename="darkly")
    app.title("SimpDL")
    
    def center_window(window, width=1450, height=900):
        window.geometry(f"{width}x{height}")
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(1200, 700)

    center_window(app, 1450, 900)

    icon_path = os.path.join(script_dir, "assets", "anna.png")
    if os.path.exists(icon_path):
        try:
            icon_img = tk.PhotoImage(file=icon_path)
            app.iconphoto(False, icon_img)
        except:
            pass

    # Remove default border
    app.configure(bg='#0a0e27')

    # Main container
    main_container = tk.Frame(app, bg='#0a0e27', relief='flat', bd=0)
    main_container.pack(fill="both", expand=True)

    # Sidebar
    sidebar = tk.Frame(main_container, bg='#0f1629', width=260, relief='flat', bd=0)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    # Logo section
    brand_frame = tk.Frame(sidebar, bg='#0f1629', relief='flat', bd=0)
    brand_frame.pack(fill="x", padx=30, pady=35)

    brand_icon = tk.Label(
        brand_frame,
        text="⚡",
        font=("SF Pro Display", 32),
        foreground="#6366f1",
        bg='#0f1629'
    )
    brand_icon.pack()

    brand_name = tk.Label(
        brand_frame,
        text="SimpDL",
        font=("SF Pro Display", 22, "bold"),
        foreground="#ffffff",
        bg='#0f1629'
    )
    brand_name.pack(pady=(8, 2))

    brand_tagline = tk.Label(
        brand_frame,
        text="Download Manager",
        font=("SF Pro Display", 10),
        foreground="#64748b",
        bg='#0f1629'
    )
    brand_tagline.pack()

    # Nav label
    nav_label = tk.Label(
        sidebar,
        text="MENU",
        font=("SF Pro Display", 9, "bold"),
        foreground="#475569",
        bg='#0f1629'
    )
    nav_label.pack(anchor="w", padx=30, pady=(25, 18))

    # Content area
    content_area = tk.Frame(main_container, bg='#0a0e27', relief='flat', bd=0)
    content_area.pack(side="left", fill="both", expand=True)

    # Top bar
    top_bar = tk.Frame(content_area, bg='#0f1629', height=75, relief='flat', bd=0)
    top_bar.pack(fill="x")
    top_bar.pack_propagate(False)

    breadcrumb_frame = tk.Frame(top_bar, bg='#0f1629', relief='flat', bd=0)
    breadcrumb_frame.pack(side="left", padx=40, pady=20)

    current_page_label = tk.Label(
        breadcrumb_frame,
        text="Dashboard",
        font=("SF Pro Display", 20, "bold"),
        foreground="#ffffff",
        bg='#0f1629'
    )
    current_page_label.pack(anchor="w")

    breadcrumb_sub = tk.Label(
        breadcrumb_frame,
        text="Welcome back",
        font=("SF Pro Display", 11),
        foreground="#64748b",
        bg='#0f1629'
    )
    breadcrumb_sub.pack(anchor="w", pady=(2, 0))

    # Status badge
    status_frame = tk.Frame(top_bar, bg='#0f1629', relief='flat', bd=0)
    status_frame.pack(side="right", padx=40)

    status_inner = tk.Frame(status_frame, bg='#134e4a', relief='flat', bd=0)
    status_inner.pack(padx=12, pady=6)

    status_badge = tk.Label(
        status_inner,
        text="●  Online",
        font=("SF Pro Display", 10, "bold"),
        foreground="#10b981",
        bg='#134e4a'
    )
    status_badge.pack()

    # Main content
    content_container = tk.Frame(content_area, bg='#0a0e27', relief='flat', bd=0)
    content_container.pack(fill="both", expand=True, padx=35, pady=30)

    pages = {}
    active_button = [None]

    def show_page(page_name, page_title, page_subtitle, button):
        for page in pages.values():
            page.pack_forget()
        pages[page_name].pack(fill="both", expand=True)
        
        current_page_label.config(text=page_title)
        breadcrumb_sub.config(text=page_subtitle)
        
        if active_button[0]:
            active_button[0]['bg'] = '#0f1629'
            active_button[0]['fg'] = '#94a3b8'
        button['bg'] = '#312e81'
        button['fg'] = '#6366f1'
        active_button[0] = button

    # HOME PAGE
    home_page = tk.Frame(content_container, bg='#0a0e27', relief='flat', bd=0)

    # Hero
    hero_card = tk.Frame(home_page, bg='#1e1b4b', relief='flat', bd=0)
    hero_card.pack(fill="x", pady=(0, 30))

    hero_content = tk.Frame(hero_card, bg='#1e1b4b', relief='flat', bd=0)
    hero_content.pack(padx=60, pady=50)

    hero_title = tk.Label(
        hero_content,
        text="Advanced Download Engine",
        font=("SF Pro Display", 36, "bold"),
        foreground="#ffffff",
        bg='#1e1b4b'
    )
    hero_title.pack(anchor="w")

    hero_subtitle = tk.Label(
        hero_content,
        text="Intelligent hybrid architecture combining browser automation with high-speed HTTP requests",
        font=("SF Pro Display", 13),
        foreground="#94a3b8",
        bg='#1e1b4b'
    )
    hero_subtitle.pack(anchor="w", pady=(12, 30))

    cta_frame = tk.Frame(hero_content, bg='#1e1b4b', relief='flat', bd=0)
    cta_frame.pack(anchor="w")

    def start_quick():
        show_page("download", "Downloads", "Execute and monitor downloads", nav_buttons[-2])

    start_btn_frame = tk.Frame(cta_frame, bg='#6366f1', relief='flat', bd=0, cursor='hand2')
    start_btn_frame.pack(side="left", padx=(0, 12))
    start_btn_frame.bind("<Button-1>", lambda e: start_quick())

    start_btn = tk.Label(
        start_btn_frame,
        text="Start Downloading",
        font=("SF Pro Display", 11, "bold"),
        foreground="#ffffff",
        bg='#6366f1',
        cursor='hand2'
    )
    start_btn.pack(padx=24, pady=12)
    start_btn.bind("<Button-1>", lambda e: start_quick())

    docs_btn_frame = tk.Frame(cta_frame, bg='#1e293b', relief='flat', bd=0, cursor='hand2')
    docs_btn_frame.pack(side="left")
    docs_btn_frame.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/annashumate1/SimpDL"))

    docs_btn = tk.Label(
        docs_btn_frame,
        text="View on GitHub",
        font=("SF Pro Display", 11, "bold"),
        foreground="#94a3b8",
        bg='#1e293b',
        cursor='hand2'
    )
    docs_btn.pack(padx=24, pady=12)
    docs_btn.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/annashumate1/SimpDL"))

    # Stats
    stats_row = tk.Frame(home_page, bg='#0a0e27', relief='flat', bd=0)
    stats_row.pack(fill="x", pady=(0, 35))

    stats_data = [
        ("Speed", "Hybrid Mode", "#8b5cf6"),
        ("Auth", "Cookie-Based", "#ec4899"),
        ("Success", "99.9%", "#10b981")
    ]

    for i, (label, value, color) in enumerate(stats_data):
        stat_card = tk.Frame(stats_row, bg='#1e293b', relief='flat', bd=0)
        stat_card.pack(side="left", fill="both", expand=True, padx=(0, 12) if i < 2 else 0)

        stat_content = tk.Frame(stat_card, bg='#1e293b', relief='flat', bd=0)
        stat_content.pack(padx=30, pady=28)

        stat_label_widget = tk.Label(
            stat_content,
            text=label,
            font=("SF Pro Display", 10),
            foreground="#64748b",
            bg='#1e293b'
        )
        stat_label_widget.pack(anchor="w")

        stat_value_widget = tk.Label(
            stat_content,
            text=value,
            font=("SF Pro Display", 26, "bold"),
            foreground=color,
            bg='#1e293b'
        )
        stat_value_widget.pack(anchor="w", pady=(8, 0))

    # Features
    features_title = tk.Label(
        home_page,
        text="Features",
        font=("SF Pro Display", 18, "bold"),
        foreground="#ffffff",
        bg='#0a0e27'
    )
    features_title.pack(anchor="w", pady=(0, 20))

    features_grid = tk.Frame(home_page, bg='#0a0e27', relief='flat', bd=0)
    features_grid.pack(fill="both", expand=True)

    features = [
        ("🚀", "Hybrid Engine", "Browser + HTTP for optimal performance", "#6366f1"),
        ("🔒", "Secure Auth", "Cookie-based authentication", "#8b5cf6"),
        ("⚡", "Multi-Thread", "Parallel processing for speed", "#ec4899"),
        ("📊", "Live Stats", "Real-time monitoring", "#10b981"),
    ]

    for i, (icon, title, desc, color) in enumerate(features):
        row = i // 2
        col = i % 2
        
        feature_card = tk.Frame(features_grid, bg='#1e293b', relief='flat', bd=0)
        feature_card.grid(row=row, column=col, sticky="nsew", 
                         padx=(0, 12) if col == 0 else 0, 
                         pady=(0, 12) if row < 1 else 0)

        feature_content = tk.Frame(feature_card, bg='#1e293b', relief='flat', bd=0)
        feature_content.pack(padx=30, pady=28, fill="both", expand=True)

        icon_label = tk.Label(
            feature_content,
            text=icon,
            font=("SF Pro Display", 32),
            foreground=color,
            bg='#1e293b'
        )
        icon_label.pack(anchor="w")

        title_label = tk.Label(
            feature_content,
            text=title,
            font=("SF Pro Display", 15, "bold"),
            foreground="#ffffff",
            bg='#1e293b'
        )
        title_label.pack(anchor="w", pady=(12, 6))

        desc_label = tk.Label(
            feature_content,
            text=desc,
            font=("SF Pro Display", 11),
            foreground="#64748b",
            bg='#1e293b',
            wraplength=280
        )
        desc_label.pack(anchor="w")

    features_grid.columnconfigure(0, weight=1)
    features_grid.columnconfigure(1, weight=1)

    pages["home"] = home_page

    # Build other pages
    config_page = build_config_frame(content_container, config_path)
    pages["config"] = config_page

    urls_page = build_urls_frame(content_container, urls_file)
    pages["urls"] = urls_page

    def refresh_urls_list():
        urls_page.refresh_list()

    generate_page = build_generate_links_frame(content_container, urls_file, refresh_urls_list)
    pages["generate"] = generate_page

    download_page = build_download_frame(content_container, config_path, urls_file)
    pages["download"] = download_page

    # Navigation buttons
    nav_items = [
        ("Dashboard", "Welcome back", "home", "🏠"),
        ("Settings", "Configure preferences", "config", "⚙️"),
        ("Queue", "Manage URLs", "urls", "📋"),
        ("Generator", "Create links", "generate", "✨"),
        ("Downloads", "Execute downloads", "download", "⬇️"),
    ]

    nav_buttons = []
    for title, subtitle, page_key, icon in nav_items:
        btn = tk.Label(
            sidebar,
            text=f"{icon}  {title}",
            font=("SF Pro Display", 11, "bold"),
            foreground="#94a3b8",
            bg='#0f1629',
            cursor='hand2',
            anchor='w',
            padx=20,
            pady=14
        )
        btn.pack(fill="x", padx=18, pady=2)
        btn.bind("<Button-1>", lambda e, t=title, s=subtitle, pk=page_key, b=btn: show_page(pk, t, s, b))
        nav_buttons.append(btn)

    # Spacer
    tk.Frame(sidebar, bg='#0f1629', relief='flat', bd=0).pack(expand=True)

    # Footer
    footer_frame = tk.Frame(sidebar, bg='#0f1629', relief='flat', bd=0)
    footer_frame.pack(fill="x", padx=30, pady=(0, 25))

    github_link = tk.Label(
        footer_frame,
        text="GitHub →",
        font=("SF Pro Display", 10, "bold"),
        foreground="#6366f1",
        bg='#0f1629',
        cursor='hand2'
    )
    github_link.pack(anchor="w", pady=(0, 15))
    github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/annashumate1/SimpDL"))

    exit_frame = tk.Frame(footer_frame, bg='#7f1d1d', relief='flat', bd=0, cursor='hand2')
    exit_frame.pack(fill="x")
    exit_frame.bind("<Button-1>", lambda e: app.quit())

    exit_label = tk.Label(
        exit_frame,
        text="Exit Application",
        font=("SF Pro Display", 10, "bold"),
        foreground="#ef4444",
        bg='#7f1d1d',
        cursor='hand2'
    )
    exit_label.pack(pady=10)
    exit_label.bind("<Button-1>", lambda e: app.quit())

    # Show home
    show_page("home", "Dashboard", "Welcome back", nav_buttons[0])

    app.mainloop()

if __name__ == "__main__":
    main_gui()