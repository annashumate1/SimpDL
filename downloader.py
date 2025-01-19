import os
import time
import json
import requests
import tkinter as tk
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from selenium import webdriver
from selenium.webdriver.common.by import By

from image_utils import get_image_src, is_valid_image
from login_utils import login_to_simpcity

def build_download_frame(parent, config_path, urls_file):
    """
    Returns a Frame that downloads images in a background thread.
    The output folder name is derived from the portion after 'threads/' 
    in the first URL.
    """
    frame = tb.Frame(parent, bootstyle="dark")

    title = tb.Label(frame, text="Download Images", font=("Helvetica", 18, "bold"))
    title.pack(pady=10)

   
    progress_label = tb.Label(frame, text="Progress: Not started", font=("Helvetica", 12))
    progress_label.pack(pady=5)

    
    progress_bar = tb.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
    progress_bar.pack(pady=5)

    
    log_text = tk.Text(frame, height=15, width=60, bg="#282828", fg="#1DB954", wrap="word")
    log_text.pack(pady=10, fill="both", expand=True)

    
    download_in_progress = [False]

    def log_message(msg):
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)

    def start_download():
        """Triggered by the button. Spawns a background thread for the main download."""
        if download_in_progress[0]:
            return  

        download_in_progress[0] = True
        start_button.config(state="disabled")
        log_message("Starting download...")

        threading.Thread(target=run_download, daemon=True).start()

    def run_download():
        """
        The main download logic, running in a background thread 
        to keep the GUI responsive.
        """
        try:
            
            with open(config_path, "r") as f:
                config = json.load(f)
            username = config.get("username", "")
            password = config.get("password", "")
            output_directory = config.get("output_directory", "")

            
            with open(urls_file, "r") as file:
                urls = [line.strip() for line in file if line.strip()]

            if not urls:
                log_message("No URLs found. Please add URLs first.")
                return

            
            folder_name = get_folder_name(urls[0])
            combined_output_dir = os.path.join(output_directory, folder_name)
            if not os.path.exists(combined_output_dir):
                os.makedirs(combined_output_dir)

            
            driver = webdriver.Chrome()
            try:
                driver.get("https://simpcity.su/login/")
                time.sleep(3)
                login_to_simpcity(driver, username, password)
                log_message("Logged in successfully.")

                total_pages = len(urls)
                current_page = 0

                for url in urls:
                    current_page += 1
                    driver.get(url)
                    time.sleep(3)

                    images = driver.find_elements(By.TAG_NAME, "img")
                    log_message(f"[Page {current_page}/{total_pages}] Found {len(images)} images. Starting download...")

                    total_images = len(images)
                    for idx, img in enumerate(images):
                        try:
                            img_url = get_image_src(driver, img)
                            if img_url and is_valid_image(img_url):
                                response = requests.get(img_url, stream=True)
                                if response.status_code == 200:
                                    image_path = os.path.join(
                                        combined_output_dir,
                                        f"image_{len(os.listdir(combined_output_dir)) + 1}.jpg"
                                    )
                                    with open(image_path, "wb") as file_out:
                                        for chunk in response.iter_content(1024):
                                            file_out.write(chunk)
                                    log_message(f"Downloaded: {image_path}")
                            else:
                                log_message(f"Skipped invalid image: {img_url}")
                        except Exception as ex:
                            log_message(f"Error downloading image: {ex}")

                        
                        progress = ((idx + 1) / total_images) * 100 if total_images > 0 else 0
                        frame.after(0, lambda val=progress: progress_bar.configure(value=val))
                        status_text = page_status(idx + 1, total_images, current_page, total_pages)
                        frame.after(0, lambda st=status_text: progress_label.config(text=st))

                log_message("All pages downloaded successfully.")

            finally:
                driver.quit()

        except Exception as e:
            log_message(f"Error: {str(e)}")

        finally:
            
            download_in_progress[0] = False
            frame.after(0, lambda: start_button.config(state="normal"))

    def page_status(current_img, total_img, current_page, total_pages):
        return f"Page {current_page}/{total_pages}: {current_img}/{total_img} images"

    def get_folder_name(url):
        """
        Extract the portion after 'threads/' from the URL.
        e.g., 
          https://simpcity.su/threads/nottrebeca_.180370/page-2 -> 'nottrebeca_.180370'
          https://simpcity.su/threads/something-else.12345 -> 'something-else.12345'
        If 'threads' is not found, default to 'default_folder'.
        """
        
        url = url.rstrip('/')
        parts = url.split('/')
        if 'threads' in parts:
            idx = parts.index('threads')
            if idx + 1 < len(parts):
                return parts[idx + 1]
        
        return "default_folder"

    start_button = tb.Button(frame, text="Start Download", bootstyle="success outline", command=start_download)
    start_button.pack(pady=10)

    return frame
