import os
import json
import time
import re
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

def force_setup(username, password):
    print(f"Starting FORCE Auto-Setup for ULTRA (User: {username})")
    
    from core.license import get_app_data_dir_by_name
    tracker_dir = os.path.join(get_app_data_dir_by_name("AutoYuUltra"), "trackers")
    os.makedirs(tracker_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        print("Navigating to login page...")
        page.goto("https://www.fotoyu.com/login", wait_until="networkidle")
        
        try:
            page.wait_for_selector("input[type='text'], input[type='email'], input[name='account']", timeout=20000)
            
            # Target specific fields
            user_field = page.query_selector("input[type='text'], input[type='email'], input[name='account']")
            pass_field = page.query_selector("input[type='password']")
            
            if user_field and pass_field:
                user_field.fill(username)
                pass_field.fill(password)
                print(f"Filled fields: User={username}, Pass=******")
            else:
                print("Could not find both login fields. Trying fallback...")
                inputs = page.query_selector_all("input")
                text_inputs = [i for i in inputs if i.get_attribute("type") in ["text", "email", "password"]]
                if len(text_inputs) >= 2:
                    text_inputs[0].fill(username)
                    text_inputs[1].fill(password)
                    print("Filled using fallback.")
                else:
                    print(f"Only found {len(text_inputs)} usable inputs.")
                    browser.close()
                    return

            login_btn = page.query_selector("button[type='submit'], button:has-text('Masuk'), div[role='button']:has-text('Masuk')")
            if login_btn:
                login_btn.click()
            else:
                page.keyboard.press("Enter")
            
            page.wait_for_url(re.compile(r"/(profile|home|dashboard|upload)"), timeout=30000)
            print(f"Login Successful! Current URL: {page.url}")
        except Exception as e:
            print(f"❌ Login failed: {e}")
            browser.close()
            return

        print("Navigating to upload page...")
        page.goto("https://www.fotoyu.com/upload", wait_until="networkidle")
        
        captured = {"token": None, "headers": None, "body": None, "url": None}

        def handle_request(request):
            if ("/creations" in request.url or "/link" in request.url) and request.method == "POST":
                print(f"🎯 Captured API Request: {request.url}")
                captured["url"] = request.url
                captured["headers"] = request.headers
                captured["token"] = request.headers.get("authorization")
                captured["body"] = request.post_data

        page.on("request", handle_request)

        try:
            # Select "Foto" mode
            page.wait_for_selector("div:has-text('Foto')", timeout=10000)
            page.click("div:has-text('Foto')")
            
            # Dummy file
            dummy_file = r"D:\demo\test.jpg"
            if not os.path.exists(dummy_file):
                from PIL import Image
                os.makedirs(os.path.dirname(dummy_file), exist_ok=True)
                img = Image.new('RGB', (1, 1), color='black')
                img.save(dummy_file)
            
            # Upload
            file_input = page.wait_for_selector("input[type='file']", timeout=10000)
            file_input.set_input_files(dummy_file)
            print("📤 File uploaded.")
            
            # Wait for form
            page.wait_for_selector("textarea", timeout=20000)
            page.fill("input[placeholder*='Harga']", "9000")
            page.fill("textarea", "denpasar")
            
            # Location
            print("Selecting location...")
            page.click("input[placeholder*='Pilih Lokasi']")
            page.fill("input[placeholder*='Cari Lokasi']", "denpasar")
            page.wait_for_timeout(4000)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            
            # Submit
            print("🚀 Submitting...")
            submit_btn = page.query_selector("button:has-text('Unggah'), div[role='button']:has-text('Unggah')")
            if submit_btn:
                submit_btn.click()
            else:
                page.keyboard.press("Enter")
            
            # Wait for capture
            for _ in range(30):
                if captured["token"]: break
                time.sleep(1)
            
            if captured["token"]:
                print("✅ SUCCESS!")
                with open(os.path.join(tracker_dir, "api_token.txt"), "w") as f: f.write(captured["token"])
                with open(os.path.join(tracker_dir, "api_headers.json"), "w") as f: json.dump(captured["headers"], f, indent=2)
                
                if captured["body"]:
                    matches = re.findall(r'name="([^"]+)"', captured["body"])
                    schema = {"url": captured["url"], "file_field": "file", "fields": {m: "" for m in matches if m != "file"}}
                    with open(os.path.join(tracker_dir, "api_ultra_schema.json"), "w") as f: json.dump(schema, f, indent=2)
                    
                    metadata = {}
                    for m in matches:
                        pattern = f'name="{m}"\r\n\r\n([^\r\n]*)'
                        val_match = re.search(pattern, captured["body"])
                        if val_match: metadata[m] = val_match.group(1).strip()
                    
                    clean_meta = {}
                    if "tree_id" in metadata: clean_meta["tree_id"] = metadata["tree_id"]
                    if "location_id" in metadata: clean_meta["location_id"] = metadata["location_id"]
                    with open(os.path.join(tracker_dir, "api_metadata.json"), "w") as f: json.dump(clean_meta, f, indent=2)
                    print(f"✅ Metadata: {clean_meta}")
            else:
                print("❌ FAILED capture.")

        except Exception as e:
            print(f"❌ Error: {e}")

        browser.close()

if __name__ == "__main__":
    force_setup("autoyu", "autoyu123")
