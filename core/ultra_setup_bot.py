import os
import json
import time
import re
from playwright.sync_api import sync_playwright

def run_setup(username, password):
    print(f"Starting Auto-Setup for ULTRA (User: {username})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()

        print("Navigating to login page...")
        page.goto("https://www.fotoyu.com/login", wait_until="networkidle")
        
        try:
            page.wait_for_selector("input[type='text'], input[type='email']", timeout=10000)
            page.fill("input[type='text'], input[type='email']", username)
            page.fill("input[type='password']", password)
            
            login_btn = page.query_selector("button[type='submit'], button:has-text('Masuk')")
            if login_btn:
                login_btn.click()
            else:
                page.keyboard.press("Enter")
            
            page.wait_for_url("**/profile**", timeout=30000)
            print("Login Successful!")
        except Exception as e:
            print(f"Login failed: {e}")
            browser.close()
            return

        print("Navigating to upload page...")
        page.goto("https://www.fotoyu.com/upload", wait_until="networkidle")
        
        captured = {"token": None, "headers": None, "body": None, "url": None}

        def handle_request(request):
            if ("/creations" in request.url) and request.method == "POST":
                print(f"Intercepted API Request: {request.url}")
                captured["url"] = request.url
                captured["headers"] = request.headers
                captured["token"] = request.headers.get("authorization")
                captured["body"] = request.post_data

        page.on("request", handle_request)

        try:
            page.click("div:has-text('Foto')")
            
            dummy_file = r"D:\demo\test.jpg"
            file_input = page.wait_for_selector("input[type='file']", timeout=10000)
            file_input.set_input_files(dummy_file)
            print("Dummy file uploaded.")
            
            page.wait_for_selector("textarea", timeout=20000)
            page.fill("input[placeholder*='Harga']", "9000")
            page.fill("textarea", "denpasar")
            
            print("Selecting location...")
            page.click("input[placeholder*='Pilih Lokasi']")
            page.fill("input[placeholder*='Cari Lokasi']", "denpasar")
            page.wait_for_timeout(3000)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            
            print("Submitting...")
            submit_btn = page.query_selector("button:has-text('Unggah'), div[role='button']:has-text('Unggah')")
            submit_btn.click()
            
            for _ in range(20):
                if captured["token"]: break
                time.sleep(1)
            
            if captured["token"]:
                print("Metadata and Token Captured!")
                from core.license import get_app_data_dir_by_name
                tracker_dir = os.path.join(get_app_data_dir_by_name("AutoYuUltra"), "trackers")
                os.makedirs(tracker_dir, exist_ok=True)
                
                with open(os.path.join(tracker_dir, "api_token.txt"), "w") as f: f.write(captured["token"])
                with open(os.path.join(tracker_dir, "api_headers.json"), "w") as f: json.dump(captured["headers"], f, indent=2)
                
                if captured["body"]:
                    matches = re.findall(r'name="([^"]+)"', captured["body"])
                    schema = {"url": captured["url"], "file_field": "file", "fields": {m: "" for m in matches if m != "file"}}
                    with open(os.path.join(tracker_dir, "api_ultra_schema.json"), "w") as f: json.dump(schema, f, indent=2)
                    
                    metadata = {}
                    for m in matches:
                        pattern = f'name="{m}"\r\n\r\n([^\r\n]+)'
                        val_match = re.search(pattern, captured["body"])
                        if val_match:
                            metadata[m] = val_match.group(1)
                    
                    clean_meta = {}
                    if "tree_id" in metadata: clean_meta["tree_id"] = metadata["tree_id"]
                    if "location_id" in metadata: clean_meta["location_id"] = metadata["location_id"]
                    
                    with open(os.path.join(tracker_dir, "api_metadata.json"), "w") as f: json.dump(clean_meta, f, indent=2)
                    print(f"Metadata saved: {clean_meta}")

            else:
                print("Failed to capture request.")

        except Exception as e:
            print(f"Error: {e}")

        browser.close()

if __name__ == "__main__":
    run_setup("autoyu", "autoyu123")
