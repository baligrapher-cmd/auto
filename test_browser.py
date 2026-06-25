
import sys
import os
from core.playwright_runtime import configure_playwright_browser_path, find_executable, get_playwright_browser_candidates
from playwright.sync_api import sync_playwright

print("=== Testing Playwright Browser Setup ===")
print(f"Python path: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print()

print("1. Checking internal browser candidates...")
candidates = get_playwright_browser_candidates()
for i, candidate in enumerate(candidates, 1):
    print(f"   Candidate {i}: {candidate}")
    exists = os.path.exists(candidate)
    print(f"      Exists: {exists}")
    if exists:
        print(f"      Contents: {os.listdir(candidate)[:10] if len(os.listdir(candidate)) > 10 else os.listdir(candidate)}")
print()

print("2. Checking configure_playwright_browser_path...")
pw_path = configure_playwright_browser_path()
print(f"   Result: {pw_path}")
print(f"   PLAYWRIGHT_BROWSERS_PATH env var: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
print()

print("3. Checking find_executable...")
exe = find_executable()
print(f"   Result: {exe}")
print()

print("4. Testing Playwright launch...")
try:
    with sync_playwright() as p:
        print("   Playwright initialized!")
        
        # Test 1: Try default
        print("   Testing default chromium...")
        try:
            browser = p.chromium.launch(headless=True)
            print("   ✅ Success! Default Chromium found")
            browser.close()
        except Exception as e:
            print(f"   ❌ Failed: {type(e).__name__}: {e}")
        
        # Test 2: Try chrome channel
        print("\n   Testing chrome channel...")
        try:
            browser = p.chromium.launch(headless=True, channel="chrome")
            print("   ✅ Success! Chrome found")
            browser.close()
        except Exception as e:
            print(f"   ❌ Failed: {type(e).__name__}: {e}")
        
        # Test 3: Try msedge channel
        print("\n   Testing msedge channel...")
        try:
            browser = p.chromium.launch(headless=True, channel="msedge")
            print("   ✅ Success! Edge found")
            browser.close()
        except Exception as e:
            print(f"   ❌ Failed: {type(e).__name__}: {e}")
            
except Exception as e:
    print(f"❌ Playwright init failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
