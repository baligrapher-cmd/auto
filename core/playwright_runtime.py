import os
import sys
import glob


def _unique_paths(paths):
    seen = set()
    result = []
    for path in paths:
        if not path:
            continue
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(os.path.abspath(path))
    return result


def _looks_like_playwright_browser_root(path):
    if not path or not os.path.isdir(path):
        print(f"[DEBUG] _looks_like_playwright_browser_root: {path} is not a valid directory")
        return False

    print(f"[DEBUG] _looks_like_playwright_browser_root: checking {path}")
    try:
        entries = os.listdir(path)
        print(f"[DEBUG] _looks_like_playwright_browser_root: contents: {entries}")
    except OSError as e:
        print(f"[DEBUG] _looks_like_playwright_browser_root: OS error {e}")
        return False

    # Check for registry.json (official Playwright structure)
    if "registry.json" in entries:
        print(f"[DEBUG] _looks_like_playwright_browser_root: found registry.json, returning True")
        return True

    # Check if any entry is a directory starting with browser prefixes
    browser_prefixes = (
        "chromium-",
        "chromium_headless_shell-",
        "chrome-",
        "msedge-",
        "firefox-",
        "webkit-",
        "ffmpeg-",
    )
    
    for entry in entries:
        entry_path = os.path.join(path, entry)
        if os.path.isdir(entry_path) and any(entry.startswith(prefix) for prefix in browser_prefixes):
            print(f"[DEBUG] _looks_like_playwright_browser_root: found browser dir {entry}, returning True")
            return True
    
    print(f"[DEBUG] _looks_like_playwright_browser_root: no match, returning False")
    return False


def get_playwright_browser_candidates():
    candidates = []

    if getattr(sys, "frozen", False):
        # WHEN FROZEN: PRIORITIZE BUNDLED BROWSERS FIRST!
        meipass = getattr(sys, "_MEIPASS", "")
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        
        # macOS Bundle (.app) resources dir
        if sys.platform == "darwin":
            contents_dir = os.path.dirname(exe_dir) # Contents
            res_dir = os.path.join(contents_dir, "Resources")
            candidates.extend([
                os.path.join(res_dir, "browsers"),
                os.path.join(res_dir, "pw-browsers"),
            ])
        
        # One-dir/Windows internal
        candidates.extend([
            os.path.join(meipass, "browsers"),
            os.path.join(exe_dir, "_internal", "browsers"),
            os.path.join(exe_dir, "browsers"),
        ])
        
        # Env path last when frozen (don't prioritize external)
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if env_path and env_path not in ("0", "1"):
            candidates.append(env_path)
    else:
        # WHEN NOT FROZEN (dev mode): Keep original order
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if env_path and env_path not in ("0", "1"):
            candidates.append(env_path)
        
        meipass = getattr(sys, "_MEIPASS", "")
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        
        candidates.extend([
            os.path.join(meipass, "browsers"),
            os.path.join(exe_dir, "_internal", "browsers"),
            os.path.join(exe_dir, "browsers"),
        ])
        
        if sys.platform == "darwin":
            contents_dir = os.path.dirname(exe_dir)
            res_dir = os.path.join(contents_dir, "Resources")
            candidates.extend([
                os.path.join(res_dir, "browsers"),
                os.path.join(res_dir, "pw-browsers"),
            ])
        
        argv0_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else ""
        cwd = os.path.abspath(".")
        candidates.extend([
            os.path.join(argv0_dir, "browsers"),
            os.path.join(cwd, "browsers"),
        ])

    return _unique_paths(candidates)


def configure_playwright_browser_path():
    import platform
    print(f"[DEBUG] configure_playwright_browser_path() - System: {platform.platform()} - Machine: {platform.machine()}")
    candidates = get_playwright_browser_candidates()
    print(f"[DEBUG] configure_playwright_browser_path() - candidates: {candidates}")
    for candidate in candidates:
        print(f"[DEBUG] configure_playwright_browser_path() - checking candidate: {candidate}")
        if _looks_like_playwright_browser_root(candidate):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = candidate
            print(f"[DEBUG] configure_playwright_browser_path() - SET to: {candidate}")
            return candidate
        
    print(f"[DEBUG] configure_playwright_browser_path() - NO valid browser root found!")
    return None


def resolve_internal_chromium_executable(browser_root):
    import platform
    import subprocess
    if not browser_root or not os.path.isdir(browser_root):
        print(f"[DEBUG] resolve_internal_chromium_executable: browser_root invalid: {browser_root}")
        return None

    print(f"[DEBUG] resolve_internal_chromium_executable: looking in {browser_root}")

    if sys.platform.startswith("win"):
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-win*", "chrome.exe"),
            os.path.join(browser_root, "chrome-*", "chrome-win*", "chrome.exe"),
            os.path.join(browser_root, "chromium_headless_shell-*", "chrome-headless-shell-win*", "chrome-headless-shell.exe"),
        ]
    elif sys.platform == "darwin":
        # Tambahkan lebih banyak pola untuk mendukung berbagai struktur folder dan arsitektur
        patterns = [
            # Pola dengan arsitektur (contoh: chrome-mac-arm64 atau chrome-mac-x64)
            os.path.join(browser_root, "chromium-*", "chrome-mac-*", "Chromium.app", "Contents", "MacOS", "Chromium"),
            os.path.join(browser_root, "chromium-*", "chrome-mac-*", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(browser_root, "chromium-*", "chrome-mac-*", "Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
            # Pola dasar tanpa suffix arsitektur
            os.path.join(browser_root, "chromium-*", "chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"),
            os.path.join(browser_root, "chromium-*", "chrome-mac", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(browser_root, "chromium-*", "chrome-mac", "Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
            # Pola tanpa "chrome-mac" di tengah
            os.path.join(browser_root, "chromium-*", "Chromium.app", "Contents", "MacOS", "Chromium"),
            os.path.join(browser_root, "chromium-*", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(browser_root, "chromium-*", "Google Chrome.app", "Contents", "MacOS", "Google Chrome"),
        ]
    else:
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-linux", "chrome"),
            os.path.join(browser_root, "chrome-*", "chrome-linux", "chrome"),
        ]

    for pattern in patterns:
        matches = glob.glob(pattern)
        print(f"[DEBUG] Pattern {pattern} found {len(matches)} matches")
        for match in sorted(matches):
            if os.path.isfile(match):
                print(f"[DEBUG] Found candidate: {match}")
                # Skip lipo check entirely to avoid macOS popup asking for command line tools
                # Just return the first valid executable we find
                return os.path.abspath(match)
    return None


def find_executable():
    """Mencari executable chromium di semua kandidat path browser."""
    candidates = get_playwright_browser_candidates()
    print(f"[DEBUG] find_executable() - candidates: {candidates}")
    for candidate in candidates:
        exe = resolve_internal_chromium_executable(candidate)
        if exe:
            print(f"[DEBUG] find_executable() - found: {exe}")
            return exe
    print(f"[DEBUG] find_executable() - NO executable found!")
    return None
