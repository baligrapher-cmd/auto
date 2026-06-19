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
        return False

    try:
        entries = os.listdir(path)
    except OSError:
        return False

    if "registry.json" in entries:
        return True

    browser_prefixes = (
        "chromium-",
        "chromium_headless_shell-",
        "chrome-",
        "msedge-",
        "firefox-",
        "webkit-",
        "ffmpeg-",
    )
    return any(entry.startswith(browser_prefixes) for entry in entries)


def get_playwright_browser_candidates():
    candidates = []

    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path and env_path not in ("0", "1"):
        candidates.append(env_path)

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        
        # 1. Lokasi di dalam folder _internal (Windows/One-Dir)
        candidates.extend([
            os.path.join(meipass, "browsers"),
            os.path.join(exe_dir, "_internal", "browsers"),
            os.path.join(exe_dir, "browsers"),
        ])
        
        # 2. Khusus macOS Bundle (.app)
        if sys.platform == "darwin":
            # Struktur .app: Contents/MacOS/AutoYuPro
            # Kita cari di: Contents/Resources/browsers
            contents_dir = os.path.dirname(exe_dir) # Contents
            res_dir = os.path.join(contents_dir, "Resources")
            candidates.extend([
                os.path.join(res_dir, "browsers"),
                os.path.join(res_dir, "pw-browsers"),
                # Backup: Kadang PyInstaller menaruh di MacOS itu sendiri
                os.path.join(exe_dir, "browsers"),
            ])

    # 3. Lokasi Development / CWD
    argv0_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else ""
    cwd = os.path.abspath(".")
    candidates.extend([
        os.path.join(argv0_dir, "browsers"),
        os.path.join(cwd, "browsers"),
    ])

    return _unique_paths(candidates)


def configure_playwright_browser_path():
    candidates = get_playwright_browser_candidates()
    for candidate in candidates:
        is_valid = _looks_like_playwright_browser_root(candidate)
        if is_valid:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = candidate
            print(f"[Playwright] Using internal browser path: {candidate}", flush=True)
            return candidate
            
    print(f"[Playwright] No internal browser found, using system default (this is normal for development)", flush=True)
    return None


def resolve_internal_chromium_executable(browser_root):
    if not browser_root or not os.path.isdir(browser_root):
        return None

    if sys.platform.startswith("win"):
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-win*", "chrome.exe"),
            os.path.join(browser_root, "chrome-*", "chrome-win*", "chrome.exe"),
            os.path.join(browser_root, "chromium_headless_shell-*", "chrome-headless-shell-win*", "chrome-headless-shell.exe"),
        ]
    elif sys.platform == "darwin":
        patterns = [
            os.path.join(
                browser_root,
                "chromium-*",
                "chrome-mac",
                "Chromium.app",
                "Contents",
                "MacOS",
                "Chromium",
            ),
            os.path.join(
                browser_root,
                "chromium-*",
                "chrome-mac",
                "Google Chrome for Testing.app",
                "Contents",
                "MacOS",
                "Google Chrome for Testing",
            ),
        ]
    else:
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-linux", "chrome"),
            os.path.join(browser_root, "chrome-*", "chrome-linux", "chrome"),
        ]

    for pattern in patterns:
        for match in sorted(glob.glob(pattern)):
            if os.path.isfile(match):
                return os.path.abspath(match)
    return None


def find_executable():
    """Mencari executable chromium di semua kandidat path browser."""
    for candidate in get_playwright_browser_candidates():
        exe = resolve_internal_chromium_executable(candidate)
        if exe:
            return exe
    return None
