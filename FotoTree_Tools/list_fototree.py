
import asyncio
import os
import json
from playwright.async_api import async_playwright

async def run():
    user_data_dir = r"C:\Users\PRAMANA VISUAL\AppData\Roaming\AutoYuPro\accounts\ipdpp\profile"
    
    async with async_playwright() as p:
        print("Launching browser with profile...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--no-sandbox"]
        )
        
        page = await context.new_page()
        
        # Monitor network responses
        fototree_data = []
        async def handle_response(response):
            if "tree" in response.url.lower() and "json" in response.headers.get("content-type", "").lower():
                try:
                    data = await response.json()
                    print(f"Captured JSON from {response.url}")
                    # Save for later analysis
                    with open("debug_tree_api.json", "a") as f:
                        f.write(json.dumps(data) + "\n")
                except:
                    pass

        page.on("response", handle_response)

        print("Navigating to FotoTree page...")
        await page.goto("https://www.fotoyu.com/tree", timeout=60000)
        await asyncio.sleep(10) # Wait for list to load
        
        print(f"Current URL: {page.url}")
        
        # Scan for potential list items in DOM
        print("Scanning for FotoTree items in DOM...")
        
        # Look for text that might be tree names
        # Usually they have a specific class or are inside certain containers
        selectors = [
            "div[class*='StyledItem']",
            "div[class*='Card']",
            "p[class*='Title']",
            "span[class*='Name']",
            "div[class*='TreeName']"
        ]
        
        all_text = []
        for selector in selectors:
            elements = await page.locator(selector).all_text_contents()
            all_text.extend([t.strip() for t in elements if t.strip()])
        
        # Also just get all paragraphs and spans to be safe
        more_text = await page.locator("p, span, h1, h2, h3").all_text_contents()
        all_text.extend([t.strip() for t in more_text if t.strip()])
        
        # Remove duplicates and noise
        unique_items = sorted(list(set(all_text)))
        
        print("\n--- DISCOVERED TEXT ITEMS ---")
        for item in unique_items:
            # Filter out very short or very long items, and common UI text
            if 3 < len(item) < 50 and item not in ["FotoTree", "Beranda", "Akun Saya", "Temukan Teman", "Cara Kerja", "Kerja Sama"]:
                print(f"- {item}")
        print("-----------------------------\n")
        
        # Save results to a file for the assistant to read
        with open("fototree_list_raw.txt", "w", encoding="utf-8") as f:
            for item in unique_items:
                f.write(f"{item}\n")

        await context.close()

if __name__ == "__main__":
    asyncio.run(run())
