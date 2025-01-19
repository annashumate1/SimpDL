import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk

def generate_links(base_link, num_pages):
    links = [base_link.rstrip("/")]
    for page_num in range(2, num_pages + 1):
        new_link = f"{base_link.rstrip('/')}/page-{page_num}"
        links.append(new_link)
    return links

def build_generate_links_frame(parent, urls_file, refresh_urls_func=None):
    frame = tb.Frame(parent, bootstyle="dark")

    title_label = tb.Label(frame, text="Generate Links", font=("Helvetica", 18, "bold"))
    title_label.pack(pady=10)

    row1 = tb.Frame(frame, bootstyle="dark")
    row1.pack(pady=5)
    tb.Label(row1, text="Base Link: ").pack(side="left")
    base_link_entry = tb.Entry(row1, width=40)
    base_link_entry.pack(side="left", padx=5)

    row2 = tb.Frame(frame, bootstyle="dark")
    row2.pack(pady=5)
    tb.Label(row2, text="Number of Pages: ").pack(side="left")
    pages_entry = tb.Entry(row2, width=10)
    pages_entry.pack(side="left", padx=5)

    status_label = tb.Label(frame, text="", font=("Helvetica", 11))
    status_label.pack(pady=5)

    def generate():
        base_link = base_link_entry.get().strip()
        try:
            num_pages = int(pages_entry.get())
            if num_pages < 2:
                raise ValueError("At least 2 pages required.")

            
            links = generate_links(base_link, num_pages)

            
            with open(urls_file, "w") as f:
                for link in links:
                    f.write(link + "\n")

            status_label.config(text="Generated links saved to URLs file.")

            
            if refresh_urls_func:
                refresh_urls_func()

        except ValueError as e:
            status_label.config(text=f"Error: {e}")

    generate_btn = tb.Button(frame, text="Generate", bootstyle="success outline", command=generate)
    generate_btn.pack(pady=10)

    return frame
