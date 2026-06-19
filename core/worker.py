import os
import sys
import time
import json
import re
import ctypes
import hashlib
from PySide6.QtCore import QThread, Signal, QObject
from playwright.sync_api import sync_playwright
from core.automation import TabAutomation
from core.state_machine import AutoState, UploadMode, MODE_CONFIG
from core.license import check_license, get_app_data_dir, get_app_data_dir_by_name
from core.playwright_runtime import configure_playwright_browser_path, find_executable, resolve_internal_chromium_executable

class AutomationWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    login_required_signal = Signal()
    license_error_signal = Signal()
    progress_signal = Signal(int, int, int, int, int) # uploaded, failed, duplicate, active, total
    batch_finished_signal = Signal(int, int) # total_uploaded, total_failed
    new_photo_signal = Signal(int) # Number of new photos detected
    login_success_signal = Signal() # Signal when login is detected
    browser_disconnected_signal = Signal() # Signal when browser disconnects/crashes
    location_resolved_signal = Signal(str, str, str) # location_name, match_type, source
    fototree_resolved_signal = Signal(str, str, str) # tree_name, match_type, source

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._is_running = True
        self._login_confirmed = False
        self.browser = None
        self.context = None
        self.playwright = None
        # Mode runtime dikunci SAFE untuk semua varian aplikasi.
        self.mode = UploadMode.SAFE
        self.config['mode'] = UploadMode.SAFE
        self.monitor_enabled = config.get('monitor_profile', False)
        self.monitor_username = config.get('monitor_username', '')
        self.monitor_interval = config.get('monitor_interval', 5) * 60 # Convert to seconds
        self._last_monitor_time = 0
        self._known_photo_count = -1 # -1 means not yet initialized
        
        # Track uploaded files
        self.history_file = None
        self.uploaded_history = set()
        
        # Crash recovery state
        self._crash_count = 0
        self._max_crash_recovery = 3
        self._last_saved_state = None
        self._page_crash_handlers_added = False
        self._last_location_resolution = None

    def _handle_location_resolved(self, location_name, match_type, source):
        resolved_name = str(location_name or "").strip()
        if not resolved_name:
            return

        resolution_key = (
            resolved_name.lower(),
            str(match_type or "").strip().lower(),
            str(source or "").strip().lower(),
        )
        if resolution_key == self._last_location_resolution:
            return

        self._last_location_resolution = resolution_key
        self.config["location"] = resolved_name
        # USER FIX: Clear FotoTree in config if Location is resolved
        self.config["fototree"] = ""
        self.location_resolved_signal.emit(
            resolved_name,
            str(match_type or ""),
            str(source or "")
        )

    def _handle_fototree_resolved(self, tree_name, match_type, source):
        resolved_name = str(tree_name or "").strip()
        if not resolved_name:
            return

        resolution_key = (
            resolved_name.lower(),
            str(match_type or "").strip().lower(),
            str(source or "").strip().lower(),
        )
        if resolution_key == getattr(self, "_last_tree_resolution", None):
            return

        self._last_tree_resolution = resolution_key
        self.config["fototree"] = resolved_name
        # USER FIX: Clear Location in config if FotoTree is resolved
        self.config["location"] = ""
        self.fototree_resolved_signal.emit(
            resolved_name,
            str(match_type or ""),
            str(source or "")
        )

    def _load_history(self):
        history = set()
        # 1. Load dari file JSON
        if self.history_file and os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    history = set(json.load(f))
            except:
                pass
        return history

    def _save_history(self, file_path):
        self.uploaded_history.add(file_path)
        try:
            with open(self.history_file, 'w') as f:
                json.dump(list(self.uploaded_history), f)
            
            # Sembunyikan file di Windows
            if os.name == 'nt':
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(self.history_file, 2)
                except:
                    pass
        except:
            pass

    def _cleanup_profile(self, user_data_dir):
        """Agresif membersihkan file sampah/lock yang membuat browser gagal launch."""
        if not os.path.exists(user_data_dir):
            return
            
        print(f"[Worker] Cleaning up profile: {user_data_dir}")
        
        # 1. File lock standar Chromium
        lock_patterns = [
            "SingletonLock",
            "SingletonSocket",
            "SingletonCookie",
            "lock",
            "LOCK",
            "*.lock"
        ]
        
        # 2. Folder cache yang sering korup
        cache_folders = [
            os.path.join(user_data_dir, "Default", "Cache"),
            os.path.join(user_data_dir, "Default", "Code Cache"),
            os.path.join(user_data_dir, "Default", "GPUCache"),
            os.path.join(user_data_dir, "ShaderCache"),
            os.path.join(user_data_dir, "GrShaderCache"),
        ]

        import shutil
        import glob

        # Hapus file lock di root profile
        for pattern in lock_patterns:
            for f in glob.glob(os.path.join(user_data_dir, pattern)):
                try:
                    if os.path.isfile(f) or os.path.islink(f):
                        os.remove(f)
                        print(f"[Worker] Removed lock file: {f}")
                except:
                    pass

        # Hapus folder cache
        for folder in cache_folders:
            try:
                if os.path.exists(folder):
                    shutil.rmtree(folder, ignore_errors=True)
                    print(f"[Worker] Cleared cache folder: {folder}")
            except:
                pass

        # Hapus file LOCK di subfolder (seperti IndexedDB, dll)
        for root, dirs, files in os.walk(user_data_dir):
            for file in files:
                if file.upper() == "LOCK":
                    try:
                        os.remove(os.path.join(root, file))
                    except:
                        pass

    def run(self):
        try:
            self._run_internal()
        except Exception as e:
            error_msg = f"CRITICAL THREAD ERROR: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.log_signal.emit(f"❌ Kesalahan Sistem: {str(e)}")
            self.finished_signal.emit()

    def _run_internal(self):
        print(f"[Worker] Thread started. Mode: {self.mode}")
        # HARD LICENSE CHECK - STARTUP
        app_type = self.config.get('app_type', 'pro')
        is_valid, status, _, _ = check_license(app_type=app_type)
        if not is_valid:
            if "CONNECTION_FAILED" in status or "SERVER_CONNECTION_ERROR" in status:
                self.log_signal.emit("⚠️ Verifikasi lisensi via internet belum berhasil.")
                self.log_signal.emit("ℹ️ Aplikasi tetap berjalan sementara sambil mencoba ulang otomatis (maks. ±10 menit).")
                self.log_signal.emit("✅ Solusi cepat: Pastikan internet stabil, matikan VPN, dan cek pengaturan keamanan/antivirus jika koneksi sering terputus.")
            else:
                error_msg = "Lisensi tidak aktif atau tidak valid."
                if status == "LICENSE_EXPIRED":
                    error_msg = "Lisensi Anda telah kadaluarsa."
                elif status == "LICENSE_DISABLED":
                    error_msg = "Lisensi telah dinonaktifkan oleh admin."
                elif status == "CONNECTION_FAILED":
                    error_msg = "Verifikasi gagal. Pastikan Anda terhubung ke internet."
                elif status == "SERVER_CONNECTION_ERROR":
                    error_msg = "Server verifikasi sedang bermasalah. Coba lagi beberapa saat."
                
                print(f"[Worker] License check failed: {status}")
                self.log_signal.emit(f"⚠️ {error_msg}")
                self.license_error_signal.emit()
                self.finished_signal.emit()
                return

        self.log_signal.emit("Memulai layanan...")
        
        account_name = self.config.get("current_account")
        print(f"[Worker] Selected account: {account_name}")
        if not account_name:
            self.log_signal.emit("❌ ERROR: Tidak ada akun yang dipilih!")
            self.finished_signal.emit()
            return
            
        # Gunakan folder data di AppData sistem (Standard Windows Workflow)
        base_local = get_app_data_dir()
        account_root = os.path.join(base_local, "accounts", account_name)
        user_data_dir = os.path.join(account_root, "profile")
        print(f"[Worker] User data dir: {user_data_dir}")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
        
        # CLEANUP: Agresif bersihkan sampah profile
        self._cleanup_profile(user_data_dir)

        # USER FIX: SINKRONISASI INITIAL HISTORY (uploaded.json tetap sebagai fallback global)
        self.history_file = os.path.join(account_root, "uploaded.json")
        self.uploaded_history = self._load_history()

        try:
            resolved_browser_path = configure_playwright_browser_path()
            if resolved_browser_path:
                print(f"[Worker] PLAYWRIGHT_BROWSERS_PATH={resolved_browser_path}")
            else:
                print("[Worker] PLAYWRIGHT_BROWSERS_PATH not resolved from bundled paths.")

            with sync_playwright() as p:
                self.playwright = p
                print("[Worker] Playwright started. Launching browser...")
                
                # Launch Persistent Context
                launch_args = {
                    "user_data_dir": user_data_dir,
                    "headless": False,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--disable-features=RendererCodeIntegrity",
                        "--disable-software-rasterizer",
                        "--disable-gpu-sandbox",
                        "--disable-accelerated-2d-canvas",
                        "--disable-sync",
                        "--window-size=1280,720", # Paksa ukuran desktop
                        "--start-maximized" # Start maximized untuk tampilan desktop penuh
                    ],
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", # Paksa Desktop User Agent
                    "no_viewport": True,
                    "permissions": ["geolocation"],
                    "geolocation": {"latitude": -8.65, "longitude": 115.216667}, # Default Bali
                    "timeout": 120000 
                }
                print(f"[Worker] Launch args: {launch_args}")

                # PRIORITAS: Coba semua opsi browser secara berurutan
                browser_launched = False
                launch_attempts = [
                    ("Internal Chromium", {"executable_path": find_executable()}),
                    ("Playwright Default Chromium", {}),
                    ("Google Chrome", {"channel": "chrome"}),
                    ("Microsoft Edge", {"channel": "msedge"}),
                ]
                
                for browser_name, extra_args in launch_attempts:
                    # Skip if the required argument isn't available
                    if "executable_path" in extra_args and extra_args["executable_path"] is None:
                        continue
                        
                    try:
                        self.log_signal.emit(f"Membuka {browser_name}...")
                        print(f"[Worker] Attempting {browser_name}...")
                        
                        # Merge extra args into launch args
                        current_launch_args = launch_args.copy()
                        current_launch_args.update(extra_args)
                        
                        # Launch the browser
                        self.context = p.chromium.launch_persistent_context(**current_launch_args)
                        print(f"[Worker] Success: {browser_name} launched!")
                        self.log_signal.emit(f"✅ {browser_name} berhasil dibuka!")
                        browser_launched = True
                        break
                    except Exception as e:
                        err_msg = str(e).split("\n")[0]
                        print(f"[Worker] {browser_name} failed: {e}")
                        self.log_signal.emit(f"⚠️ {browser_name} gagal: {err_msg[:60]}...")
                
                if not browser_launched:
                    self.log_signal.emit("❌ CRITICAL ERROR: Tidak dapat menemukan browser apapun!")
                    self.log_signal.emit("Pastikan Google Chrome, Microsoft Edge, atau Playwright Chromium sudah terinstal.")
                    self.log_signal.emit("Untuk menginstal Playwright Chromium, jalankan: playwright install chromium")
                    self.finished_signal.emit()
                    return

                # Ensure context is valid
                if not self.context:
                    self.log_signal.emit("Gagal membuat konteks browser.")
                    self.finished_signal.emit()
                    return

                # DETEKSI BROWSER DITUTUP PAKSA
                def on_context_close():
                    if self._is_running:
                        self.log_signal.emit("⚠️ Browser ditutup paksa. Menghentikan engine...")
                        self.browser_disconnected_signal.emit()
                        self._is_running = False

                self.context.on("close", on_context_close)

                # DETEKSI PAGE CRASH / DISCONNECT (saat internet mati browser fechou)
                def on_page_crash(page):
                    if self._is_running:
                        self._crash_count += 1
                        self._save_crash_recovery_state()
                        if self._crash_count <= self._max_crash_recovery:
                            self.log_signal.emit(f"⚠️ Tab/Browser crash (kemungkinan internet drop). Recovery {self._crash_count}/{self._max_crash_recovery}...")
                            self.log_signal.emit("ℹ️ Solusi cepat: cek WiFi/Hotspot, matikan VPN, lalu tunggu 5-10 detik.")
                        else:
                            self.log_signal.emit("❌ Maksimum recovery tercapai. Engine dihentikan untuk menjaga data.")
                            self._is_running = False

                page = self.context.pages[0]
                page.on("crash", lambda: on_page_crash(page))

                # Set timeout untuk detecting network issues
                page.set_default_timeout(15000)
                try:
                    page.set_default_navigation_timeout(30000)
                except Exception:
                    pass

                page.goto("https://www.fotoyu.com/upload")

                if self.config.get("setup_ultra"):
                    def _capture_ultra_token_and_meta(request):
                        try:
                            url = str(getattr(request, "url", "") or "").lower()
                            if "api.fotoyu.com" not in url:
                                return

                            headers = getattr(request, "headers", {}) or {}
                            auth_token = headers.get("authorization") or headers.get("Authorization")
                            if auth_token and len(str(auth_token).strip()) >= 20:
                                for base_local in (get_app_data_dir(), get_app_data_dir_by_name("AutoYuUltra")):
                                    try:
                                        token_dir = os.path.join(base_local, "trackers")
                                        os.makedirs(token_dir, exist_ok=True)
                                        token_file = os.path.join(token_dir, "api_token.txt")
                                        with open(token_file, "w", encoding="utf-8") as f:
                                            f.write(auth_token)
                                    except Exception:
                                        pass

                            method = ""
                            try:
                                method = request.method
                            except Exception:
                                try:
                                    method = request.method()
                                except Exception:
                                    method = ""

                            if str(method or "").upper() != "POST":
                                return

                            post_data = ""
                            try:
                                post_data = request.post_data or ""
                            except Exception:
                                try:
                                    post_data = request.post_data() or ""
                                except Exception:
                                    post_data = ""

                            if not post_data:
                                return

                            if "/gs/v3/creations" in url:
                                try:
                                    # Simpan headers lengkap untuk ULTRA
                                    ultra_headers = {}
                                    for h_key, h_val in headers.items():
                                        if h_key.lower() in ["authorization", "user-agent", "origin", "referer", "accept"]:
                                            ultra_headers[h_key] = h_val
                                    
                                    for base_local in (get_app_data_dir(), get_app_data_dir_by_name("AutoYuUltra")):
                                        try:
                                            token_dir = os.path.join(base_local, "trackers")
                                            os.makedirs(token_dir, exist_ok=True)
                                            header_file = os.path.join(token_dir, "api_headers.json")
                                            with open(header_file, "w", encoding="utf-8") as f:
                                                json.dump(ultra_headers, f)
                                        except Exception:
                                            pass

                                    names = re.findall(r'name="([^"]+)"', post_data)
                                    file_field = None
                                    m = re.search(r'name="([^"]+)"[^\r\n]*\r\n[^\r\n]*filename="[^"]+"', post_data)
                                    if m:
                                        file_field = m.group(1)
                                    schema = {
                                        "endpoint": "https://api.fotoyu.com/gs/v3/creations",
                                        "fields": list(dict.fromkeys(names)),
                                    }
                                    if file_field:
                                        schema["file_field"] = file_field
                                    if not getattr(self, "_ultra_schema_logged", False):
                                        self._ultra_schema_logged = True
                                        try:
                                            ff = file_field or "?"
                                            self.log_signal.emit(f"🔎 ULTRA: Skema API terdeteksi (file_field={ff}).")
                                        except Exception:
                                            pass
                                    for base_local in (get_app_data_dir(), get_app_data_dir_by_name("AutoYuUltra")):
                                        try:
                                            token_dir = os.path.join(base_local, "trackers")
                                            os.makedirs(token_dir, exist_ok=True)
                                            schema_file = os.path.join(token_dir, "api_ultra_schema.json")
                                            with open(schema_file, "w", encoding="utf-8") as f:
                                                json.dump(schema, f)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            # USER FIX: Mutual Exclusion Metadata Capture
                            changed = False
                            meta = {}
                            is_tree = False
                            is_loc = False

                            if "tree_id" in post_data:
                                match = re.search(r'name="tree_id"\s*\r\n\r\n(\d+)', post_data)
                                if match and match.group(1) != "0":
                                    meta["tree_id"] = match.group(1)
                                    is_tree = True
                                    changed = True
                            
                            if "location_id" in post_data:
                                match = re.search(r'name="location_id"\s*\r\n\r\n(\d+)', post_data)
                                if match and match.group(1) != "0":
                                    meta["location_id"] = match.group(1)
                                    is_loc = True
                                    changed = True

                            if not changed:
                                return

                            for base_local in (get_app_data_dir(), get_app_data_dir_by_name("AutoYuUltra")):
                                try:
                                    token_dir = os.path.join(base_local, "trackers")
                                    os.makedirs(token_dir, exist_ok=True)
                                    
                                    # Get account name from config
                                    account_name = str(self.config.get("current_account") or "").strip()
                                    
                                    # List of metadata files to update (account-specific first, then main)
                                    metadata_files = []
                                    if account_name:
                                        metadata_files.append(os.path.join(token_dir, f"api_metadata_{account_name}.json"))
                                    metadata_files.append(os.path.join(token_dir, "api_metadata.json"))
                                    
                                    # Load existing data from the first available metadata file
                                    existing = {}
                                    for f in metadata_files:
                                        if os.path.exists(f):
                                            try:
                                                with open(f, "r", encoding="utf-8") as f_obj:
                                                    existing = json.load(f_obj) or {}
                                                break
                                            except Exception:
                                                continue
                                    
                                    # Update with mutual exclusion
                                    if is_tree:
                                        existing["tree_id"] = meta["tree_id"]
                                        existing.pop("location_id", None)
                                    if is_loc:
                                        existing["location_id"] = meta["location_id"]
                                        existing.pop("tree_id", None)

                                    # Save to all metadata files
                                    for metadata_file in metadata_files:
                                        with open(metadata_file, "w", encoding="utf-8") as f:
                                            json.dump(existing, f, indent=2)
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    try:
                        page.on("requestfinished", _capture_ultra_token_and_meta)
                    except Exception:
                        pass

                # Login Phase
                self.log_signal.emit("Menunggu login...")
                self.login_required_signal.emit()
                
                # AUTO-DETECTION: Deteksi otomatis jika user sudah login
                from core.automation import SELECTORS
                
                # USER FIX: SINKRONISASI LOGIKA HASH (Source of Truth)
                import hashlib
                def _get_folder_hash(path):
                    abs_p = os.path.abspath(os.path.expanduser(path))
                    # Normalisasi trailing separator
                    if abs_p.endswith(os.sep): abs_p = abs_p[:-1]
                    
                    hash_p = abs_p
                    if os.name == 'nt':
                        hash_p = hash_p.lower()
                    return hashlib.md5(hash_p.encode('utf-8')).hexdigest()[:12]

                while not self._login_confirmed and self._is_running:
                    try:
                        curr_url = page.url.lower()
                        # Deteksi halaman upload (pasti sudah login)
                        if "fotoyu.com/upload" in curr_url or "fotoyu.com/creation" in curr_url:
                             # Cek elemen kunci di halaman upload
                             # Gunakan .count() > 0 untuk memastikan elemen ada di DOM
                             has_upload_ui = False
                             try:
                                 if page.locator(SELECTORS["trigger_container"]).first.count() > 0 or \
                                    page.locator(SELECTORS["price_input"]).first.count() > 0:
                                     has_upload_ui = True
                             except:
                                 pass

                             if has_upload_ui:
                                 self._login_confirmed = True
                                 self.log_signal.emit("✅ Login terdeteksi otomatis!")
                                 self.login_success_signal.emit()
                                 break
                        
                        # Deteksi halaman profil/home yang menandakan sudah login
                        if "fotoyu.com/profile" in curr_url or "fotoyu.com/home" in curr_url:
                             self._login_confirmed = True
                             self.log_signal.emit("✅ Login terdeteksi (Halaman Profil/Home).")
                             self.login_success_signal.emit()
                             break

                    except Exception:
                        pass
                    
                    time.sleep(1)
                
                if not self._is_running:
                    try:
                        self.context.close()
                    except:
                        pass
                    return

                # Jika hanya untuk login (saat tambah akun baru)
                if self.config.get("login_only"):
                    if self.config.get("setup_metadata_first"):
                        self.log_signal.emit("✅ Login terdeteksi. Upload manual 1 foto dengan metadata lengkap, lalu tunggu setup selesai.")
                        from core.automation import SELECTORS

                        def _mark_setup_done_for_account(captured_meta=None):
                            try:
                                account_name = str(self.config.get("current_account") or "").strip()
                                if not account_name:
                                    return False

                                # 1. Mark as setup done in user_settings.json
                                settings_path = os.path.join(get_app_data_dir(), "user_settings.json")
                                settings = {}
                                if os.path.exists(settings_path):
                                    try:
                                        with open(settings_path, "r", encoding="utf-8") as f:
                                            settings = json.load(f) or {}
                                    except Exception:
                                        settings = {}
                                if not isinstance(settings, dict):
                                    settings = {}

                                setup_accounts = settings.get("setup_done_accounts") or {}
                                if not isinstance(setup_accounts, dict):
                                    setup_accounts = {}

                                setup_accounts[account_name] = int(time.time())
                                settings["setup_done_accounts"] = setup_accounts

                                # 2. Save captured metadata to api_metadata.json for UI fallback
                                if captured_meta:
                                    try:
                                        tracker_dir = os.path.join(get_app_data_dir(), "trackers")
                                        os.makedirs(tracker_dir, exist_ok=True)
                                        
                                        # Load existing metadata (account-specific first, then main)
                                        existing_meta = {}
                                        metadata_paths = [
                                            os.path.join(tracker_dir, f"api_metadata_{account_name}.json"),
                                            os.path.join(tracker_dir, "api_metadata.json")
                                        ]
                                        for path in metadata_paths:
                                            if os.path.exists(path):
                                                try:
                                                    with open(path, "r", encoding="utf-8") as f:
                                                        loaded = json.load(f)
                                                        if loaded:
                                                            existing_meta = loaded
                                                            break
                                                except:
                                                    continue
                                        
                                        # Format data sesuai kebutuhan UI
                                        # PENTING: Jika ditangkap dari sniffing web, simpan sebagai _name agar di-load UI dengan benar
                                        final_meta = {
                                            "price": captured_meta.get("price", "") or existing_meta.get("price", ""),
                                            "desc": captured_meta.get("desc", "") or existing_meta.get("desc", ""),
                                            "fototree_name": captured_meta.get("fototree", "") or existing_meta.get("fototree_name", ""),
                                            "location_name": captured_meta.get("location", "") or existing_meta.get("location_name", ""),
                                            "tree_id": existing_meta.get("tree_id", ""),
                                            "location_id": existing_meta.get("location_id", ""),
                                            "updated_at": int(time.time()),
                                            "source": "manual_setup_capture"
                                        }
                                        
                                        # Save to account-specific and main metadata file
                                        for path in [
                                            os.path.join(tracker_dir, f"api_metadata_{account_name}.json"),
                                            os.path.join(tracker_dir, "api_metadata.json")
                                        ]:
                                            with open(path, "w", encoding="utf-8") as f:
                                                json.dump(final_meta, f, indent=2, ensure_ascii=False)
                                    except Exception as e:
                                        print(f"Error saving captured metadata: {e}")

                                # Save user_settings.json
                                base_dir = os.path.dirname(settings_path)
                                if base_dir:
                                    os.makedirs(base_dir, exist_ok=True)
                                tmp_path = settings_path + ".tmp"
                                with open(tmp_path, "w", encoding="utf-8") as f:
                                    json.dump(settings, f, ensure_ascii=False)
                                    f.flush()
                                    try:
                                        os.fsync(f.fileno())
                                    except Exception:
                                        pass
                                os.replace(tmp_path, settings_path)
                                return True
                            except Exception:
                                try:
                                    tmp_path = os.path.join(get_app_data_dir(), "user_settings.json.tmp")
                                    if os.path.exists(tmp_path):
                                        os.remove(tmp_path)
                                except Exception:
                                    pass
                                return False

                        waited = 0
                        detected_once = False
                        last_captured_meta = {}

                        while self._is_running and waited < 600:
                            try:
                                # SNIFFING: Tangkap metadata yang sedang diisi user secara realtime
                                try:
                                    price_el = page.locator(SELECTORS["price_input"]).first
                                    desc_el = page.locator(SELECTORS["desc_input"]).first
                                    tree_el = page.locator(SELECTORS["tree_search"]).first
                                    loc_el = page.locator(SELECTORS["loc_trigger"]).first

                                    if price_el.count() > 0:
                                        val = (price_el.input_value(timeout=100) or "").strip()
                                        if val and val.isdigit(): last_captured_meta["price"] = val
                                    
                                    if desc_el.count() > 0:
                                        val = (desc_el.input_value(timeout=100) or "").strip()
                                        if val and len(val) > 2: last_captured_meta["desc"] = val

                                    # MUTUAL EXCLUSION SNIFFING: Hanya tangkap yang visible dan enabled
                                    # Reset temp values in each loop to capture the LATEST state
                                    current_loop_tree = ""
                                    current_loop_loc = ""

                                    if tree_el.count() > 0 and tree_el.is_visible() and tree_el.is_enabled():
                                        # Gunakan JS untuk mengambil value terbaru
                                        val = (tree_el.evaluate("el => el.value") or "").strip()
                                        if val and not any(p in val.lower() for p in ["mencari", "searching", "pilih", "loading"]):
                                            current_loop_tree = val

                                    if loc_el.count() > 0 and loc_el.is_visible() and loc_el.is_enabled():
                                        # Gunakan JS untuk mengambil value/text terbaru
                                        val = (loc_el.evaluate("el => el.value || el.innerText") or "").strip()
                                        if val and not any(p in val.lower() for p in ["pilih lokasi", "mencari", "searching", "loading"]):
                                            current_loop_loc = val
                                    
                                    # UPDATE: Hanya simpan ke metadata jika elemen tersebut AKTIF/DIPILIH di web
                                    # Jika user mengosongkan di web, kita juga harus mengosongkan di memori penangkap
                                    last_captured_meta["fototree"] = current_loop_tree
                                    last_captured_meta["location"] = current_loop_loc
                                    
                                    # Jika satu terisi, pastikan yang lain kosong (Mutual Exclusion)
                                    if last_captured_meta.get("fototree"):
                                        last_captured_meta["location"] = ""
                                    elif last_captured_meta.get("location"):
                                        last_captured_meta["fototree"] = ""
                                except:
                                    pass

                                success = False
                                # Periksa berbagai indikator sukses (Teks, Modal Duplikat, atau Tombol Laporan)
                                for sel in (
                                    SELECTORS.get("success_text"),
                                    SELECTORS.get("dup_modal_text"),
                                    SELECTORS.get("success_modal_text2"),
                                    "button:has-text('Lihat Laporan')",
                                    "button:has-text('TUTUP')",
                                ):
                                    if not sel:
                                        continue
                                    try:
                                        if page.locator(sel).first.is_visible(timeout=800):
                                            success = True
                                            break
                                    except Exception:
                                        continue

                                if success:
                                    # Tunggu sebentar agar animasi modal selesai jika perlu
                                    time.sleep(0.5)
                                    _mark_setup_done_for_account(last_captured_meta)
                                    
                                    self.log_signal.emit("✅ Setup Lokasi & Foto Tree selesai!")
                                    if last_captured_meta:
                                        summary = []
                                        if last_captured_meta.get("fototree"): summary.append(f"Tree: {last_captured_meta['fototree']}")
                                        if last_captured_meta.get("location"): summary.append(f"Lokasi: {last_captured_meta['location']}")
                                        if summary:
                                            self.log_signal.emit(f"📝 Data terekam: {' | '.join(summary)}")
                                            
                                    self.log_signal.emit("ℹ️ Engine dihentikan. Silakan cek kembali pengaturan (Jumlah Tab, Batch, dll), lalu klik <b>JALANKAN OTOMASI</b> untuk mulai.")
                                    detected_once = True
                                    break
                            except Exception:
                                pass

                            time.sleep(1)
                            waited += 1

                        if not detected_once and self._is_running:
                            self.log_signal.emit("⚠️ Setup belum selesai. Pastikan upload manual benar-benar sampai status berhasil, lalu coba lagi.")

                        self._is_running = False
                        try:
                            self.context.close()
                        except Exception:
                            pass
                        self.finished_signal.emit()
                        return
                    if self.config.get("setup_ultra"):
                        token_paths = [
                            os.path.join(get_app_data_dir_by_name("AutoYuUltra"), "trackers", "api_token.txt"),
                            os.path.join(get_app_data_dir(), "trackers", "api_token.txt"),
                        ]
                        self.log_signal.emit("✅ Login terdeteksi. Silakan upload manual 1 file sampai berhasil untuk menangkap token.")
                        waited = 0
                        while self._is_running and waited < 600:
                            if any(os.path.exists(p) for p in token_paths):
                                self.log_signal.emit("🔑 Token terdeteksi. Setup selesai.")
                                break
                            time.sleep(1)
                            waited += 1

                        self._is_running = False
                        try:
                            self.context.close()
                        except Exception:
                            pass
                        self.finished_signal.emit()
                        return
                    self.log_signal.emit("✅ Login berhasil! Akun telah tersimpan.")
                    self.log_signal.emit("ℹ️ Engine dihentikan otomatis. Silakan isi data upload untuk memulai otomasi.")
                    # Tutup langsung tanpa delay agar user tidak menunggu
                    self._is_running = False
                    try:
                        self.context.close()
                    except:
                        pass
                    self.finished_signal.emit()
                    return

                self.log_signal.emit("Login dikonfirmasi. Memulai proses...")
                
                requested_tabs = self.config['tabs']
                num_tabs = requested_tabs
                
                # Batasi tab hanya jika AutoCalc aktif; manual bebas
                if bool(self.config.get('auto_calc')):
                    if requested_tabs > 20:
                        num_tabs = 20
                        self.log_signal.emit(f"Membatasi tab aktif menjadi {num_tabs} demi stabilitas sistem.")
                
                # Gunakan _get_files dari helper jika ada, atau os.listdir
                def _get_files_with_filter(folder_path):
                    try:
                        # USER FIX: SINKRONISASI LOGIKA DETEKSI FILE DENGAN UI
                        # Menggunakan os.walk agar konsisten dan lebih handal di macOS
                        real_folder = os.path.abspath(os.path.expanduser(folder_path))
                        
                        upload_type = self.config.get('type', 'foto')
                        if upload_type == 'foto':
                            exts = ('.jpg', '.jpeg', '.png', '.webp')
                        else:
                            exts = ('.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.3gp', '.m4v', '.mpg', '.mpeg')
                            
                        all_found = []
                        for root, dirs, files in os.walk(real_folder):
                            # Abaikan folder internal
                            if 'processed' in dirs: dirs.remove('processed')
                            if 'failed' in dirs: dirs.remove('failed')
                            
                            for name in files:
                                # macOS / Linux: Abaikan file bayangan (._*) dan file sistem (.DS_Store)
                                if name.startswith('._') or name.startswith('.DS_Store'):
                                    continue
                                    
                                if name.lower().endswith(exts):
                                    full_path = os.path.join(root, name)
                                    all_found.append(os.path.abspath(full_path))
                        
                        # Filter unik dan sorting
                        unique_files = sorted(list(set(all_found)))
                        return unique_files
                    except Exception as e:
                        print(f"Error listing files: {e}")
                        return []

                all_files = _get_files_with_filter(self.config['folder'])
                
                # USER FIX: SINKRONISASI TRACKER PATH (Mac Compatibility)
                folder_hash = _get_folder_hash(self.config['folder'])
                self.history_file = os.path.join(account_root, f"tracker_{folder_hash}.json")
                self.uploaded_history = self._load_history()

                if not all_files:
                    self.log_signal.emit("Tidak ada file di folder!")
                    # BERI INFO TAMBAHAN: Mungkin folder salah atau ekstensi tidak didukung
                    self.log_signal.emit(f"ℹ️ Pastikan folder {os.path.basename(self.config['folder'])} berisi file JPG/PNG/MP4.")
                    self.context.close()
                    self.finished_signal.emit()
                    return

                # Batasi total file hanya saat AutoCalc aktif (Limit 1jt untuk SD Card besar)
                if bool(self.config.get('auto_calc')) and len(all_files) > 1000000:
                    self.log_signal.emit("Membatasi total file ke 1000000 untuk menjaga stabilitas.")
                    all_files = all_files[:1000000]
                total_files = len(all_files)

                batch_per_tab = self.config.get('batch_size', 500)
                upload_type = self.config.get('type', 'foto')
                
                # Hard limit for video
                if upload_type == 'video' and batch_per_tab > 25:
                    batch_per_tab = 25
                    self.config['batch_size'] = 25 # Update config for TabAutomation
                    self.log_signal.emit(f"⚠️ Membatasi batch video ke 25 file per tab agar lebih stabil.")

                if all_files:
                    # Optimize num_tabs based on batch_size if it's too many tabs for too few files
                    # especially important for "Retry Failed"
                    import math
                    actual_batch = self.config.get('batch_size', 500)
                    
                    # If we have very few files compared to (num_tabs * actual_batch), 
                    # we should reduce num_tabs to respect the batch_size setting.
                    if len(all_files) < (num_tabs * actual_batch):
                        optimized_tabs = math.ceil(len(all_files) / actual_batch)
                        if optimized_tabs < num_tabs:
                            if self.config.get("retry_failed_only"):
                                self.log_signal.emit(f"Mengoptimalkan jumlah tab: {num_tabs} -> {optimized_tabs} (berdasarkan sisa {len(all_files)} file)")
                            num_tabs = max(1, optimized_tabs)

                    # Distribusi file ke jumlah tab secara merata (Round-Robin)
                    file_chunks = [[] for _ in range(num_tabs)]
                    for idx, f in enumerate(all_files):
                        file_chunks[idx % num_tabs].append(f)
                    
                    # Update active num_tabs to match actual chunks created (in case files < tabs)
                    file_chunks = [c for c in file_chunks if c]
                    num_tabs = len(file_chunks)
                    
                    total_files = len(all_files)
                else:
                    file_chunks = [[] for _ in range(num_tabs)]

                # Global lock for heavy operations (only 1 tab can inject/compress at a time)
                global_lock = {'injector': None}

                tabs = []
                # Buka 1 tab dulu untuk menghindari spike awal
                t_page = page
                first_files = file_chunks[0] if file_chunks else []
                tab_auto = TabAutomation(
                    tab_id=1,
                    page=t_page,
                    files=first_files,
                    config=self.config,
                    logger_func=lambda msg: self.log_signal.emit(msg),
                    global_lock=global_lock,
                    location_update_callback=self._handle_location_resolved,
                    tree_update_callback=self._handle_fototree_resolved
                )
                tabs.append(tab_auto)
                try:
                    seeded = tab_auto._ensure_pending(all_files)
                    if seeded:
                        self.log_signal.emit("ℹ Menyiapkan daftar file untuk memastikan tidak ada yang tertinggal jika terjadi gangguan.")
                except Exception:
                    pass
                current_tabs = 1
                engine_start_time = time.time()
                last_tab_open_time = engine_start_time

                # Round-Robin Loop
                active_tabs = True
                finished_signal_emitted = False
                last_visual_wait_log_at = 0.0
                
                # Tambahkan handler jika browser ditutup manual
                def on_browser_disconnected():
                    if self._is_running:
                        self.log_signal.emit("⚠️ Browser ditutup oleh pengguna. Menghentikan engine...")
                        self.browser_disconnected_signal.emit()
                        self._is_running = False
                        # Hentikan semua tab secara paksa
                        for t in tabs:
                            t.is_running = False

                if self.context and self.context.browser:
                    self.context.browser.on("disconnected", on_browser_disconnected)

                while self._is_running:
                    # CEK APAKAH BROWSER MASIH ADA (PENTING!)
                    if not self.context or not self.context.browser or not self.context.browser.is_connected():
                        self._is_running = False
                        break
                    
                    try:
                        if len(self.context.pages) == 0:
                            self._is_running = False
                            break
                    except:
                        self._is_running = False
                        break

                    active_count = 0
                    total_uploaded = 0
                    total_failed = 0
                    total_duplicate = 0
                    total_active = 0
                    
                    for tab in tabs:
                        if tab.is_running:
                            # CEK PAGE CLOSED/CRASH sebelum run_step
                            try:
                                # Jika browser sudah disconnected, is_closed() akan throw error
                                if not self.context or not self.context.browser or not self.context.browser.is_connected():
                                    self._is_running = False
                                    tab.is_running = False
                                    break

                                if tab.page.is_closed():
                                    self._crash_count += 1
                                    self._save_crash_recovery_state()
                                    if self._crash_count <= self._max_crash_recovery:
                                        if not self._is_running:
                                            tab.is_running = False
                                            continue
                                            
                                        self.log_signal.emit(f"⚠️ Tab {tab.tab_id} crash. Recovery {self._crash_count}/{self._max_crash_recovery} dalam 5 detik...")
                                        
                                        # Tunggu 5 detik tapi tetap responsif jika user klik STOP
                                        for _ in range(50):
                                            if not self._is_running: break
                                            time.sleep(0.1)
                                            
                                        if not self._is_running:
                                            tab.is_running = False
                                            continue
                                            
                                        # Coba reconnect/reload
                                        try:
                                            tab.page = self.context.pages[0] if self.context.pages else None
                                            if tab.page and self._is_running:
                                                tab.page.goto("https://www.fotoyu.com/upload", timeout=10000)
                                                tab.state_start_time = time.time()
                                                tab.state = AutoState.OPEN_UPLOAD_PAGE
                                                continue
                                        except:
                                            pass
                                    tab.is_running = False
                                    continue
                            except Exception:
                                pass
                            
                            # Ambil file yang sedang diproses sebelum run_step (untuk history)
                            current_batch = list(tab.current_batch_files) if tab.current_batch_files else []
                            
                            # Run one step
                            continue_run = tab.run_step()
                            
                            # Jika batch baru saja selesai (current_batch_files jadi kosong)
                            # Simpan ke history agar tidak terupload ulang jika aplikasi crash
                            if current_batch and not tab.current_batch_files:
                                for f in current_batch:
                                    self._save_history(f)

                            if continue_run:
                                active_count += 1
                            else:
                                tab.is_running = False
                                # Hanya tutup page jika SUKSES SEMUA
                                if hasattr(tab, 'page_closed') and not tab.page_closed:
                                    status_msg = f"Tab {tab.tab_id}: {tab.uploaded_count} sukses, {tab.failed_count} gagal"
                                    if tab.duplicate_count > 0:
                                        status_msg += f", {tab.duplicate_count} duplikat"
                                    self.log_signal.emit(status_msg)
                                    
                                    if tab.failed_count == 0:
                                        try:
                                            tab.page.close()
                                        except Exception:
                                            pass
                                        tab.page_closed = True
                                    else:
                                        self.log_signal.emit(f"⚠️ Tab {tab.tab_id} dibiarkan terbuka untuk pengecekan gagal.")
                        
                        # Accumulate status from all tabs (including finished ones)
                    # Gunakan tracker untuk akurasi total unik (Source of Truth)
                    current_tracking = {}
                    for t in tabs:
                        current_tracking.update(t.upload_tracking)
                    
                    # Hanya hitung yang diproses di SESI INI (cek timestamp)
                    total_uploaded = len([v for v in current_tracking.values() if v.get('status') == 'success' and v.get('timestamp', 0) >= engine_start_time])
                    total_failed = len([v for v in current_tracking.values() if v.get('status') == 'failed' and v.get('timestamp', 0) >= engine_start_time])
                    
                    total_duplicate = sum(tab.duplicate_count for tab in tabs) # Duplikat tetap dari counter
                    total_active = sum(tab.active_count for tab in tabs)
                    
                    self.progress_signal.emit(total_uploaded, total_failed, total_duplicate, total_active, total_files)
                    
                    # Tambah tab baru hanya setelah tab sebelumnya selesai kompresi (preview siap)
                    if self._is_running and current_tabs < num_tabs:
                        prev_tab = tabs[current_tabs - 1]
                        if prev_tab.compression_done:
                            # CEK KETAT: Apakah browser masih hidup sebelum mencoba buka tab baru
                            is_browser_alive = False
                            try:
                                if self.context and self.context.browser and self.context.browser.is_connected():
                                    if len(self.context.pages) > 0:
                                        is_browser_alive = True
                            except:
                                is_browser_alive = False

                            if not is_browser_alive:
                                self._is_running = False
                                break

                            self.log_signal.emit(f"Memulai Tab {current_tabs + 1} setelah Tab {prev_tab.tab_id} selesai kompresi...")
                            try:
                                # Gunakan timeout sangat singkat untuk deteksi dini
                                new_page = self.context.new_page()
                                try:
                                    new_page.set_default_timeout(15000)
                                    new_page.set_default_navigation_timeout(30000)
                                except Exception:
                                    pass
                                index = current_tabs
                                new_files = file_chunks[index] if index < len(file_chunks) else []
                                new_tab = TabAutomation(
                                    tab_id=index+1,
                                    page=new_page,
                                    files=new_files,
                                    config=self.config,
                                    logger_func=lambda msg: self.log_signal.emit(msg),
                                    global_lock=global_lock,
                                    location_update_callback=self._handle_location_resolved,
                                    tree_update_callback=self._handle_fototree_resolved
                                )
                                tabs.append(new_tab)
                                current_tabs += 1
                            except Exception as e:
                                self.log_signal.emit(f"⚠️ Gagal membuka tab baru: Browser ditutup.")
                                self._is_running = False
                                break
                    
                    # Berhenti jika tidak ada tab aktif DAN semua tab sudah dibuka
                    # Beri waktu konfirmasi visual pasca-submit agar tidak terlalu cepat menyimpulkan gagal.
                    if active_count == 0 and current_tabs >= num_tabs:
                        confirm_delay_sec = float(self.config.get("visual_confirm_delay_sec", 4))
                        now = time.time()
                        has_recent_submit = any(
                            getattr(t, "last_submit_at", 0) and (now - getattr(t, "last_submit_at", 0)) < confirm_delay_sec
                            for t in tabs
                        )
                        has_pending_batch = any(bool(getattr(t, "current_batch_files", [])) for t in tabs)
                        if has_recent_submit or has_pending_batch:
                            now_log = time.time()
                            if now_log - last_visual_wait_log_at >= 1.5:
                                self.log_signal.emit("ℹ Menunggu konfirmasi visual sebelum ringkasan akhir...")
                                last_visual_wait_log_at = now_log
                            time.sleep(0.6)
                            continue
                        break
                        
                    time.sleep(0.1)

            # --- SELESAI LOOP ---
            
            # 0. Grace period final untuk konfirmasi visual sebelum cleanup/ringkasan.
            try:
                final_confirm_delay = float(self.config.get("visual_confirm_delay_sec", 4))
                if final_confirm_delay > 0:
                    self.log_signal.emit("ℹ Verifikasi akhir hasil unggah...")
                    end_at = time.time() + final_confirm_delay
                    while time.time() < end_at and self._is_running:
                        progressed = False
                        for tab in tabs:
                            if not getattr(tab, "current_batch_files", None):
                                continue
                            try:
                                if tab.confirm_upload():
                                    tab.run_step()
                                    progressed = True
                            except Exception:
                                pass
                        if not progressed:
                            time.sleep(0.4)
            except Exception:
                pass

            # 1. Cleanup: Tandai SEMUA file sisa sebagai gagal sebelum hitung laporan
            active_files_found = False
            
            # 1a. Handle files di tab yang sudah terbuka
            for tab in tabs:
                remaining_in_tab = []
                # File yang sedang diproses
                if tab.current_batch_files:
                    remaining_in_tab.extend(tab.current_batch_files)
                # File yang belum sempat diproses di tab tersebut
                if tab.file_index < len(tab.all_files):
                    remaining_in_tab.extend(tab.all_files[tab.file_index:])
                
                # Unikkan list
                remaining_in_tab = list(dict.fromkeys(remaining_in_tab))
                
                # Saring: HANYA pindahkan file yang statusnya BUKAN 'success' di tracker
                actual_failed_to_move = []
                for f_path in remaining_in_tab:
                    try:
                        if hasattr(tab, "_get_file_status"):
                            if tab._get_file_status(f_path) != 'success':
                                actual_failed_to_move.append(f_path)
                        else:
                            f_name = os.path.basename(f_path)
                            if tab.upload_tracking.get(f_name, {}).get('status') != 'success':
                                actual_failed_to_move.append(f_path)
                    except Exception:
                        actual_failed_to_move.append(f_path)
                
                if actual_failed_to_move:
                    if not active_files_found:
                        self.log_signal.emit("⚠️ Pembersihan: Menandai sisa file sebagai gagal...")
                        active_files_found = True
                    try:
                        tab._mark_batch(actual_failed_to_move, 'failed')
                        tab.current_batch_files = []
                    except:
                        pass
            
            # 1b. Handle files di chunks yang BELUM sempat dibuat tab-nya (PENTING!)
            if current_tabs < len(file_chunks):
                unassigned_files = []
                for i in range(current_tabs, len(file_chunks)):
                    unassigned_files.extend(file_chunks[i])
                
                if unassigned_files:
                    # Saring juga untuk chunks yang belum terbuka
                    # (Walaupun kemungkinan besar belum ada yang sukses, tetap kita cek demi akurasi)
                    actual_unassigned_failed = []
                    if tabs:
                        proxy_tab = tabs[0]
                        for f_path in unassigned_files:
                            try:
                                if hasattr(proxy_tab, "_get_file_status"):
                                    if proxy_tab._get_file_status(f_path) != 'success':
                                        actual_unassigned_failed.append(f_path)
                                else:
                                    f_name = os.path.basename(f_path)
                                    if proxy_tab.upload_tracking.get(f_name, {}).get('status') != 'success':
                                        actual_unassigned_failed.append(f_path)
                            except Exception:
                                actual_unassigned_failed.append(f_path)
                    
                    if actual_unassigned_failed:
                        if not active_files_found:
                            self.log_signal.emit("⚠️ Pembersihan: Menandai sisa antrian sebagai gagal...")
                            active_files_found = True
                        
                        if tabs:
                            proxy_tab = tabs[0]
                            try:
                                proxy_tab._mark_batch(actual_unassigned_failed, 'failed')
                            except:
                                pass

            # 2. Hitung total akhir
            # 2a. Statistik sesi: gunakan tracker runtime (berisi timestamp sesi ini)
            session_tracking = {}
            for tab in tabs:
                try:
                    session_tracking.update(getattr(tab, "upload_tracking", {}) or {})
                except Exception:
                    pass

            session_success = len([
                v for v in session_tracking.values()
                if v.get('status') == 'success' and v.get('timestamp', 0) >= engine_start_time
            ])
            session_failed = len([
                v for v in session_tracking.values()
                if v.get('status') in ('failed', 'pending') and v.get('timestamp', 0) >= engine_start_time
            ])

            # 2b. Statistik global
            all_tracking = {}
            for tab in tabs:
                try:
                    all_tracking.update(getattr(tab, "upload_tracking", {}) or {})
                except Exception:
                    pass

            total_all = len([v for v in all_tracking.values() if v.get('status') == 'success'])
            final_total_failed = len([v for v in all_tracking.values() if v.get('status') in ('failed', 'pending')])

            # 3. Kirim Pop-up (Gunakan data SESI INI yang sudah diperbaiki)
            if not finished_signal_emitted:
                # Update progress bar satu kali terakhir agar sinkron dengan ringkasan
                total_duplicate = sum(tab.duplicate_count for tab in tabs)
                self.progress_signal.emit(session_success, session_failed, total_duplicate, 0, total_files)
                
                self.batch_finished_signal.emit(session_success, session_failed)
                finished_signal_emitted = True
                self.log_signal.emit(f"✅ Selesai. Sesi ini: {session_success} sukses, {session_failed} gagal.")
            
            # 4. Tampilkan Ringkasan di Log
            self.log_signal.emit("\n" + "="*30)
            self.log_signal.emit("🏁 SEMUA TUGAS SELESAI")
            self.log_signal.emit(f"📊 RINGKASAN SESI INI:")
            
            # Hitung statistik per tab dari memory (Sesi ini)
            for tab in tabs:
                tab_session_success = len([
                    v for v in session_tracking.values()
                    if v.get('status') == 'success' and v.get('timestamp', 0) >= engine_start_time and v.get('tab_id') == tab.tab_id
                ])
                tab_session_failed = len([
                    v for v in session_tracking.values()
                    if v.get('status') in ('failed', 'pending') and v.get('timestamp', 0) >= engine_start_time and v.get('tab_id') == tab.tab_id
                ])
                
                self.log_signal.emit(f"Tab {tab.tab_id}: {tab_session_success} sukses, {tab_session_failed} gagal")
            
            self.log_signal.emit("\n📊 TOTAL GLOBAL:")
            self.log_signal.emit(f"TOTAL SUKSES: {total_all} file")
            self.log_signal.emit(f"TOTAL GAGAL: {final_total_failed} file")
            self.log_signal.emit("="*30 + "\n")
            
            # Cleanup browser context (Hanya jika SEMUA SUKSES)
            if final_total_failed == 0:
                self.log_signal.emit("💡 Semua sukses! Menutup browser...")
                try:
                    if hasattr(self, 'context') and self.context:
                        self.context.close()
                except Exception as e:
                    pass
            else:
                self.log_signal.emit(f"⚠️ Terdeteksi {final_total_failed} file gagal.")
                self.log_signal.emit("💡 Browser tetap dibuka agar Anda bisa mengecek status di website.")
                self.log_signal.emit("💡 Jika internet sudah nyala, Anda bisa klik 'Unggah' manual atau restart aplikasi.")
            
            self.finished_signal.emit()

        except Exception as e:
            error_msg = str(e).split('\n')[0]
            self.log_signal.emit(f"❌ Terjadi kesalahan sistem: {error_msg}")
            # JANGAN tutup context di sini agar browser tetap terbuka saat crash
            self.finished_signal.emit()

    def confirm_login(self):
        self._login_confirmed = True

    def _get_ram_usage(self):
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return int(stat.dwMemoryLoad)
        except Exception:
            return 0

    def stop(self):
        self._is_running = False
        self._save_crash_recovery_state()
        self.log_signal.emit("Berhenti...")

    def _save_crash_recovery_state(self):
        """Simpan state saat crash untuk recovery nanti"""
        try:
            state = {
                'timestamp': time.time(),
                'crash_count': self._crash_count,
                'uploaded_history': list(self.uploaded_history),
            }
            if self.history_file:
                recovery_file = self.history_file + '.recovery'
                with open(recovery_file, 'w') as f:
                    json.dump(state, f)
                
                # Sembunyikan file di Windows
                if os.name == 'nt':
                    try:
                        ctypes.windll.kernel32.SetFileAttributesW(recovery_file, 2)
                    except:
                        pass
        except:
            pass

    def _load_crash_recovery_state(self):
        """Load state recovery jika ada"""
        try:
            if self.history_file:
                recovery_file = self.history_file + '.recovery'
                if os.path.exists(recovery_file):
                    with open(recovery_file, 'r') as f:
                        state = json.load(f)
                    # Cek jika recovery file < 1 jam
                    if time.time() - state.get('timestamp', 0) < 3600:
                        self._crash_count = state.get('crash_count', 0) + 1
                        self.uploaded_history = set(state.get('uploaded_history', []))
                        return True
        except:
            pass
        return False

    def _get_file_id(self, filepath, base_folder=None):
        try:
            abs_path = os.path.abspath(filepath)
            stats = os.stat(filepath)
            size = stats.st_size
            mtime = int(stats.st_mtime)
            rel = os.path.basename(abs_path)
            if base_folder:
                try:
                    rel = os.path.relpath(abs_path, base_folder)
                except Exception:
                    rel = os.path.basename(abs_path)
            
            rel = rel.replace("\\", "/").lstrip("./")
            rel_clean = rel
            if os.name == 'nt':
                rel_clean = rel_clean.lower()
            return f"{rel_clean}_{size}_{mtime}"
        except:
            return os.path.basename(filepath)

    def _get_tracker_file(self, folder):
        try:
            folder_path = os.path.abspath(folder) if folder else ""
            if folder_path.endswith(':') and os.name == 'nt':
                folder_path += os.sep

            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()[:12]
            if sys.platform == 'darwin':
                base_local = os.path.expanduser("~/Library/Application Support/AutoYuPro")
            else:
                base_local = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
            
            tracker_file = os.path.join(base_local, "trackers", f"tracker_{folder_hash}.json")
            if not os.path.exists(tracker_file):
                # Fallback ke tracker lokal di folder (jika ada)
                local_tracker = os.path.join(folder_path, ".upload_tracker.json")
                if os.path.exists(local_tracker):
                    return local_tracker
            return tracker_file
        except:
            return None

    def _get_failed_files_from_tracker(self, folder, valid_exts):
        folder = os.path.abspath(folder) if folder else folder
        if folder and folder.endswith(':') and os.name == 'nt':
            folder += os.sep

        tracker_file = self._get_tracker_file(folder)
        tracking_data = {}
        if tracker_file and os.path.exists(tracker_file):
            try:
                with open(tracker_file, 'r', encoding='utf-8') as f:
                    tracking_data = json.load(f) or {}
            except:
                pass

        if not tracking_data:
            return []

        failed_files = []
        seen = set()

        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                if filename.startswith('._') or filename.startswith('.DS_Store'):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in valid_exts:
                    continue
                
                path = os.path.join(root, filename)
                file_id = self._get_file_id(path, folder)
                
                status_data = tracking_data.get(file_id)
                if status_data is None:
                    # Fallback legacy ID
                    try:
                        st = os.stat(path)
                        legacy_id = f"{os.path.basename(path)}_{st.st_size}_{int(st.st_mtime)}"
                        status_data = tracking_data.get(legacy_id)
                    except: pass
                
                if status_data is None:
                    status_data = tracking_data.get(os.path.basename(path))

                status = status_data.get('status') if isinstance(status_data, dict) else None
                if status in ('failed', 'pending'):
                    key = os.path.normpath(os.path.abspath(path)).lower() if os.name == 'nt' else os.path.normpath(os.path.abspath(path))
                    if key not in seen:
                        seen.add(key)
                        failed_files.append(path)

        failed_files.sort()
        return failed_files

    def _get_files(self, folder):
        # Deteksi type dari config
        upload_type = self.config.get('type', 'foto')
        if upload_type == 'video':
            valid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.3gp', '.m4v', '.mpg', '.mpeg'}
        else:
            valid_exts = {'.jpg', '.jpeg', '.png'}
        
        # Normalisasi folder path
        if folder:
            folder = os.path.abspath(folder)
            if folder.endswith(':') and os.name == 'nt':
                folder += os.sep
        
        if self.config.get("retry_failed_only"):
            return self._get_failed_files_from_tracker(folder, valid_exts)
                
        files = []
        if not folder or not os.path.exists(folder):
            return []

        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                if filename.startswith('._') or filename.startswith('.DS_Store'):
                    continue
                    
                ext = os.path.splitext(filename)[1].lower()
                if ext in valid_exts:
                    files.append(os.path.join(root, filename))
        files.sort()
        return files

    # Monitor kirim ulang dinonaktifkan
