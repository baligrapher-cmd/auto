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
    if not browser_root or not os.path.isdir(browser_root):
        print(f"[DEBUG] resolve_internal_chromium_executable: browser_root invalid: {browser_root}")
        return None

    print(f"[DEBUG] resolve_internal_chromium_executable: looking in {browser_root}")

    # Debug: Print semua subdirektori di browser_root untuk melihat struktur
    try:
        print(f"[DEBUG] Browser root contents: {os.listdir(browser_root)}")
        # Print isi setiap direktori chromium-*
        for item in os.listdir(browser_root):
            item_path = os.path.join(browser_root, item)
            if os.path.isdir(item_path) and item.startswith("chromium-"):
                print(f"[DEBUG] Content of {item}: {os.listdir(item_path)}")
                # Cek satu level lebih dalam
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path):
                        print(f"[DEBUG] Content of {item}/{subitem}: {os.listdir(subitem_path)[:10]}")
    except Exception as e:
        print(f"[DEBUG] Error listing browser root: {e}")

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
            # Pola pencarian lebih agresif - cari semua .app di dalam chromium-*
            os.path.join(browser_root, "chromium-*", "*.app", "Contents", "MacOS", "*"),
        ]
    else:
        patterns = [
            os.path.join(browser_root, "chromium-*", "chrome-linux", "chrome"),
            os.path.join(browser_root, "chrome-*", "chrome-linux", "chrome"),
            os.path.join(browser_root, "chromium-*", "*", "chrome"),
        ]

    collected = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        print(f"[DEBUG] Pattern {pattern} found {len(matches)} matches")
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                print(f"[DEBUG] Valid executable found: {match}")
                collected.append(os.path.abspath(match))

    if not collected:
        print(f"[DEBUG] No executable found! Last resort: recursive search for any executable in browser_root")
        # Last resort: cari semua file executable di browser_root secara rekursif
        for root, dirs, files in os.walk(browser_root):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                    # Cek nama file untuk memastikan itu Chromium
                    filename = file.lower()
                    if "chromium" in filename or "chrome" in filename and not filename.endswith((".dll", ".dylib", ".so")):
                        print(f"[DEBUG] Found possible executable via recursive search: {file_path}")
                        collected.append(os.path.abspath(file_path))

    if not collected:
        print(f"[DEBUG] Still no executable found!")
        return None

    if sys.platform == "darwin":
        current_arch = platform.machine().lower()
        print(f"[DEBUG] Current architecture: {current_arch}")

        def _score(path):
            p = path.lower()
            score = 0
            if current_arch in ("arm64", "aarch64"):
                if "arm64" in p:
                    score += 20
                if "x64" in p or "x86_64" in p:
                    score -= 20
                # Prioritaskan nama Chromium
                if "chromium" in p:
                    score += 10
            elif current_arch in ("x86_64", "i386"):
                if "x64" in p or "x86_64" in p:
                    score += 20
                if "arm64" in p or "aarch64" in p:
                    score -= 20
                # Prioritaskan nama Chromium
                if "chromium" in p:
                    score += 10
            return (-score, p)

        collected = sorted(set(collected), key=_score)
        chosen = collected[0]
        print(f"[DEBUG] Found candidate (best match): {chosen}")
        return chosen

    chosen = sorted(set(collected))[0]
    print(f"[DEBUG] Found candidate: {chosen}")
    return chosen


def get_executable_arch(executable_path):
    """Mendapatkan arsitektur executable secara actual dengan perintah file (macOS/Linux) atau Windows API."""
    import subprocess
    import platform
    try:
        if sys.platform == "darwin":
            # Gunakan perintah file di macOS
            result = subprocess.run(["file", executable_path], capture_output=True, text=True, check=False)
            output = result.stdout.lower()
            if "arm64" in output or "aarch64" in output:
                return "arm64"
            elif "x86_64" in output or "x64" in output:
                return "x86_64"
            elif "i386" in output:
                return "i386"
        elif sys.platform.startswith("win"):
            # Di Windows, kita bisa cek dengan sederhana atau return None
            return None
        elif sys.platform.startswith("linux"):
            result = subprocess.run(["file", executable_path], capture_output=True, text=True, check=False)
            output = result.stdout.lower()
            if "arm64" in output or "aarch64" in output:
                return "arm64"
            elif "x86_64" in output or "x64" in output:
                return "x86_64"
    except Exception as e:
        print(f"[DEBUG] Error checking executable arch: {e}")
    return None

def find_executable():
    """Mencari executable chromium di semua kandidat path browser."""
    import platform
    current_arch = platform.machine().lower()
    if current_arch == "amd64":
        current_arch = "x86_64"
    
    candidates = get_playwright_browser_candidates()
    print(f"[DEBUG] find_executable() - candidates: {candidates}")
    print(f"[DEBUG] find_executable() - current system arch: {current_arch}")
    
    best_match = None
    fallback_match = None
    
    for candidate in candidates:
        exe = resolve_internal_chromium_executable(candidate)
        if exe:
            print(f"[DEBUG] find_executable() - checking: {exe}")
            
            # Cek arsitektur executable secara actual
            exe_arch = get_executable_arch(exe)
            print(f"[DEBUG] find_executable() - executable arch: {exe_arch}")
            
            if exe_arch == current_arch:
                print(f"[DEBUG] find_executable() - perfect match found!")
                best_match = exe
                break  # langsung gunakan yang perfect
            
            # Fallback: jika tidak perfect, simpan sebagai fallback
            if not fallback_match:
                fallback_match = exe
    
    if best_match:
        return best_match
    if fallback_match:
        print(f"[DEBUG] find_executable() - using fallback (arch might not match perfectly): {fallback_match}")
        return fallback_match
    
    print(f"[DEBUG] find_executable() - NO executable found!")
    return None
