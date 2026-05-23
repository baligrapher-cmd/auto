
import os
import sys
import time
from playwright.sync_api import sync_playwright

def check_session():
    user_data_dir = r"c:\Users\PRAMANA VISUAL\AppData\Roaming\AutoYuPro\accounts\1\profile"
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True
        )
        page = browser.pages[0]
        page.goto("https://www.fotoyu.com/upload")
        time.sleep(5)
        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        
        # Check if upload container is visible
        is_logged_in = page.locator("div[class*='StyledUploadPhotoContainer']").first.is_visible()
        print(f"Logged In: {is_logged_in}")
        browser.close()

if __name__ == "__main__":
    check_session()
