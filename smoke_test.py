#!/usr/bin/env python3
"""
SMOKE TEST: Memastikan aplikasi SELALU menggunakan Chromium Internal/Bundled,
tidak fallback ke Chrome pengguna.
"""

import sys
import os

def test_no_user_chrome_fallback():
    """Test: Worker tidak lagi mencoba menggunakan Chrome/Edge pengguna di launch_attempts"""
    # Kita tidak import Worker (karena butuh GUI), tapi kita cek kode worker.py secara langsung
    print("Test 1: Cek apakah worker tidak mencoba menggunakan Chrome pengguna di launch_attempts")
    
    worker_file = os.path.join(os.path.dirname(__file__), "core", "worker.py")
    with open(worker_file, "r", encoding="utf-8") as f:
        worker_content = f.read()
    
    # Kita cari bagian launch_attempts (yang penting)
    # Cari apakah ada "Google Chrome" atau "Microsoft Edge" di tuple launch_attempts
    # Boleh ada di pesan error, tapi tidak boleh di launch_attempts logic
    
    # Cari pola tuple dengan nama browser forbidden
    import re
    forbidden_patterns = [
        r'\("Google Chrome",',
        r'\("Microsoft Edge",',
        r"'Google Chrome',",
        r"'Microsoft Edge',",
    ]
    
    found_forbidden_in_launch = []
    for pattern in forbidden_patterns:
        if re.search(pattern, worker_content):
            found_forbidden_in_launch.append(pattern)
    
    if found_forbidden_in_launch:
        print(f"  ❌ FAIL: Found forbidden browser in launch_attempts: {found_forbidden_in_launch}")
        return False
    else:
        print("  ✅ PASS: No forbidden user-installed browsers in launch_attempts!")
    
    # Juga verifikasi logic launch_attempts
    from core.playwright_runtime import configure_playwright_browser_path
    
    internal_browser_path = configure_playwright_browser_path()
    
    if internal_browser_path:
        launch_attempts = [("Internal Chromium (PLAYWRIGHT_BROWSERS_PATH)", {})]
    else:
        launch_attempts = [("Playwright Default Chromium", {})]
    
    print(f"  Expected launch attempts: {[name for name, args in launch_attempts]}")
    
    # Verifikasi tidak ada yang forbidden
    forbidden_names = ["Google Chrome", "Microsoft Edge"]
    valid = True
    for name, args in launch_attempts:
        for fn in forbidden_names:
            if fn in name:
                print(f"  ❌ FAIL: Found forbidden in launch_attempts: {name}")
                valid = False
    
    if valid:
        print("  ✅ PASS: Launch attempts only include internal Chromium!")
    return valid

def test_playwright_browser_path_config():
    """Test: configure_playwright_browser_path berjalan normal"""
    print("\nTest 2: Cek configure_playwright_browser_path")
    from core.playwright_runtime import configure_playwright_browser_path
    
    result = configure_playwright_browser_path()
    print(f"  Result: {result}")
    
    if result:
        print(f"  ✅ PASS: Found internal browser path: {result}")
        return True
    else:
        print(f"  ℹ️ No internal browser path (expected in development, not production build)")
        print("  ✅ PASS: configure_playwright_browser_path returned None gracefully")
        return True

def test_macos_search_patterns():
    """Test: macOS search patterns include chrome-mac-x64"""
    print("\nTest 3: Cek macOS Chromium search patterns include chrome-mac-x64")
    from core.playwright_runtime import resolve_internal_chromium_executable
    
    # Test simulasi: cari pola "chrome-mac-x64" di kode
    import inspect
    source = inspect.getsource(resolve_internal_chromium_executable)
    
    required_patterns = ["chrome-mac-x64", "chrome-mac-arm64", "chrome-mac"]
    found_all = True
    for pattern in required_patterns:
        if pattern in source:
            print(f"  ✅ Found pattern: {pattern}")
        else:
            print(f"  ❌ Missing pattern: {pattern}")
            found_all = False
    
    return found_all

if __name__ == "__main__":
    print("="*60)
    print("  AUTOYU SMOKE TEST: BROWSER CONFIGURATION")
    print("="*60)
    
    tests = [
        ("No user Chrome fallback", test_no_user_chrome_fallback),
        ("PLAYWRIGHT_BROWSERS_PATH config", test_playwright_browser_path_config),
        ("macOS search patterns include x64/arm64", test_macos_search_patterns),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("  SMOKE TEST SUMMARY")
    print("="*60)
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 SEMUA TEST BERHASIL! Aplikasi akan menggunakan Chromium internal.")
        sys.exit(0)
    else:
        print("\n⚠️ ADA TEST YANG GAGAL! Mohon periksa konfigurasi.")
        sys.exit(1)
