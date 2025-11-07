"""
Link Generation Utilities
Generate paginated URLs for forum threads.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk

def generate_links(base_link, num_pages):
    """Generate paginated links from base URL."""
    links = []
    for page_num in range(1, num_pages + 1):
        if page_num == 1:
            links.append(f"{base_link.rstrip('/')}/page-1")
        else:
            links.append(f"{base_link.rstrip('/')}/page-{page_num}")
    return links

def build_generate_links_frame(parent, urls_file, refresh_urls_func=None):
    """Modern link generator interface."""
    frame = tb.Frame(parent, bootstyle="dark")

    # Header
    header_frame = tb.Frame(frame, bootstyle="dark")
    header_frame.pack(fill="x", pady=(0, 20))

    title_label = tb.Label(
        header_frame,
        text="✨ Link Generator",
        font=("Helvetica", 24, "bold")
    )
    title_label.pack(anchor="w")

    subtitle_label = tb.Label(
        header_frame,
        text="Automatically generate paginated URLs",
        font=("Helvetica", 11),
        bootstyle="secondary"
    )
    subtitle_label.pack(anchor="w", pady=(5, 0))

    # Input card
    input_card = tb.Frame(frame, bootstyle="secondary", padding=30)
    input_card.pack(fill="both", expand=True)

    # Base URL input
    url_frame = tb.LabelFrame(
        input_card,
        text="🔗 Thread URL",
        bootstyle="primary",
        padding=20
    )
    url_frame.pack(fill="x", pady=(0, 20))

    url_label = tb.Label(
        url_frame,
        text="Enter the base thread URL (without page number):",
        font=("Helvetica", 10),
        bootstyle="secondary"
    )
    url_label.pack(anchor="w", pady=(0, 10))

    base_link_entry = tb.Entry(url_frame, font=("Helvetica", 11))
    base_link_entry.pack(fill="x")
    base_link_entry.insert(0, "https://simpcity.cr/threads/example.12345")

    # Page count input
    pages_frame = tb.LabelFrame(
        input_card,
        text="📄 Number of Pages",
        bootstyle="info",
        padding=20
    )
    pages_frame.pack(fill="x", pady=(0, 20))

    pages_label = tb.Label(
        pages_frame,
        text="How many pages to generate?",
        font=("Helvetica", 10),
        bootstyle="secondary"
    )
    pages_label.pack(anchor="w", pady=(0, 10))

    pages_spinbox = tb.Spinbox(
        pages_frame,
        from_=1,
        to=100,
        font=("Helvetica", 11),
        bootstyle="info"
    )
    pages_spinbox.pack(fill="x")
    pages_spinbox.set(5)

    # Status label
    status_label = tb.Label(
        input_card,
        text="",
        font=("Helvetica", 11)
    )
    status_label.pack(pady=(0, 20))

    # Generate button
    def generate():
        base_link = base_link_entry.get().strip()
        
        if not base_link:
            status_label.config(
                text="⚠️ Please enter a valid URL",
                bootstyle="warning"
            )
            return
        
        try:
            num_pages = int(pages_spinbox.get())
            if num_pages < 1:
                raise ValueError("Must be at least 1 page")

            links = generate_links(base_link, num_pages)

            with open(urls_file, "w") as f:
                for link in links:
                    f.write(link + "\n")

            status_label.config(
                text=f"✓ Successfully generated {num_pages} URLs!",
                bootstyle="success"
            )

            if refresh_urls_func:
                refresh_urls_func()

        except ValueError as e:
            status_label.config(
                text=f"✗ Error: {str(e)}",
                bootstyle="danger"
            )

    generate_btn = tb.Button(
        input_card,
        text="✨ Generate Links",
        bootstyle="success",
        command=generate
    )
    generate_btn.pack(pady=(0, 20), ipadx=20, ipady=10)

    # Example section
    example_frame = tb.LabelFrame(
        input_card,
        text="💡 Example",
        bootstyle="light",
        padding=20
    )
    example_frame.pack(fill="x")

    example_text = """
Base URL: https://simpcity.cr/threads/example.12345
Pages: 3

Will generate:
  → https://simpcity.cr/threads/example.12345/page-1
  → https://simpcity.cr/threads/example.12345/page-2
  → https://simpcity.cr/threads/example.12345/page-3
    """

    example_label = tb.Label(
        example_frame,
        text=example_text,
        font=("Courier", 10),
        bootstyle="secondary",
        justify="left"
    )
    example_label.pack()

    return frame