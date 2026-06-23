#!/usr/bin/env python3

import sys
import os
import platform

print("=" * 60)
print("🚀 AUTOYU SMOKE TEST")
print("=" * 60)
print()

# --- TEST 1: System Info ---
print("📊 1. System Information")
print("-" * 40)
print(f"OS: {platform.system()} {platform.release()}")
print(f"Architecture: {platform.machine()}")
print(f"Python: {sys.version}")
print(f"Frozen (PyInstaller): {getattr(sys, 'frozen', False)}")
print()

# --- TEST 2: Import Required Modules ---
print("📦 2. Testing Module Imports")
print("-" * 40)
modules_to_test = [
    "PySide6",
    "playwright",
    "watchdog",
    "requests",
    "cryptography",
    "PIL",
    "psutil"
]

all_imports_ok = True
for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")
        all_imports_ok = False
print()

# --- TEST 3: Browser Configuration ---
print("🌐 3. Testing Internal Browser")
print("-" * 40)
try:
    from core.playwright_runtime import (
        configure_playwright_browser_path,
        find_executable,
        get_playwright_browser_candidates
    )
    
    print("Checking browser candidates...")
    candidates = get_playwright_browser_candidates()
    for i, candidate in enumerate(candidates, 1):
        exists = os.path.exists(candidate)
        print(f"   Candidate {i}: {candidate} {'✅' if exists else '❌'}")
    
    print("\nConfiguring browser path...")
    browser_path = configure_playwright_browser_path()
    print(f"   Browser path configured: {browser_path}")
    
    print("\nFinding executable...")
    exe_path = find_executable()
    if exe_path and os.path.isfile(exe_path):
        print(f"✅ Found executable: {exe_path}")
        exe_exists = True
    else:
        print(f"❌ Executable not found")
        exe_exists = False
        
except Exception as e:
    print(f"❌ Browser test failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    exe_exists = False
print()

# --- TEST 4: Playwright Launch Test ---
print("🎮 4. Testing Playwright Launch")
print("-" * 40)
try:
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        print("✅ Playwright initialized")
        
        if exe_exists:
            print("\nTesting with internal browser...")
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("about:blank")
                title = page.title()
                print(f"✅ Success! Page title: {title}")
                browser.close()
                playwright_ok = True
            except Exception as e:
                print(f"❌ Failed: {type(e).__name__}: {e}")
                playwright_ok = False
        else:
            print("⚠️ Skipping (no internal browser found)")
            playwright_ok = False
            
except Exception as e:
    print(f"❌ Playwright test failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    playwright_ok = False
print()

# --- FINAL RESULTS ---
print("=" * 60)
print("📋 SMOKE TEST RESULTS")
print("=" * 60)
print(f"✅ Imports: {'PASS' if all_imports_ok else 'FAIL'}")
print(f"✅ Browser Found: {'PASS' if exe_exists else 'FAIL'}")
print(f"✅ Playwright: {'PASS' if playwright_ok else 'FAIL'}")
print()

if all_imports_ok and exe_exists and playwright_ok:
    print("🎉 ALL TESTS PASSED - APPLICATION SHOULD WORK!")
    sys.exit(0)
else:
    print("⚠️ Some tests failed - please check the errors above")
    sys.exit(1)
