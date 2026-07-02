import os
import sys
import glob


def _unique_paths(paths):
    seen = set()
    result = []
    for path in paths:
        if not path:
            continue
        try:
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(os.path.abspath(path))
        except (OSError, ValueError):
            continue
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

    try:
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if env_path and env_path not in ("0", "1"):
            candidates.append(env_path)
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        try:
            meipass = getattr(sys, "_MEIPASS", "")
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            
            # 1. Lokasi di dalam folder _internal (Windows/One-Dir) - PRIORITAS PERTAMA
            if meipass:
                candidates.append(os.path.join(meipass, "pw-browsers"))
                candidates.append(os.path.join(meipass, "browsers"))
            candidates.extend([
                os.path.join(exe_dir, "pw-browsers"),
                os.path.join(exe_dir, "browsers"),
                os.path.join(exe_dir, "_internal", "pw-browsers"),
                os.path.join(exe_dir, "_internal", "browsers"),
            ])
            
            # 2. Khusus macOS Bundle (.app)
            if sys.platform == "darwin":
                # Struktur .app: Contents/MacOS/AutoYuPro
                # Kita cari di: Contents/Resources/browsers
                contents_dir = os.path.dirname(exe_dir) # Contents
                res_dir = os.path.join(contents_dir, "Resources")
                candidates.extend([
                    os.path.join(res_dir, "pw-browsers"),
                    os.path.join(res_dir, "browsers"),
                    # Backup: Kadang PyInstaller menaruh di MacOS itu sendiri
                    os.path.join(exe_dir, "pw-browsers"),
                    os.path.join(exe_dir, "browsers"),
                ])
        except Exception:
            pass
    else:
        # Jika bukan frozen (development), prioritaskan folder di project root
        try:
            argv0_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else ""
            cwd = os.path.abspath(".")
            candidates.extend([
                os.path.join(cwd, "pw-browsers"),
                os.path.join(cwd, "browsers"),
                os.path.join(argv0_dir, "pw-browsers"),
                os.path.join(argv0_dir, "browsers"),
            ])
        except Exception:
            pass

    # 3. Lokasi default Playwright di sistem - terakhir
    try:
        if sys.platform.startswith("win"):
            # Windows: %USERPROFILE%\AppData\Local\ms-playwright
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if local_app_data:
                candidates.append(os.path.join(local_app_data, "ms-playwright"))
                candidates.append(os.path.join(local_app_data, "ms-playwright", "browsers"))
                candidates.append(os.path.join(local_app_data, "ms-playwright", "pw-browsers"))
            
            # Fallback: %USERPROFILE%\AppData\Roaming\ms-playwright
            app_data = os.environ.get("APPDATA", "")
            if app_data:
                candidates.append(os.path.join(app_data, "ms-playwright"))
                candidates.append(os.path.join(app_data, "ms-playwright", "browsers"))
                candidates.append(os.path.join(app_data, "ms-playwright", "pw-browsers"))
        
        elif sys.platform == "darwin":
            # macOS: ~/Library/Caches/ms-playwright
            home = os.path.expanduser("~")
            candidates.append(os.path.join(home, "Library", "Caches", "ms-playwright"))
            candidates.append(os.path.join(home, "Library", "Caches", "ms-playwright", "browsers"))
            candidates.append(os.path.join(home, "Library", "Caches", "ms-playwright", "pw-browsers"))
        
        else:
            # Linux: ~/.cache/ms-playwright
            home = os.path.expanduser("~")
            candidates.append(os.path.join(home, ".cache", "ms-playwright"))
            candidates.append(os.path.join(home, ".cache", "ms-playwright", "browsers"))
            candidates.append(os.path.join(home, ".cache", "ms-playwright", "pw-browsers"))
    except Exception:
        pass

    return _unique_paths(candidates)


def configure_playwright_browser_path():
    print(f"[Playwright] Checking for internal browsers...", flush=True)
    candidates = get_playwright_browser_candidates()
    print(f"[Playwright] Found {len(candidates)} candidates", flush=True)
    
    for i, candidate in enumerate(candidates):
        try:
            is_valid = _looks_like_playwright_browser_root(candidate)
            status = "✅ VALID" if is_valid else "❌ NOT FOUND"
            print(f"[Playwright] Candidate {i+1}: {candidate} -> {status}", flush=True)
            
            if is_valid:
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = candidate
                print(f"[Playwright] Final internal browser path set to: {candidate}", flush=True)
                return candidate
        except Exception as e:
            print(f"[Playwright] Error checking candidate {candidate}: {e}", flush=True)
            continue
            
    print("[Playwright] No internal browser path found, falling back to system default.", flush=True)
    return None


def resolve_internal_chromium_executable(browser_root):
    if not browser_root or not os.path.isdir(browser_root):
        print(f"[Playwright] Invalid browser_root: {browser_root}", flush=True)
        return None

    print(f"[Playwright] Resolving Chromium executable in: {browser_root}", flush=True)

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
            os.path.join(
                browser_root,
                "chrome-*",
                "chrome-mac",
                "Chromium.app",
                "Contents",
                "MacOS",
                "Chromium",
            ),
            os.path.join(
                browser_root,
                "chrome-*",
                "chrome-mac",
                "Google Chrome for Testing.app",
                "Contents",
                "MacOS",
                "Google Chrome for Testing",
            ),
        ]
    else:
        # Linux
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-linux", "chrome"),
            os.path.join(browser_root, "chrome-*", "chrome-linux", "chrome"),
        ]

    print(f"[Playwright] Using {len(patterns)} patterns", flush=True)

    for pattern in patterns:
        try:
            matches = sorted(glob.glob(pattern))
            print(f"[Playwright] Pattern {pattern} found {len(matches)} matches", flush=True)
            for match in matches:
                try:
                    if os.path.isfile(match):
                        print(f"[Playwright] Found executable: {match}", flush=True)
                        return os.path.abspath(match)
                except (OSError, ValueError) as e:
                    print(f"[Playwright] Error checking match {match}: {e}", flush=True)
                    continue
        except Exception as e:
            print(f"[Playwright] Error with pattern {pattern}: {e}", flush=True)
            continue
    
    print(f"[Playwright] No executable found in {browser_root}", flush=True)
    return None


def find_executable():
    """Mencari executable chromium di semua kandidat path browser."""
    print("[Playwright] find_executable() called", flush=True)
    candidates = get_playwright_browser_candidates()
    print(f"[Playwright] Checking {len(candidates)} candidates", flush=True)
    
    for i, candidate in enumerate(candidates):
        print(f"[Playwright] Trying candidate {i+1}: {candidate}", flush=True)
        try:
            exe = resolve_internal_chromium_executable(candidate)
            if exe:
                print(f"[Playwright] SUCCESS: Found executable at {exe}", flush=True)
                return exe
        except Exception as e:
            print(f"[Playwright] Error in candidate {candidate}: {e}", flush=True)
            continue
    
    print("[Playwright] FAILED: No executable found in any candidate", flush=True)
    return None
