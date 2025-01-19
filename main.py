import os
import webbrowser
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog



from config_utils import build_config_frame, build_urls_frame
from downloader import build_download_frame
from link_utils import build_generate_links_frame
from login_utils import login_to_simpcity
from image_utils import is_valid_image, get_image_src

def main_gui():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(script_dir, "config", "config.json")
    urls_file = os.path.join(script_dir, "config", "urls.txt")

    
    app = tb.Window(themename="darkly")  
    app.title("SimpDL")

    def center_window(window, width=900, height=600):
        """
        Manually center a Tk window on the screen at the given width/height.
        """
        window.geometry(f"{width}x{height}")
        window.update_idletasks() 

        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        window.geometry(f"{width}x{height}+{x}+{y}")

    
    center_window(app, 900, 600)

    icon_path = os.path.join(script_dir, "assets", "anna.png")
    icon_img = tk.PhotoImage(file=icon_path)
    app.iconphoto(False, icon_img)

    
    outer_frame = tb.Frame(app, bootstyle="secondary")
    outer_frame.pack(fill="both", expand=True)

    sidebar_frame = tb.Frame(outer_frame, bootstyle="primary", padding=10)
    sidebar_frame.pack(side="left", fill="y")

    content_frame = tb.Frame(outer_frame, bootstyle="secondary")
    content_frame.pack(side="left", fill="both", expand=True)

    pages = {}

    def show_page(page_name):
        for page in pages.values():
            page.pack_forget()
        pages[page_name].pack(fill="both", expand=True)

    
    home_page = tb.Frame(content_frame, bootstyle="dark")
    home_title = tb.Label(home_page, text="Welcome to SimpDL", font=("Helvetica", 24, "bold"))
    home_title.pack(pady=30)

    
    desc_frame = tb.Frame(home_page, bootstyle="dark")
    desc_frame.pack(pady=20)

    
    line_label = tb.Label(
        desc_frame,
        text=(
            "This is a tool to download images from SimpCity.\n"
            "For help or more information, contact me on Telegram:"
        ),
        font=("Helvetica", 16)
    )
    line_label.pack(pady=(0, 10))

    
    def open_telegram(event):
        webbrowser.open_new("https://t.me/annashumatelover")

    
    link_label = tb.Label(
        desc_frame,
        text="https://t.me/annashumatelover",
        font=("Helvetica", 16, "underline"),
        foreground="blue",
        cursor="hand2"
    )
    link_label.pack()

    
    link_label.bind("<Button-1>", open_telegram)

    pages["home"] = home_page

   
    config_page = build_config_frame(content_frame, config_path)
    pages["config"] = config_page

    urls_page = build_urls_frame(content_frame, urls_file)
    pages["urls"] = urls_page

    def refresh_urls_list():
        urls_page.refresh_list()

    generate_page = build_generate_links_frame(content_frame, urls_file, refresh_urls_list)
    pages["generate"] = generate_page

    download_page = build_download_frame(content_frame, config_path, urls_file)
    pages["download"] = download_page

    
    style_for_button = "success-outline"

    tb.Button(
        sidebar_frame,
        text="Home",
        bootstyle=style_for_button,
        command=lambda: show_page("home")
    ).pack(pady=5, fill="x")

    tb.Button(
        sidebar_frame,
        text="Modify Config",
        bootstyle=style_for_button,
        command=lambda: show_page("config")
    ).pack(pady=5, fill="x")

    tb.Button(
        sidebar_frame,
        text="Change URL File",
        bootstyle=style_for_button,
        command=lambda: show_page("urls")
    ).pack(pady=5, fill="x")

    tb.Button(
        sidebar_frame,
        text="Generate Links",
        bootstyle=style_for_button,
        command=lambda: show_page("generate")
    ).pack(pady=5, fill="x")

    tb.Button(
        sidebar_frame,
        text="Download Images",
        bootstyle=style_for_button,
        command=lambda: show_page("download")
    ).pack(pady=5, fill="x")

    tb.Button(
        sidebar_frame,
        text="Exit",
        bootstyle="danger",
        command=app.quit
    ).pack(pady=(40, 10), fill="x")

    
    show_page("home")

    app.mainloop()

if __name__ == "__main__":
    main_gui()
