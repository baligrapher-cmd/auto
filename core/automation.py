import os
import sys
import json
import time
import shutil
import ctypes
import re
import urllib.request
import urllib.error
from playwright.sync_api import Page
from core.state_machine import AutoState, UploadMode, MODE_CONFIG
from core.license import check_license

#region debug-point tab-next-compress-setup
_TRAE_DBG_URL = None
_TRAE_DBG_SESSION = None
_TRAE_DBG_ENV_TRIED = False

def _trae_dbg__load_env_once():
    global _TRAE_DBG_URL, _TRAE_DBG_SESSION, _TRAE_DBG_ENV_TRIED
    if _TRAE_DBG_ENV_TRIED:
        return
    _TRAE_DBG_ENV_TRIED = True

    _TRAE_DBG_URL = os.environ.get("DEBUG_SERVER_URL") or None
    _TRAE_DBG_SESSION = os.environ.get("DEBUG_SESSION_ID") or None

    candidates = []
    try:
        candidates.append(os.path.join(os.getcwd(), ".dbg", "tab-next-compress.env"))
    except Exception:
        pass
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.abspath(os.path.join(here, "..", ".dbg", "tab-next-compress.env")))
    except Exception:
        pass

    for p in candidates:
        try:
            if not p or not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    if not line or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = (k or "").strip()
                    v = (v or "").strip()
                    if k == "DEBUG_SERVER_URL" and v:
                        _TRAE_DBG_URL = v
                    elif k == "DEBUG_SESSION_ID" and v:
                        _TRAE_DBG_SESSION = v
        except Exception:
            continue

def _trae_dbg(event, **fields):
    _trae_dbg__load_env_once()
    if not _TRAE_DBG_URL:
        return
    payload = {
        "ts": time.time(),
        "sessionId": _TRAE_DBG_SESSION or "tab-next-compress",
        "event": str(event),
        "fields": fields,
    }
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            _TRAE_DBG_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.2).read()
    except Exception:
        return
#endregion debug-point tab-next-compress-setup

# ==========================================
# CENTRALIZED SELECTORS (Production Standard)
# ==========================================
SELECTORS = {
    # API Configuration - Mudah diupdate jika server berubah
    "api_base_url": "api.fotoyu.com",
    "api_endpoint": "/gs/v2/creations/link",
    "url_upload": "https://www.fotoyu.com/upload",
    "trigger_foto": "div:has-text('Foto')",
    "trigger_video": "div:has-text('Pratinjau Video')",
    "trigger_container": "div[class*='StyledUploadPhotoContainer']",
    "preview_ready": "img[src^='blob:'], img[src^='data:']",
    "video_preview_ready": "video[src^='blob:'], video[src^='data:']",
    "compressing": "text=Mengompres",
    "price_input": "input[placeholder*='Harga']",
    "desc_input": "textarea",
    "submit_text": "Unggah",
    "submit_button": "button:has-text('Unggah'), button[type='submit'], div[role='button']:has-text('Unggah'), div[data-testid='button']:has-text('Unggah')",
    "success_text": "text=Berhasil, text=Diunggah, text=Success",
    # Hindari false-positive dari teks umum seperti 'Error'/'Wajib' yang sering muncul di form.
    # Diperketat agar hanya mencari di elemen yang kemungkinan besar adalah modal/toast error
    "error_text": "div[role='alert'] >> text=/gagal|kendala|kesalahan|koneksi|internet|coba\\s+ulang|duplikat|sudah\\s+pernah/i, div[class*='modal'] >> text=/gagal|kendala|kesalahan|koneksi|internet|coba\\s+ulang|duplikat|sudah\\s+pernah/i, .error-message >> text=/gagal|kesalahan|duplikat/i",
    "uploading": "text=Mengunggah, .progress-bar, .upload-indicator",
    "counter_text": "text=/\\d+\\s*\\/\\s*\\d+\\s*(Konten|foto|video|items|files|image)/i",
    "dup_modal_text": "text=/Diunggah|terdeteksi\\s+sebagai\\s+duplikat/i",
    "success_modal_text2": "text=/Selesai!|Semua\\s+konten\\s+telah\\s+berhasil\\s+diunggah/i",
    "modal_ok": "div[data-testid='button']:has-text('OK'), div[data-testid='button']:has-text('Tutup'), button:has-text('OK'), button:has-text('TUTUP'), button:has-text('Nanti Saja'), button:has-text('NANTI SAJA')",
    "modal_retry": "button:has-text('Ulangi'), div[role='button']:has-text('Ulangi'), div[data-testid='button']:has-text('Ulangi'), [label='Ulangi'], div:has-text('Ulangi')",
    "btn_next": "button:has-text('Selanjutnya'), button:has-text('Lanjut'), button:has-text('Next'), button:has-text('Berikutnya')",
    "tree_search": "input[placeholder*='FotoTree'], input[placeholder*='Cari FotoTree'], input[placeholder*='Ketik nama FotoTree']",
    "loc_trigger": "input[placeholder*='Pilih Lokasi'], div:has-text('Pilih Lokasi'), div[data-testid*='location-trigger'], .location-selector",
    "loc_search": "input[placeholder*='Cari Lokasi'], input[placeholder*='Cari lokasi'], input[placeholder*='Search'], input[class*='search'], input[class*='Search']",
    "loc_save": "button:has-text('Simpan Perubahan'), button:has-text('Simpan'), button:has-text('Pilih Lokasi'), div[role='button']:has-text('Simpan'), div[data-testid='button']:has-text('Simpan Perubahan'), span:has-text('Simpan Perubahan')"
}

class TabAutomation:
    def _normalize_text_value(self, value):
        return str(value or "").strip()

    def _state_label(self):
        try:
            state_val = self.state.value if hasattr(self.state, "value") else str(self.state)
        except Exception:
            state_val = "UNKNOWN"

        mapping = {
            "OPEN_UPLOAD_PAGE": "membuka halaman upload",
            "WAIT_QUEUE": "antrian (menunggu tab lain selesai injeksi)",
            "SELECT_MODE": "memilih mode foto/video & injeksi file",
            "SET_FILES": "memasukkan file ke uploader",
            "WAIT_PREVIEW": "menunggu pratinjau / kompresi",
            "WAIT_METADATA_CONTAINER": "menunggu form metadata",
            "FILL_METADATA": "mengisi harga/deskripsi",
            "VERIFY_FILLED": "verifikasi input metadata",
            "FILL_LOCATION": "mengisi lokasi",
            "SUBMIT": "klik tombol Unggah",
            "CONFIRM_SUCCESS": "verifikasi hasil upload",
        }
        return mapping.get(state_val, state_val)

    def _error_guidance(self, err_str):
        err_str = str(err_str or "")
        low = err_str.lower()
        stage = self._state_label()

        if any(k in low for k in ["net::err_internet_disconnected", "internet_disconnected", "err_name_not_resolved", "err_connection_timed_out", "err_connection_reset", "err_network_changed", "dns", "name not resolved"]):
            return (
                f"🌐 Internet bermasalah saat {stage}.",
                [
                    "Pastikan internet stabil (WiFi/Hotspot), matikan VPN, lalu coba lagi.",
                    "Jika memakai jaringan kantor/kampus: cek pengaturan keamanan/antivirus yang mungkin memblokir koneksi.",
                ],
            )

        if "timeout" in low or "timed out" in low:
            return (
                f"⏱️ Timeout saat {stage} (tab kemungkinan nge-freeze / server lambat).",
                [
                    "Tunggu 10–20 detik, jika masih sama klik STOP lalu jalankan lagi.",
                    "Kurangi jumlah TAB / batch per tab untuk stabilitas (terutama PC RAM kecil).",
                ],
            )

        if any(k in low for k in ["execution context was destroyed", "cannot find context with specified id", "frame was detached", "navigation interrupted", "net::err_aborted"]):
            return (
                f"🔄 Halaman sedang refresh/redirect saat {stage}.",
                [
                    "Ini normal setelah klik Unggah. Sistem akan verifikasi ulang hasil upload.",
                ],
            )

        if any(k in low for k in ["target closed", "page closed", "browser closed", "context or browser has been closed"]):
            return (
                "⚠️ Browser/Tab tertutup.",
                [
                    "Jangan menutup browser saat engine berjalan. Jika terlanjur, gunakan 'LANJUTKAN SISA GAGAL'.",
                ],
            )

        return (
            f"❌ Terjadi kendala saat {stage}.",
            [
                "Jika ini berulang: klik STOP, tutup browser, lalu jalankan ulang.",
            ],
        )

    def __init__(self, tab_id: int, page: Page, files: list, config: dict, logger_func, global_lock=None, location_update_callback=None, tree_update_callback=None):
        self.tab_id = tab_id
        self.page = page
        self.all_files = files
        self.config = config
        self.log = logger_func
        self.global_lock = global_lock if global_lock is not None else {}
        
        self.state = AutoState.INIT
        self.state_start_time = 0
        self.retries = 0
        self.submit_retries = 0
        self.modal_retry_count = 0
        self.batch_failed_after_retry = False
        self.batch_finished = False
        self.last_submit_at = 0.0
        self._last_exception_log_at = 0.0
        self._last_post_submit_wait_log_at = 0.0
        self._last_guidance_log_at = 0.0
        
        self.current_batch_files = []
        self.batch_size = config.get('batch_size', 1)
        self.file_index = 0
        self.upload_type = config.get('type', 'foto')
        
        self.price = config.get('price', '8000')
        self.desc = config.get('desc', '')
        
        self.fototree = self._normalize_text_value(config.get('fototree', '')) or None
        self.fototree_keyword = str(self.fototree or "").strip()
        self.fototree_locked = bool(config.get("fototree_locked")) and bool(self.fototree_keyword)
        self.tree_update_callback = tree_update_callback

        raw_location = self._normalize_text_value(config.get('location', ''))
        self.location = raw_location.strip() if raw_location else None
        self.location_keyword = str(self.location or "").strip()
        self.location_update_callback = location_update_callback
        
        self._resolved_tree = self.fototree_keyword if self.fototree_locked else None
        self._resolved_location = self.location_keyword if self.location_keyword else None
        self._last_tree_log_key = None
        self._last_location_log_key = None
        
        self.is_running = True
        self.uploaded_count = 0
        self.failed_count = 0
        self.duplicate_count = 0
        self.active_count = 0

        # Optimized Write Batching
        self._pending_tracker_updates = {}
        self._last_tracker_save = 0.0
        self._tracker_save_interval = 5.0  # Save at most every 5 seconds

        # Network Intercept for JSON Response
        self.last_api_response = None
        self.api_responses = [] # Daftar untuk menampung semua respon dalam satu batch
        self.page.on("requestfinished", self._handle_network_request_finished)

        # Mode engine dikunci SAFE (utama + lite).
        self.mode = UploadMode.SAFE
        self.mode_config = MODE_CONFIG[UploadMode.SAFE]
        # Lite memakai mode SAFE, jadi pakai flag terpisah agar tidak bentrok enum mode.
        self.is_lite = bool(config.get("is_lite") or config.get("lite_mode"))
        self.turbo_errors = 0
        self.compression_done = False
        self.first_compression_done = False  # New flag: stays True after first compression completes
        self.injection_done = False
        self.page_closed = False
        self.visual_success_detected = False # Flag untuk Hybrid Verification
        self.redirect_success_detected = False # Flag untuk deteksi redirect ke profil sebagai sukses
        self._conn_fail_count = 0 # Counter toleransi koneksi internet

        self.source_dir = config.get('folder', '')
        self._created_dirs = set() # Cache untuk folder yang sudah dibuat

        # Normalisasi source_dir agar selalu absolute dan konsisten
        if self.source_dir:
            self.source_dir = os.path.abspath(self.source_dir)
            # Pastikan drive root seperti E: menjadi E:\
            if self.source_dir.endswith(':') and os.name == 'nt':
                self.source_dir += os.sep

        # JSON Tracker - Source of Truth untuk akurasi 100%
        # Mode Full: Selalu simpan tracker di folder AppData komputer agar folder sumber tetap bersih
        try:
            import hashlib
            # Normalisasi path untuk hash agar case-insensitive di Windows
            hash_path = self.source_dir
            if os.name == 'nt':
                hash_path = hash_path.lower()
            
            # Buat hash dari path folder agar tracker unik per folder sumber
            folder_hash = hashlib.md5(hash_path.encode()).hexdigest()[:12]
            
            if sys.platform == 'darwin':
                base_local = os.path.expanduser("~/Library/Application Support/AutoYuPro")
            else:
                base_local = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
            
            tracker_dir = os.path.join(base_local, "trackers")
            os.makedirs(tracker_dir, exist_ok=True)
            self.tracker_file = os.path.join(tracker_dir, f"tracker_{folder_hash}.json")
        except:
            self.tracker_file = os.path.join(self.source_dir, ".upload_tracker.json") if self.source_dir else None
            
        self.upload_tracking = {} # {file_id: {status, timestamp, tab_id, filename}}
        self._load_tracker()

        # FILTER: Hapus file yang sudah sukses dari daftar antrean
        if self.all_files:
            original_count = len(self.all_files)
            # Hanya simpan file yang statusnya bukan 'success'
            # USER FIX: File 'failed' harus tetap masuk antrean agar bisa di-resume
            self.all_files = [f for f in self.all_files if self._get_file_status(f) != 'success']
            filtered_count = len(self.all_files)
            if original_count != filtered_count:
                skipped = original_count - filtered_count
                self.log(f"ℹ Tab {self.tab_id}: Mengabaikan {skipped} file yang sudah sukses terunggah.")
            
            # Jika semua file terfilter (semua sudah sukses), beri info jelas
            if original_count > 0 and not self.all_files:
                self.log(f"✅ Tab {self.tab_id}: Semua file di folder ini sudah berstatus SUKSES di tracker.")
        
        # Logika folder processed/failed dihapus. Menggunakan Mode Full (Tracker Only).
        self.processed_dir = None
        self.failed_dir = None

    def _move_files(self, files, target_dir_base):
        """Bypass pemindahan file (Mode Full)."""
        return

    def _load_tracker(self):
        """Muat tracker dari file JSON"""
        if not self.tracker_file:
            return
        try:
            if os.path.exists(self.tracker_file):
                with open(self.tracker_file, 'r', encoding='utf-8') as f:
                    self.upload_tracking = json.load(f) or {}
                if not isinstance(self.upload_tracking, dict):
                    self.upload_tracking = {}
        except Exception:
            self.upload_tracking = {}
            try:
                bak = self.tracker_file + ".bak"
                if os.path.exists(bak):
                    with open(bak, 'r', encoding='utf-8') as f:
                        data = json.load(f) or {}
                    if isinstance(data, dict):
                        self.upload_tracking = data
            except Exception:
                self.upload_tracking = {}

    def _save_tracker(self):
        """Simpan tracker ke file JSON dengan me-merge data terbaru dari disk untuk mencegah overwriting antar tab."""
        if not self.tracker_file:
            return
        try:
            tracker_dir = os.path.dirname(self.tracker_file)
            if tracker_dir:
                os.makedirs(tracker_dir, exist_ok=True)

            # 1. Reload dari disk & Merge (PENTING untuk multi-tab)
            if os.path.exists(self.tracker_file):
                try:
                    with open(self.tracker_file, 'r', encoding='utf-8') as f:
                        disk_data = json.load(f)
                        if isinstance(disk_data, dict):
                            # Simpan job_config dari disk jika ada, atau gunakan yang baru
                            job_config = disk_data.get('__job_config__', {})
                            
                            # Hanya timpa jika data di memory lebih baru atau data di disk belum ada
                            for k, v in disk_data.items():
                                if k == '__job_config__':
                                    continue
                                if k not in self.upload_tracking:
                                    self.upload_tracking[k] = v
                                else:
                                    # Opsional: Cek timestamp jika ingin lebih presisi
                                    disk_ts = v.get('timestamp', 0)
                                    mem_ts = self.upload_tracking[k].get('timestamp', 0)
                                    if disk_ts > mem_ts:
                                        self.upload_tracking[k] = v
                except:
                    pass

            # 2. Sisipkan/Update Job Config (PENTING: Agar saat dilanjutkan mengikuti setting sebelumnya)
            # Kita simpan setting utama yang krusial
            self.upload_tracking['__job_config__'] = {
                'type': self.config.get('type'),
                'tabs': self.config.get('tabs'),
                'batch_size': self.config.get('batch_size'),
                'price': self.config.get('price'),
                'desc': self.config.get('desc'),
                'fototree': self.config.get('fototree'),
                'location': self.config.get('location'),
                'updated_at': int(time.time())
            }

            # 3. Save as Atomic Operation
            tmp_path = self.tracker_file + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.upload_tracking, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except:
                    pass

            if os.path.exists(self.tracker_file):
                try:
                    shutil.copyfile(self.tracker_file, self.tracker_file + ".bak")
                except:
                    pass
            os.replace(tmp_path, self.tracker_file)
            
            # Sembunyikan file di Windows
            if os.name == 'nt':
                try:
                    # FILE_ATTRIBUTE_HIDDEN = 2
                    ctypes.windll.kernel32.SetFileAttributesW(self.tracker_file, 2)
                    try:
                        ctypes.windll.kernel32.SetFileAttributesW(self.tracker_file + ".bak", 2)
                    except Exception:
                        pass
                except:
                    pass
        except Exception:
            try:
                tmp_path = self.tracker_file + ".tmp"
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def _get_file_id(self, filepath):
        """Menghasilkan ID stabil untuk file (tetap sama meski file dipindah ke processed/failed)"""
        try:
            abs_path = os.path.abspath(filepath)
            stats = os.stat(filepath)
            size = stats.st_size
            mtime = int(stats.st_mtime) # Waktu modifikasi terakhir
            rel = os.path.basename(abs_path)
            if self.source_dir:
                try:
                    rel = os.path.relpath(abs_path, self.source_dir)
                except Exception:
                    rel = os.path.basename(abs_path)

            rel = rel.replace("\\", "/").lstrip("./")
            rel_clean = rel
            if os.name == 'nt':
                rel_clean = rel_clean.lower()
            return f"{rel_clean}_{size}_{mtime}"
        except:
            return os.path.basename(filepath)

    def _mark_file(self, filepath, status):
        """Tandai satu file dalam tracker (with batching)"""
        file_id = self._get_file_id(filepath)
        self.upload_tracking[file_id] = {
            'status': status,
            'timestamp': time.time(),
            'tab_id': self.tab_id,
            'filename': os.path.basename(filepath)
        }
        self._pending_tracker_updates[file_id] = True
        self._flush_tracker_if_needed()

    def _mark_batch(self, files, status):
        """Tandai sekelompok file dalam tracker (with batching)"""
        if not files:
            return
        now = time.time()
        for f in files:
            file_id = self._get_file_id(f)
            self.upload_tracking[file_id] = {
                'status': status,
                'timestamp': now,
                'tab_id': self.tab_id,
                'filename': os.path.basename(f)
            }
            self._pending_tracker_updates[file_id] = True
        self._flush_tracker_if_needed()

    def _flush_tracker_if_needed(self):
        """Flush tracker ke disk jika interval sudah lewat atau force"""
        now = time.time()
        if (now - self._last_tracker_save) >= self._tracker_save_interval:
            self._save_tracker()
            self._pending_tracker_updates.clear()
            self._last_tracker_save = now

    def _flush_tracker(self):
        """Force flush semua pending update ke disk"""
        if self._pending_tracker_updates:
            self._save_tracker()
            self._pending_tracker_updates.clear()
            self._last_tracker_save = time.time()

    def _ensure_pending(self, files):
        if not files:
            return 0
        now = time.time()
        updated = 0
        for f in files:
            try:
                status = self._get_file_status(f)
                if status == 'unknown':
                    file_id = self._get_file_id(f)
                    self.upload_tracking[file_id] = {
                        'status': 'pending',
                        'timestamp': now,
                        'tab_id': self.tab_id,
                        'filename': os.path.basename(f)
                    }
                    updated += 1
            except Exception:
                continue
        if updated:
            self._save_tracker()
        return updated

    def _get_file_status(self, filepath):
        """Dapatkan status satu file dari tracker"""
        file_id = self._get_file_id(filepath)
        legacy_id = None
        try:
            st = os.stat(filepath)
            legacy_id = f"{os.path.basename(filepath)}_{st.st_size}_{int(st.st_mtime)}"
        except Exception:
            legacy_id = None
        status_data = self.upload_tracking.get(file_id)
        if status_data is None and legacy_id:
            status_data = self.upload_tracking.get(legacy_id)
        if status_data is None:
            status_data = self.upload_tracking.get(os.path.basename(filepath))
        return status_data.get('status', 'unknown') if status_data else 'unknown'

    def _get_tracker_stats(self):
        """Dapatkan statistik dari tracker JSON (Source of Truth)"""
        success = sum(1 for v in self.upload_tracking.values() if v.get('status') == 'success')
        failed = sum(1 for v in self.upload_tracking.values() if v.get('status') == 'failed')
        return success, failed

    def _sync_from_folders(self):
        """Bypass sinkronisasi folder (Mode Full)."""
        return

    def assign_files(self, files):
        self.all_files = files or []
        self.file_index = 0
        self.current_batch_files = []
        self.batch_finished = False
        self.submit_retries = 0
        self.modal_retry_count = 0
        self.batch_failed_after_retry = False
        self.last_api_response = None
        self.api_responses = [] # Daftar untuk menampung semua respon dalam satu batch
        if self.all_files:
            self.state = AutoState.OPEN_UPLOAD_PAGE
            self.state_start_time = time.time()
            self.is_running = True
        else:
            self.state = AutoState.DONE
            self.is_running = False

    def _handle_network_request_finished(self, request):
        """Menangkap respon JSON dari API Unggah menggunakan requestfinished (lebih aman saat redirect)"""
        try:
            url = request.url.lower()
            # Filter: Hanya ambil respon dari API utama fotoyu
            if "api.fotoyu.com" in url:
                # [PROTOTYPE] Tangkap Token Authorization untuk Direct API
                headers = request.headers
                auth_token = headers.get("authorization") or headers.get("Authorization")
                if auth_token and len(str(auth_token).strip()) >= 20:
                    from core.license import get_app_data_dir, get_app_data_dir_by_name
                    base_dirs = [get_app_data_dir()]
                    if self.config.get("setup_ultra"):
                        base_dirs.append(get_app_data_dir_by_name("AutoYuUltra"))
                    for base_local in base_dirs:
                        token_dir = os.path.join(base_local, "trackers")
                        os.makedirs(token_dir, exist_ok=True)
                        token_file = os.path.join(token_dir, "api_token.txt")
                        try:
                            with open(token_file, "w") as f:
                                f.write(auth_token)
                        except:
                            pass

                if request.method == "POST":
                    # [PROTOTYPE] Tangkap Metadata (FotoTree & Lokasi) untuk Ultra Mode
                    try:
                        post_data = request.post_data
                        if post_data:
                            # Jika data dalam format multipart/form-data, kita bisa cari ID-nya
                            # Biasanya ID FotoTree dikirim sebagai parameter 'tree_id' atau 'tree'
                            # Dan Lokasi sebagai 'location_id' atau 'location'
                            # Simpan ke file metadata untuk dibaca UltraWorker
                            metadata_targets = []
                            try:
                                from core.license import get_app_data_dir, get_app_data_dir_by_name
                                metadata_targets = [os.path.join(get_app_data_dir(), "trackers", "api_metadata.json")]
                                # Also save to account-specific metadata file
                                account_name = str(self.config.get("current_account") or "").strip()
                                if account_name:
                                    metadata_targets.append(os.path.join(get_app_data_dir(), "trackers", f"api_metadata_{account_name}.json"))
                                if self.config.get("setup_ultra"):
                                    metadata_targets.append(os.path.join(get_app_data_dir_by_name("AutoYuUltra"), "trackers", "api_metadata.json"))
                            except:
                                metadata_targets = []

                            # Load existing metadata (prefer account-specific first)
                            existing_meta = {}
                            for metadata_file in metadata_targets:
                                if os.path.exists(metadata_file):
                                    try:
                                        with open(metadata_file, "r", encoding="utf-8") as f:
                                            loaded = json.load(f)
                                            if loaded:
                                                existing_meta = loaded
                                                break  # Stop at the first existing file
                                    except:
                                        continue
                            
                            # USER FIX: Implementasi Mutual Exclusion (Isi Salah Satu)
                            # Jika menangkap tree_id, maka location_id harus dibersihkan, dan sebaliknya.
                            changed = False
                            if "tree_id" in post_data:
                                match = re.search(r'name="tree_id"\s*\r\n\r\n(\d+)', post_data)
                                if match and match.group(1) != "0":
                                    existing_meta["tree_id"] = match.group(1)
                                    existing_meta.pop("location_id", None) # Hapus lokasi jika tree ada
                                    changed = True
                            
                            if "location_id" in post_data:
                                match = re.search(r'name="location_id"\s*\r\n\r\n(\d+)', post_data)
                                if match and match.group(1) != "0":
                                    existing_meta["location_id"] = match.group(1)
                                    existing_meta.pop("tree_id", None) # Hapus tree jika lokasi ada
                                    changed = True
                            
                            if changed:
                                for metadata_file in metadata_targets:
                                    try:
                                        os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
                                        with open(metadata_file, "w", encoding="utf-8") as f:
                                            json.dump(existing_meta, f, indent=2)
                                    except:
                                        pass
                    except:
                        pass

                    response = request.response()
                if response:
                    try:
                        data = response.json()
                        if not hasattr(self, 'api_responses'): self.api_responses = []
                        
                        # LOG RAW untuk pemantauan user (Bisa dihapus jika sudah stabil)
                        # self.log(f"DEBUG_JSON_RAW: {json.dumps(data)}")
                        
                        # 1. Deteksi sukses pendaftaran file (v3/creations)
                        # Ini adalah sinyal terkuat bahwa satu file berhasil masuk sistem
                        if "/v3/creations" in url:
                            if data.get('message') == 'OK' and 'result' in data:
                                self.api_responses.append(data)
                                self.last_api_response = data
                                # self.log(f"DEBUG_JSON_RAW: {json.dumps(data)}") # Munculkan lagi untuk tracker
                                # self.log(f"DEBUG: File terdaftar (JSON v3)")
                        
                        # 2. Fallback: Deteksi struktur lama atau list (jika ada batch)
                        elif isinstance(data, dict):
                            results = data.get('data', {}).get('results', []) or data.get('results', [])
                            if results and isinstance(results, list):
                                self.api_responses.append(data)
                                self.last_api_response = data
                                # self.log(f"DEBUG: Batch terdeteksi ({len(results)} item)")
                            
                            # Cek duplikat (tetap dianggap 'proses selesai' untuk batch ini)
                            elif data.get('message') == 'Conflict' or 'duplicate' in str(data).lower():
                                self.api_responses.append(data)
                                # self.log(f"DEBUG: Duplikat terdeteksi (JSON)")
                    except:
                        pass
        except:
            pass

    def _handle_network_response(self, response):
        # Digantikan oleh _handle_network_request_finished untuk stabilitas redirect
        pass

    def _normalize_search_text(self, value):
        text = self._normalize_text_value(value)
        return " ".join(text.lower().split())

    def _extract_primary_option_text(self, value):
        text = self._normalize_text_value(value)
        if not text:
            return ""
        text = text.replace("\r", "\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            text = lines[0]
        if "|" in text:
            text = text.split("|", 1)[0].strip()
        return text

    def _log_once(self, message, key, attr_name):
        if key and key == getattr(self, attr_name, None):
            return
        setattr(self, attr_name, key)
        self.log(message)

    def _notify_location_update(self, resolved_name, match_type, source):
        resolved_name = self._extract_primary_option_text(resolved_name)
            
        if not resolved_name:
            return

        self.location = resolved_name
        self._resolved_location = resolved_name

        if not self.location_update_callback:
            return

        try:
            self.location_update_callback(resolved_name, match_type, source)
        except Exception:
            pass

    def _notify_tree_update(self, resolved_name, match_type, source):
        resolved_name = self._extract_primary_option_text(resolved_name)
            
        if not resolved_name:
            return

        self.fototree = resolved_name
        self._resolved_tree = resolved_name

        if not self.tree_update_callback:
            return

        try:
            self.tree_update_callback(resolved_name, match_type, source)
        except Exception:
            pass

    def _collect_live_candidates(self):
        try:
            results = self.page.evaluate("""() => {
                const selectors = [
                    "[role='option']",
                    "[role='listbox'] [role='option']",
                    "[role='listbox'] div",
                    "div[class*='option']",
                    "div[class*='Option']",
                    "div[class*='item']",
                    "div[class*='Item']",
                    "li"
                ];
                const skipTexts = new Set(["Simpan", "Simpan Perubahan", "Pilih Lokasi"]);
                const seen = new Set();
                const results = [];

                for (const selector of selectors) {
                    for (const el of document.querySelectorAll(selector)) {
                        const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
                        if (!text || text.length > 120 || skipTexts.has(text)) {
                            continue;
                        }

                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (!rect.width || !rect.height) {
                            continue;
                        }
                        if (style.visibility === "hidden" || style.display === "none") {
                            continue;
                        }

                        const key = text.toLowerCase();
                        if (!seen.has(key)) {
                            seen.add(key);
                            results.push(text);
                            if (results.length >= 30) {
                                return results;
                            }
                        }
                    }
                }
                return results;
            }""")
            return results if isinstance(results, list) else []
        except Exception:
            return []

    def _clear_shared_tree_location_value(self):
        try:
            # Langkah 1: Gunakan Playwright untuk mencari tombol X secara global di area yang relevan
            clear_selectors = [
                "svg:visible",
                "button:visible",
                "[role='button']:visible",
                "span:visible"
            ]
            
            clicks_count = 0
            # Batasi pencarian ke area "Fototree / Location" untuk keamanan
            try:
                label = self.page.locator(r"text=/Fototree \/ Location/i").first
                if label.is_visible():
                    container = label.locator("xpath=..")
                    for _ in range(3):
                        if container.count() > 0:
                            container = container.locator("xpath=..")
                    
                    if container.count() > 0:
                        for sel in clear_selectors:
                            elements = container.locator(sel)
                            count = elements.count()
                            for i in range(count):
                                try:
                                    if i >= elements.count(): break
                                    target = elements.nth(i)
                                    if not target.is_visible(): continue
                                    
                                    txt = (target.text_content() or "").strip().lower()
                                    title = (target.get_attribute("title") or "").lower()
                                    is_x_text = txt in ['x', '×'] or 'hapus' in txt or 'clear' in txt or 'hapus' in title or 'clear' in title
                                    is_svg = target.evaluate("el => el.tagName.toLowerCase() === 'svg' || el.querySelector('svg')")
                                    
                                    if is_x_text or is_svg:
                                        if len(txt) > 5 and not ('hapus' in txt or 'clear' in txt):
                                            continue
                                        target.click(force=True)
                                        clicks_count += 1
                                        self.page.wait_for_timeout(200)
                                except: continue
            except: pass

            # Langkah 2: Deep Clear via JavaScript (Force reset value & state React/Vue)
            # Ini sangat penting agar state internal website benar-benar kosong
            self.page.evaluate("""() => {
                const selectors = [
                    'input[placeholder*="FotoTree"]',
                    'input[placeholder*="Lokasi"]',
                    'input[placeholder*="Location"]',
                    '.location-selector input'
                ];
                
                selectors.forEach(sel => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.value = '';
                        ['input', 'change', 'blur'].forEach(evt => {
                            el.dispatchEvent(new Event(evt, { bubbles: true }));
                        });
                    }
                });
            }""")

            # Langkah 3: Fallback JS Klik (Tetap dipertahankan untuk membersihkan UI)
            return clicks_count + self.page.evaluate("""() => {
                let clicks = 0;
                const all = Array.from(document.querySelectorAll('*'));
                const label = all.find(el => (el.innerText || '').trim().toLowerCase().includes('fototree / location'));
                if (!label) return clicks;

                let container = label;
                for (let i = 0; i < 5; i++) {
                    if (!container || !container.parentElement) break;
                    container = container.parentElement;
                }

                const candidates = Array.from(container.querySelectorAll('button, [role="button"], svg, span, i'));
                candidates.forEach(el => {
                    const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                    const title = (el.getAttribute('title') || '').toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();

                    const isClearText = text === 'x' || text === '×' || text.includes('hapus') || text.includes('clear') ||
                                        title.includes('hapus') || title.includes('clear') ||
                                        aria.includes('hapus') || aria.includes('clear');

                    if (!isClearText) return;

                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) return;
                    if (rect.width > 120 || rect.height > 120) return;

                    ['mousedown', 'mouseup', 'click'].forEach(evt => {
                        el.dispatchEvent(new MouseEvent(evt, {bubbles: true, cancelable: true, view: window}));
                    });
                    clicks++;
                });

                return clicks;
            }""")
        except Exception:
            return 0

    def _click_dropdown_option_by_name(self, option_name):
        option_name = self._extract_primary_option_text(option_name)
        if not option_name:
            return False

        exact_locators = [
            self.page.get_by_text(option_name, exact=True),
            self.page.locator(f"[role='option']").filter(has_text=option_name),
            self.page.locator(f"div").filter(has_text=option_name),
        ]
        for locator in exact_locators:
            try:
                if locator.count() > 0:
                    for idx in range(locator.count()):
                        node = locator.nth(idx)
                        if not node.is_visible(timeout=500):
                            continue
                        txt = self._extract_primary_option_text(node.text_content() or "")
                        if self._normalize_search_text(txt) != self._normalize_search_text(option_name):
                            continue
                        node.click(force=True)
                        return True
            except Exception:
                continue
        return False

    def _pick_best_match(self, keyword, candidates):
        keyword_norm = self._normalize_search_text(keyword)
        if not keyword_norm:
            return None, None

        cleaned_candidates = []
        seen = set()
        for candidate in candidates or []:
            cleaned = str(candidate or "").strip()
            if not cleaned:
                continue
            norm = self._normalize_search_text(cleaned)
            if norm in seen:
                continue
            seen.add(norm)
            cleaned_candidates.append(cleaned)

        if not cleaned_candidates:
            return None, None

        # Tanda centang hijau (verified) seringkali berupa karakter Unicode tertentu
        verified_marks = ['✅', '✔', '☑', '✓']

        def get_match_score(candidate):
            cand_norm = self._normalize_search_text(candidate)
            
            # 1. Cek Verified (Centang Hijau) - PRIORITAS TERTINGGI
            is_verified = any(mark in candidate for mark in verified_marks)
            
            # 2. Cek Exact Match
            is_exact = cand_norm == keyword_norm
            
            # 3. Cek Token Overlap
            kw_tokens = set(keyword_norm.split())
            cand_tokens = set(cand_norm.split())
            overlap = len(kw_tokens.intersection(cand_tokens))
            
            # Skor: Exact (2000) + Verified (500) + Overlap (10 per token) - Length Diff (Penalty)
            # Prioritas: Exact match adalah yang utama agar sesuai metadata yang ditangkap.
            score = (2000 if is_exact else 0) + (500 if is_verified else 0) + (overlap * 10)
            score -= abs(len(cand_norm) - len(keyword_norm))
            
            return score

        # Urutkan berdasarkan skor tertinggi
        best_candidate = max(cleaned_candidates, key=get_match_score)
        
        # Tentukan tipe match untuk logging
        final_score = get_match_score(best_candidate)
        is_verified = any(mark in best_candidate for mark in verified_marks)
        
        if is_verified:
            match_type = "verified"
        elif final_score >= 500:
            match_type = "exact"
        else:
            match_type = "partial"
        
        return best_candidate, match_type

    def _fill_location_search_input(self, search_input, value, wait_ms=1500):
        # Gunakan .fill untuk kecepatan dan reliabilitas input modern (React/Vue)
        search_input.click(force=True)
        # Hapus dulu isinya
        search_input.fill("")
        # Ketik pelan untuk memicu dropdown
        self.page.keyboard.type(value, delay=100)
        # Beri jeda agar website memproses event input
        self.page.wait_for_timeout(wait_ms)
        
        # Verifikasi apakah teks benar-benar terisi
        try:
            current = search_input.input_value()
            if not current or current.lower() != value.lower():
                search_input.fill(value)
                self.page.wait_for_timeout(wait_ms)
        except:
            pass

    def _resolve_realtime_choice(self, keyword, kind="pilihan"):
        keyword = self._normalize_text_value(keyword)
        if not keyword:
            return None

        live_candidates = self._collect_live_candidates()
        best_live, match_type = self._pick_best_match(keyword, live_candidates)
        if best_live:
            if kind == "fototree":
                self._notify_tree_update(best_live, match_type or "live", "live")
                self._log_once(
                    f"🌳 FotoTree realtime cocok: {best_live}",
                    ("tree", match_type, self._normalize_search_text(best_live)),
                    "_last_tree_log_key"
                )
            else:
                self._notify_location_update(best_live, match_type or "live", "live")
                self._log_once(
                    f"📍 Lokasi realtime cocok: {best_live}",
                    ("location", match_type, self._normalize_search_text(best_live)),
                    "_last_location_log_key"
                )
            return best_live

        return keyword

    def confirm_upload(self):
        """
        Optimized Success Detection
        Menggunakan evaluate untuk meminimalkan round-trip ke browser
        """
        if self.batch_finished:
            return True

        page = self.page
        
        # 0. CEK JSON COUNT (Struktur baru v3 & lama)
        if hasattr(self, 'api_responses') and self.api_responses:
            total_items_in_json = 0
            for resp in self.api_responses:
                if not isinstance(resp, (dict, list)): continue
                
                if isinstance(resp, list): 
                    total_items_in_json += len(resp)
                else:
                    # Cek struktur v3 (result singular)
                    if resp.get('message') == 'OK' and 'result' in resp:
                        total_items_in_json += 1
                    # Cek struktur Conflict/Duplicate
                    elif resp.get('message') == 'Conflict' or 'duplicate' in str(resp).lower():
                        total_items_in_json += 1
                    # Cek struktur lama (results plural)
                    else:
                        res_data = resp.get('data', {}).get('results', []) or resp.get('results', [])
                        if not res_data and isinstance(resp.get('data'), list): res_data = resp.get('data')
                        
                        if isinstance(res_data, list):
                            total_items_in_json += len(res_data)
                        elif res_data: # Singular object in results
                            total_items_in_json += 1
            
            # self.log(f"DEBUG: JSON Count = {total_items_in_json} / {len(self.current_batch_files)}")
            if total_items_in_json >= len(self.current_batch_files):
                self.batch_finished = True
                return True

        # 1. CEK MODAL/TEXT SUKSES (FAST TRACK)
        # Sederhanakan: Jika ada teks Selesai/Berhasil, langsung kunci sukses.
        success_data = page.evaluate(f"""() => {{
            const text = document.body.innerText;
            
            // Cari indikator sukses yang paling umum di FotoYu
            const isSuccess = /Selesai!|Semua konten telah berhasil diunggah|Berhasil diunggah|Success|Unggahan Berhasil/i.test(text);
            const isPartial = /Diunggah.*Tetapi|terdeteksi.*duplikat|gagal diunggah|1 konten terdeteksi/i.test(text);
            
            return {{
                success: isSuccess,
                partial: isPartial
            }};
        }}""")

        if success_data['success']:
            # TANDA VISUAL SUKSES MUTLAK: Langsung kunci sukses
            self.visual_success_detected = True
            self.batch_finished = True
            self.log(f"✔ Berhasil (Konfirmasi Visual)")
            return True

        if success_data['partial']:
            # TANDA PARSIAL/GAGAL: Website menampilkan modal "Diunggah! Tetapi..."
            # Kita anggap batch ini selesai diproses oleh website.
            # Sistem akan menggunakan data JSON API untuk menentukan mana yang sukses/gagal.
            self.batch_finished = True
            self.log(f"⚠ Selesai dengan catatan (Konfirmasi Visual)")
            return True

        # 2. CEK FORM HILANG (Hanya jika sedang di domain yang benar & online)
        try:
            # Cek URL & Online Status dalam satu kali evaluate
            browser_state = page.evaluate("""() => {
                return {
                    url: window.location.href,
                    online: navigator.onLine,
                    priceVisible: !!document.querySelector('input[placeholder*="Harga"]'),
                    previewVisible: !!document.querySelector('img[src^="blob:"], video[src^="blob:"]'),
                    submitVisible: document.body.innerText.includes('Unggah'),
                    uploading: document.body.innerText.includes('Mengunggah') || !!document.querySelector('.progress-bar, .upload-indicator'),
                    compressing: document.body.innerText.includes('Mengompres')
                };
            }""")

            if "fotoyu.com" not in browser_state['url'] or "chrome-error" in browser_state['url']:
                return False
            
            # HYBRID LOGIC: Jika sudah di halaman profile dan form upload hilang, 
            # itu pertanda kuat upload sukses & redirect otomatis oleh website.
            if "/profile/" in browser_state['url'].lower() and \
               not browser_state['priceVisible'] and \
               not browser_state['previewVisible'] and \
               not browser_state['submitVisible']:
                self.redirect_success_detected = True
                self.batch_finished = True
                self.log(f"✔ Berhasil (Redirect ke Profil)")
                return True

            if not browser_state['online']:
                return False

            # Jika semua indikator form & proses hilang, berarti sukses
            if not browser_state['priceVisible'] and \
               not browser_state['previewVisible'] and \
               not browser_state['submitVisible'] and \
               not browser_state['uploading'] and \
               not browser_state['compressing']:
                self.visual_success_detected = True # SET FLAG SUKSES DI SINI JUGA
                self.batch_finished = True
                self.active_count = 0
                self.log(f"✔ Berhasil (Form Selesai)")
                return True
        except:
            pass

        return False

    def _check_and_close_modals(self):
        """Mendeteksi dan menutup modal yang mungkin menghalangi proses"""
        try:
            # Cari tombol OK/Tutup/Simpan yang mungkin muncul sebagai overlay
            # Gunakan evaluate untuk efisiensi
            self.page.evaluate("""() => {
                const selectors = [
                    "div[data-testid='button']",
                    "button",
                    "div[role='button']"
                ];
                const texts = ['OK', 'Tutup', 'Close', 'Tingkatkan', 'Nanti Saja', 'Selesai', 'Ulangi'];
                
                for (const sel of selectors) {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        const txt = el.innerText.trim();
                        if (texts.some(t => txt.includes(t)) && el.offsetWidth > 0 && el.offsetHeight > 0) {
                            // Cek apakah ini modal yang menghalangi (z-index tinggi atau overlay)
                            // Untuk amannya, kita hanya klik jika teksnya sangat spesifik untuk modal pengganggu
                            if (txt.includes('Tingkatkan') || txt.includes('Nanti Saja') || 
                                (txt === 'OK' && document.body.innerText.includes('Kreator')) ||
                                (txt === 'Ulangi' && (document.body.innerText.includes('Diunggah! Tetapi') || document.body.innerText.includes('gagal diunggah')))) {
                                ['mousedown', 'mouseup', 'click'].forEach(evt => {
                                    el.dispatchEvent(new MouseEvent(evt, {bubbles: true, cancelable: true, view: window}));
                                });
                                console.log('AutoYu: Closed modal with text: ' + txt);
                            }
                        }
                    }
                }
            }""")
        except:
            pass

    def run_step(self):
        """Executes one step of the FSM. Returns True if should continue, False if finished."""
        if not self.is_running:
            return False

        # DETEKSI DINI: Jika page sudah tertutup atau browser terputus, langsung stop
        try:
            if not self.page or self.page.is_closed():
                self.is_running = False
                return False
            
            # Tambahan cek koneksi browser untuk persistent context
            if not self.page.context or not self.page.context.pages:
                self.is_running = False
                return False
        except:
            self.is_running = False
            return False

        # Tutup modal pengganggu di setiap langkah
        self._check_and_close_modals()

        # HARD LICENSE CHECK - RUNTIME LOOP
        # Checks every 10 seconds to save CPU
        now = time.time()
        if not hasattr(self, '_last_license_check') or now - self._last_license_check > 10:
            app_type = "lite" if self.is_lite else "pro"
            is_valid, status, _, _ = check_license(app_type=app_type)
            self._last_license_check = now
            
            if is_valid:
                # Reset counter jika koneksi kembali normal
                if self._conn_fail_count > 0:
                    self.log("✅ Koneksi internet kembali normal.")
                self._conn_fail_count = 0
            else:
                # Toleransi jika hanya masalah koneksi
                if "CONNECTION_FAILED" in status or "SERVER_CONNECTION_ERROR" in status:
                    self._conn_fail_count += 1
                    
                    # 60 kali (x 10 detik = ~10 menit toleransi)
                    max_retry = 60 
                    remaining = max_retry - self._conn_fail_count
                    
                    if remaining > 0:
                        # Log setiap 1 menit sekali biar tidak spam (6 x 10 detik)
                        if self._conn_fail_count == 1 or self._conn_fail_count % 6 == 0:
                            self.log(f"⚠️ Koneksi internet terganggu. Mencoba verifikasi ulang ({remaining * 10} detik lagi)...")
                        # Jangan return False, biarkan loop tetap berjalan (mode offline sementara)
                    else:
                        self.log(f"❌ Koneksi internet gagal setelah {max_retry} kali percobaan. Menghentikan engine demi keamanan.")
                        self.is_running = False
                        return False
                else:
                    # Jika status EXPIRED, DISABLED, atau lainnya yang eksplisit (Bukan Masalah Koneksi)
                    self.log(f"Lisensi tidak aktif: {status}")
                    self.is_running = False
                    return False

        try:
            elapsed = time.time() - self.state_start_time if self.state_start_time else 0

            #region debug-point tab-next-compress-state
            try:
                last_state = getattr(self, "_trae_dbg_last_state", None)
                if last_state != self.state:
                    self._trae_dbg_last_state = self.state
                    _trae_dbg(
                        "state_change",
                        runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                        tabId=self.tab_id,
                        state=str(self.state),
                        url=getattr(self.page, "url", None),
                        injector=self.global_lock.get("injector") if isinstance(self.global_lock, dict) else None,
                    )
            except Exception:
                pass
            #endregion debug-point tab-next-compress-state

            # -------------------------------------------------
            # INIT / START
            # -------------------------------------------------
            if self.state == AutoState.INIT:
                self.log(f"✔ Mulai memproses")
                self.state = AutoState.OPEN_UPLOAD_PAGE
                self.state_start_time = time.time()

            # -------------------------------------------------
            # OPEN_UPLOAD_PAGE (Logic from START state in batch_uploader)
            # -------------------------------------------------
            elif self.state == AutoState.OPEN_UPLOAD_PAGE:
                # 1. Check for more files
                start = self.file_index
                
                current_batch_size = self.batch_size
                end = min(start + current_batch_size, len(self.all_files))
                
                if start >= len(self.all_files):
                    self.state = AutoState.DONE
                    self._flush_tracker()
                    return False # Stop running
                
                self.current_batch_files = self.all_files[start:end]
                self.active_count = 0 # Start at 0, will increase as previews appear
                self.submit_retries = 0
                self.batch_finished = False
                self.compression_done = False # Reset compression status for new batch
                self.injection_done = False
                self.visual_success_detected = False # Reset for new batch
                self.redirect_success_detected = False # Reset for new batch
                self._mark_batch(self.current_batch_files, 'pending')
                
                # 2. Navigation
                if "/upload" not in self.page.url:
                    try:
                        now_nav = time.time()
                        last_try = getattr(self, "_nav_last_try_at", 0.0)
                        if now_nav - last_try >= 1.0:
                            self._nav_last_try_at = now_nav
                            self.page.goto(SELECTORS["url_upload"], wait_until="domcontentloaded", timeout=2500)
                    except Exception:
                        pass
                    return True
                
                if "/upload" in self.page.url:
                    # Check for upgrade modal ("Tingkatkan ke Kreator")
                    try:
                        ok_btn = self.page.locator(SELECTORS["modal_ok"]).last
                        if ok_btn.is_visible():
                            self.log(f"Menutup pemberitahuan...")
                            ok_btn.click(force=True)
                            self.page.wait_for_timeout(500)
                    except:
                        pass
                        
                    self.log(f"Memproses {len(self.current_batch_files)} file...")
                    # Antri sebelum melakukan proses injeksi file (SELECT_MODE)
                    self.state = AutoState.WAIT_QUEUE 
                    self.state_start_time = time.time()
                elif elapsed > 60:
                    self.log(f"Halaman tidak merespon")
                    self._mark_batch(self.current_batch_files, 'failed')
                    self.log(f"⚠️ {len(self.current_batch_files)} file gagal.")
                    self.failed_count += len(self.current_batch_files)
                    self.active_count = 0
                    self.file_index += len(self.current_batch_files)
                    self.state = AutoState.OPEN_UPLOAD_PAGE # Retry next batch
                    self.state_start_time = time.time()

            # -------------------------------------------------
            # WAIT_QUEUE (Antrian Injeksi File)
            # -------------------------------------------------
            elif self.state == AutoState.WAIT_QUEUE:
                # Jika tidak ada file tersisa untuk diproses, hentikan tab agar tidak terlihat "menunggu"
                if self.file_index >= len(self.all_files) or not self.current_batch_files:
                    if self.global_lock.get('injector') == self.tab_id:
                        self.global_lock['injector'] = None
                    self.is_running = False
                    self.state = AutoState.DONE
                    return False
                # Cek apakah injector sedang kosong atau sedang dipegang tab ini
                injector = self.global_lock.get('injector')
                if injector is None or injector == self.tab_id:
                    #region debug-point tab-next-compress-injector-acquire
                    try:
                        _trae_dbg(
                            "injector_acquire",
                            runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                            tabId=self.tab_id,
                            injectorBefore=injector,
                            elapsed=elapsed,
                        )
                    except Exception:
                        pass
                    #endregion debug-point tab-next-compress-injector-acquire
                    self.global_lock['injector'] = self.tab_id
                    self.state = AutoState.SELECT_MODE
                    self.state_start_time = time.time()
                else:
                    #region debug-point tab-next-compress-injector-wait
                    try:
                        now_dbg = time.time()
                        last_dbg = getattr(self, "_trae_dbg_last_wait_emit", 0.0)
                        if now_dbg - last_dbg >= 1.0:
                            self._trae_dbg_last_wait_emit = now_dbg
                            _trae_dbg(
                                "injector_wait",
                                runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                                tabId=self.tab_id,
                                injectorHeldBy=injector,
                                elapsed=elapsed,
                            )
                    except Exception:
                        pass
                    #endregion debug-point tab-next-compress-injector-wait
                    if int(elapsed) % 30 == 0:
                         self.log(f"⏳ Menunggu antrian...")
                    
                    if elapsed > 600: # Timeout antrian 10 menit
                         self.global_lock['injector'] = None # Force reset
                         self.state = AutoState.OPEN_UPLOAD_PAGE

            # -------------------------------------------------
            # SELECT_MODE (Maps to UPLOAD state - Inject Files)
            # -------------------------------------------------
            elif self.state == AutoState.SELECT_MODE:
                trigger = None
                is_input = False
                
                if self.upload_type == "video":
                    # PRIORITAS: Klik tab video dulu
                    try:
                        # Cari elemen tab video yang bisa diklik
                        video_tab = self.page.locator("text='Pratinjau Video'").first
                        if video_tab.is_visible(timeout=5000):
                            # self.log(f"Menyiapkan video...")
                            # Gunakan expect_file_chooser karena pada beberapa kondisi, 
                            # klik tab ini memicu dialog file sistem yang mengganggu otomasi.
                            try:
                                with self.page.expect_file_chooser(timeout=2000) as fc_info:
                                    video_tab.click(force=True)
                                
                                # Jika dialog terbuka, tangani dengan Playwright agar tidak muncul di Windows
                                file_chooser = fc_info.value
                                # self.log(f"Memproses file...")
                                file_chooser.set_files(self.current_batch_files)
                                #region debug-point tab-next-compress-video-inject
                                try:
                                    _trae_dbg(
                                        "files_injected",
                                        runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                                        tabId=self.tab_id,
                                        branch="video-tab-file-chooser",
                                        fileCount=len(self.current_batch_files or []),
                                        injector=self.global_lock.get("injector") if isinstance(self.global_lock, dict) else None,
                                    )
                                except Exception:
                                    pass
                                #endregion debug-point tab-next-compress-video-inject
                                
                                # Jika kita sudah set_files di sini, kita bisa langsung ke state berikutnya
                                # self.log(f"File siap. Memproses...")
                                self.injection_done = True
                                self.state = AutoState.WAIT_PREVIEW
                                self.state_start_time = time.time()
                                return True # Keluar dari SELECT_MODE step ini dan lanjut running
                            except Exception:
                                # Jika timeout (tidak ada dialog), berarti hanya switch tab biasa. Lanjut ke pencarian input.
                                self.page.wait_for_timeout(500)
                        else:
                            # Fallback ke selector di SELECTORS
                            video_tab_alt = self.page.locator(SELECTORS["trigger_video"]).first
                            if video_tab_alt.is_visible():
                                # self.log(f"Mencoba kembali...")
                                try:
                                    with self.page.expect_file_chooser(timeout=1000) as fc_info:
                                        video_tab_alt.click(force=True)
                                    file_chooser = fc_info.value
                                    file_chooser.set_files(self.current_batch_files)
                                    self.injection_done = True
                                    self.state = AutoState.WAIT_PREVIEW
                                    self.state_start_time = time.time()
                                    return True
                                except:
                                    self.page.wait_for_timeout(500)
                    except Exception as e:
                        pass

                    # Cari input file yang benar-benar untuk video
                    try:
                        all_file_inputs = self.page.locator("input[type='file']")
                        count = all_file_inputs.count()
                        
                        best_score = -999
                        best_input = None
                        
                        for i in range(count):
                            inp = all_file_inputs.nth(i)
                            p_text = inp.evaluate("el => el.parentElement.innerText")
                            accept = (inp.get_attribute("accept") or "").lower()
                            
                            score = 0
                            if "video" in accept: score += 10
                            if "image" in accept and "video" not in accept: score -= 20
                            if "Pratinjau Video" in p_text: score += 5
                            if "Maks. 50" in p_text: score += 5
                            
                            if score > best_score:
                                best_score = score
                                best_input = inp
                        
                        if best_input and best_score > -10:
                            # self.log(f"Menyiapkan data...")
                            trigger = best_input
                            is_input = True
                        
                        if not trigger:
                            # Jika masih belum ketemu, coba cari input yang tadi kita temukan SEBELUM klik
                            # self.log(f"Mencoba kembali...")
                            # (Gunakan logika yang sama untuk input SEBELUM klik jika perlu, 
                            # tapi biasanya SETELAH klik lebih akurat jika scoring benar)
                            # Fallback sederhana ke pencarian teks jika scoring gagal
                            for i in range(count):
                                inp = all_file_inputs.nth(i)
                                p_text = inp.evaluate("el => el.parentElement.innerText")
                                if "Pratinjau Video" in p_text:
                                    trigger = inp
                                    is_input = True
                                    break
                    except Exception as e:
                        pass
                
                if not trigger:
                    trigger = self.page.locator(SELECTORS["trigger_foto"]).first
                
                # Hanya fallback ke container jika kita BELUM menemukan input file langsung
                if not is_input:
                    if not trigger or not trigger.is_visible():
                        trigger = self.page.locator(SELECTORS["trigger_container"]).first
                
                if trigger:
                    # Ganti teks log agar sesuai dengan tipe upload (foto/video)
                    label_tipe = "video" if self.upload_type == "video" else "foto"
                    self.log(f"Memulai pengunggahan...")
                    try:
                        # Jika belum diketahui is_input, coba deteksi
                        if not is_input:
                            try:
                                tag_name = trigger.evaluate("el => el.tagName.toLowerCase()")
                                is_input = (tag_name == "input")
                            except:
                                pass
                        if is_input:
                            # self.log(f"Mengirim file...")
                            # Verifikasi file sebelum upload
                            valid_files = [f for f in self.current_batch_files if os.path.exists(f)]
                            
                            if not valid_files:
                                self.log(f"❌ {len(self.current_batch_files)} file tidak ditemukan di folder.")
                                self._mark_batch(self.current_batch_files, 'failed')
                                self.failed_count += len(self.current_batch_files)
                                self.file_index += len(self.current_batch_files)
                                self.current_batch_files = []
                                self.state = AutoState.OPEN_UPLOAD_PAGE
                                return True
                            
                            # Jika hanya sebagian yang ada, tandai yang hilang sebagai gagal
                            if len(valid_files) < len(self.current_batch_files):
                                missing_count = len(self.current_batch_files) - len(valid_files)
                                self.log(f"⚠️ {missing_count} file tidak ditemukan, melanjutkan sisanya...")
                                # Cari file mana yang hilang dan tandai gagal
                                for f in self.current_batch_files:
                                    if f not in valid_files:
                                        self._mark_file(f, 'failed')
                                        self.failed_count += 1
                                
                            self.current_batch_files = valid_files
                            trigger.set_input_files(valid_files)
                            self.injection_done = True
                            #region debug-point tab-next-compress-inject-input
                            try:
                                _trae_dbg(
                                    "files_injected",
                                    runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                                    tabId=self.tab_id,
                                    branch="input-set-files",
                                    fileCount=len(valid_files or []),
                                    injector=self.global_lock.get("injector") if isinstance(self.global_lock, dict) else None,
                                )
                            except Exception:
                                pass
                            #endregion debug-point tab-next-compress-inject-input
                        else:
                            # Gunakan expect_file_chooser untuk menangani dialog upload file
                            with self.page.expect_file_chooser(timeout=10000) as fc_info:
                                trigger.click(force=True)
                            
                            file_chooser = fc_info.value
                            valid_files = [f for f in self.current_batch_files if os.path.exists(f)]
                            if not valid_files:
                                self.log(f"❌ {len(self.current_batch_files)} file tidak ditemukan di folder.")
                                self._mark_batch(self.current_batch_files, 'failed')
                                self.failed_count += len(self.current_batch_files)
                                self.file_index += len(self.current_batch_files)
                                self.current_batch_files = []
                                self.state = AutoState.OPEN_UPLOAD_PAGE
                                return True

                            if len(valid_files) < len(self.current_batch_files):
                                missing_count = len(self.current_batch_files) - len(valid_files)
                                self.log(f"⚠️ {missing_count} file tidak ditemukan, melanjutkan sisanya...")
                                for f in self.current_batch_files:
                                    if f not in valid_files:
                                        self._mark_file(f, 'failed')
                                        self.failed_count += 1
                                self.current_batch_files = valid_files
                            file_chooser.set_files(valid_files)
                            self.injection_done = True
                            #region debug-point tab-next-compress-inject-chooser
                            try:
                                _trae_dbg(
                                    "files_injected",
                                    runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                                    tabId=self.tab_id,
                                    branch="file-chooser-set-files",
                                    fileCount=len(valid_files or []),
                                    injector=self.global_lock.get("injector") if isinstance(self.global_lock, dict) else None,
                                )
                            except Exception:
                                pass
                            #endregion debug-point tab-next-compress-inject-chooser
                        
                        # self.log(f"Terkirim, sedang diproses...")
                        #region debug-point tab-next-compress-injector-release
                        try:
                            _trae_dbg(
                                "injector_after_select_mode",
                                runId=os.environ.get("TRAE_DBG_RUN_ID") or "pre",
                                tabId=self.tab_id,
                                injector=self.global_lock.get("injector") if isinstance(self.global_lock, dict) else None,
                            )
                        except Exception:
                            pass
                        #endregion debug-point tab-next-compress-injector-release
                        self.state = AutoState.WAIT_PREVIEW
                        self.state_start_time = time.time()
                    except Exception as ex:
                        self.log(f"❌ Gagal memproses ({type(ex).__name__}).")
                elif elapsed > 30:
                    self.log(f"Gagal memproses file")
                    self.log(f"⚠️ {len(self.current_batch_files)} file gagal.")
                    self.failed_count += len(self.current_batch_files)
                    self.active_count = 0
                    self.file_index += len(self.current_batch_files)
                    self.state = AutoState.OPEN_UPLOAD_PAGE
                    self.state_start_time = time.time()

            # -------------------------------------------------
            # WAIT_PREVIEW
            # -------------------------------------------------
            elif self.state == AutoState.WAIT_PREVIEW:
                # Menunggu pratinjau muncul dan kompresi selesai
                url = self.page.url
                video_count = 0
                foto_count = 0
                compressing_count = 0
                try:
                    video_count = self.page.locator(SELECTORS["video_preview_ready"]).count()
                    foto_count = self.page.locator(SELECTORS["preview_ready"]).count()
                    compressing_count = self.page.locator(SELECTORS["compressing"]).count()
                except:
                    pass
                
                # Cek apakah masih ada kompresi yang berlangsung
                still_compressing = compressing_count > 0
                
                # Check for "Selanjutnya" button, price input, or edit url
                next_btn_visible = False
                price_input_visible = False
                edit_url = "edit" in url or "send-to-face" in url
                
                try:
                    next_btn = self.page.locator(SELECTORS["btn_next"]).first
                    next_btn_visible = next_btn.is_visible(timeout=500)
                except:
                    pass

                try:
                    price_input = self.page.locator(SELECTORS["price_input"]).first
                    price_input_visible = price_input.count() > 0 and price_input.is_visible(timeout=500)
                except:
                    pass
                
                # Tentukan apakah bisa lanjut:
                # - Tidak ada lagi teks "Mengompres"
                # - DAN (ada preview, atau next button, atau price input, atau di halaman edit, atau timeout)
                can_proceed = False
                if not still_compressing:
                    if (video_count > 0 or foto_count > 0) or next_btn_visible or price_input_visible or edit_url or elapsed > 120:
                        can_proceed = True
                
                if can_proceed:
                    if video_count > 0 or foto_count > 0:
                        self.log(f"✔ Konten siap.")
                    if self.global_lock.get('injector') == self.tab_id:
                        self.global_lock['injector'] = None
                    self.compression_done = True
                    self.first_compression_done = True  # First compression is done, never reset this!
                    if price_input_visible or edit_url:
                        self.state = AutoState.FILL_METADATA
                    else:
                        self.state = AutoState.WAIT_METADATA_CONTAINER
                    self.state_start_time = time.time()
                
                # Check for upgrade modal that might block preview
                try:
                    ok_btn = self.page.locator(SELECTORS["modal_ok"]).last
                    if ok_btn.count() > 0 and ok_btn.is_visible(timeout=500):
                        ok_btn.click(force=True)
                except:
                    pass

                try:
                    self.active_count = min(video_count if self.upload_type == "video" else foto_count, len(self.current_batch_files))
                except:
                    pass

            # -------------------------------------------------
            # WAIT_METADATA_CONTAINER
            # -------------------------------------------------
            elif self.state == AutoState.WAIT_METADATA_CONTAINER:
                # Keep active_count updated
                try:
                    if self.upload_type == "video":
                        preview_count = self.page.locator(SELECTORS["video_preview_ready"]).count()
                    else:
                        preview_count = self.page.locator(SELECTORS["preview_ready"]).count()
                    self.active_count = min(preview_count, len(self.current_batch_files))
                except:
                    pass

                # SPEED OPTIMIZED: Use wait_for for faster detection
                try:
                    price_input = self.page.locator(SELECTORS["price_input"]).first
                    price_input.wait_for(state="visible", timeout=3000) # Fast wait 3 detik
                    self.state = AutoState.FILL_METADATA
                    self.state_start_time = time.time()
                except:
                    if elapsed > 10: # Timeout lebih cepat: 10 detik
                        self.log(f"Gagal menyiapkan data")
                        self.log(f"⚠️ {len(self.current_batch_files)} file gagal.")
                        self.failed_count += len(self.current_batch_files)
                        self.active_count = 0
                        self.file_index += len(self.current_batch_files)
                        self.state = AutoState.OPEN_UPLOAD_PAGE
                        self.state_start_time = time.time()

            # -------------------------------------------------
            # FILL_METADATA
            # -------------------------------------------------
            elif self.state == AutoState.FILL_METADATA:
                # Keep active_count updated
                self.active_count = len(self.current_batch_files)
                
                # SPEED OPTIMIZED - SAFE MODE
                try:
                    # Target: Metadata fill < 0.5 detik
                    price_loc = self.page.locator(SELECTORS["price_input"]).first
                    desc_loc = self.page.locator(SELECTORS["desc_input"]).first
                    
                    # Ensure visibility
                    price_loc.wait_for(state="visible", timeout=2000)
                    
                    # Mode Delay
                    delay = self.mode_config.get("delay_meta", 0.1) # Dipercepat dari 0.3
                    if self.mode == UploadMode.TURBO:
                        delay = 0 # No delay for Turbo
                    
                    if delay > 0:
                        time.sleep(delay)
                    
                    # Fill metadata
                    price_loc.fill(self.price, timeout=2000)
                    desc_loc.fill(self.desc, timeout=2000)
                    
                    # TURBO MODE: Langsung klik Unggah di sini juga untuk memangkas siklus loop
                    if self.mode == UploadMode.TURBO:
                        try:
                            submit_btn = self.page.locator(SELECTORS["submit_button"]).first
                            if submit_btn.is_visible():
                                self.log(f"🚀 Mengunggah instan...")
                                submit_btn.click(no_wait_after=True)
                                self.state = AutoState.CONFIRM_SUCCESS
                                self.state_start_time = time.time()
                                return True
                        except:
                            pass
                        self.state = AutoState.SUBMIT
                    else:
                        self.state = AutoState.VERIFY_FILLED
                    
                    self.state_start_time = time.time()
                except Exception as e:
                    if elapsed > 15:
                        self.log(f"Gagal menyimpan data")
                        self.log(f"⚠️ {len(self.current_batch_files)} file gagal.")
                        self.failed_count += len(self.current_batch_files)
                        self.active_count = 0
                        self.file_index += len(self.current_batch_files)
                        self.state = AutoState.OPEN_UPLOAD_PAGE
                        self.state_start_time = time.time()

            # -------------------------------------------------
            # VERIFY_FILLED
            # -------------------------------------------------
            elif self.state == AutoState.VERIFY_FILLED:
                # SPEED OPTIMIZED - SAFE MODE
                try:
                    # Quick 1-time verification
                    price_val = self.page.locator(SELECTORS["price_input"]).first.input_value(timeout=1000)
                    desc_val = self.page.locator(SELECTORS["desc_input"]).first.input_value(timeout=1000)
                    
                    if price_val == self.price and self.desc in desc_val:
                        self.state = AutoState.FILL_LOCATION
                        self.state_start_time = time.time()
                        self.retries = 0
                    else:
                        if elapsed > 2:
                            self.state = AutoState.FILL_METADATA
                            self.state_start_time = time.time()
                except:
                    self.state = AutoState.FILL_METADATA
                    self.state_start_time = time.time()

            # -------------------------------------------------
            # FILL_LOCATION (New)
            # -------------------------------------------------
            elif self.state == AutoState.FILL_LOCATION:
                requested_tree = self._normalize_text_value(self._resolved_tree or self.fototree_keyword or self.fototree or "")
                requested_location = self._normalize_text_value(self._resolved_location or self.location_keyword or self.location or "")

                # USER FIX: Clear existing location/tree before filling (Isi salah satu)
                # PENTING: Jika data berasal dari Setup, pastikan kita benar-benar mengosongkan dropdown lama
                if requested_tree or requested_location:
                    self._clear_shared_tree_location_value()
                    self.page.wait_for_timeout(1000)
                    try:
                        ok_btn = self.page.locator(SELECTORS["modal_ok"]).last
                        if ok_btn.is_visible(timeout=300):
                            ok_btn.click(force=True)
                            self.page.wait_for_timeout(300)
                    except Exception:
                        pass

                if requested_tree:
                    try:
                        tree_input = self.page.locator(SELECTORS["tree_search"]).first
                        if tree_input.count() > 0:
                            # Tunggu sampai input enabled (bisa diisi)
                            try:
                                # Jika masih disabled, coba hapus lagi secara agresif
                                is_disabled = tree_input.evaluate("el => el.disabled || el.readOnly || el.classList.contains('disabled')")
                                if is_disabled:
                                    self.log("⚠️ Input FotoTree terkunci, mencoba membuka paksa...")
                                    self._clear_shared_tree_location_value()
                                    self.page.wait_for_timeout(1500)
                                    
                                    # Fallback Terakhir: Paksa aktifkan via JS jika benar-benar macet
                                    if tree_input.evaluate("el => el.disabled || el.readOnly"):
                                        tree_input.evaluate("el => { el.disabled = false; el.readOnly = false; el.classList.remove('disabled'); }")
                                        self.page.wait_for_timeout(500)
                            except: pass

                            tree_input.wait_for(state="visible", timeout=5000)

                            current_tree = ""
                            try:
                                current_tree = tree_input.input_value() or tree_input.text_content() or ""
                            except Exception:
                                pass

                            if self._normalize_search_text(current_tree) != self._normalize_search_text(requested_tree):
                                clicked_tree = False
                                
                                # FIX: Gunakan keyword bersih untuk pencarian agar memicu dropdown
                                base_keyword = self._extract_primary_option_text(requested_tree)
                                is_setup_data = bool(self.config.get("setup_metadata_active"))
                                
                                # Loop percobaan untuk FotoTree (Hanya jika bukan data Setup)
                                max_attempts = 1 if is_setup_data else 3
                                
                                for tree_attempt in range(max_attempts):
                                    search_keyword = base_keyword
                                    if not is_setup_data:
                                        if tree_attempt == 1:
                                            words = base_keyword.split()
                                            if len(words) > 3: search_keyword = " ".join(words[:3])
                                        elif tree_attempt == 2:
                                            words = base_keyword.split()
                                            if len(words) > 2: search_keyword = " ".join(words[:2])

                                    # USER FIX: Sederhanakan log pengisian
                                    self.log(f"🌳 Mengisi FotoTree: {search_keyword}")
                                    
                                    # Metode Injeksi Langsung untuk kecepatan
                                    try:
                                        self.page.evaluate(f"""(val) => {{
                                            const input = document.querySelector('input[placeholder*="FotoTree"], input[class*="tree"]');
                                            if (input) {{
                                                input.value = val;
                                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            }}
                                        }}""", search_keyword)
                                    except: pass

                                    self._fill_location_search_input(tree_input, search_keyword, wait_ms=2000)
                                    
                                    # Tunggu sebentar agar dropdown muncul
                                    try:
                                        self.page.wait_for_selector("[role='option'], div[class*='option'], li[class*='item']", timeout=2000)
                                    except:
                                        pass

                                    selected_tree = requested_tree
                                    if not is_setup_data:
                                        selected_tree = self._resolve_realtime_choice(requested_tree, kind="fototree") or requested_tree
                                    
                                    if not is_setup_data and selected_tree and requested_tree:
                                        req_tokens = set(self._normalize_search_text(requested_tree).split())
                                        sel_tokens = set(self._normalize_search_text(selected_tree).split())
                                        overlap = len(req_tokens.intersection(sel_tokens))
                                        if overlap < 1 and len(req_tokens) > 0:
                                            selected_tree = requested_tree
                                    
                                    tree_selectors = [
                                        self.page.get_by_text(selected_tree, exact=True),
                                        self.page.locator(f"[role='option']").filter(has_text=selected_tree),
                                        self.page.locator(f"div").filter(has_text=selected_tree)
                                    ]
                                    
                                    for locator in tree_selectors:
                                        try:
                                            if locator.count() > 0:
                                                for i in range(locator.count()):
                                                    node = locator.nth(i)
                                                    if node.is_visible(timeout=500):
                                                        node_text = (node.text_content() or "").strip()
                                                        if self._normalize_search_text(node_text) == self._normalize_search_text(selected_tree):
                                                            node.click(force=True)
                                                            clicked_tree = True
                                                            break
                                                if clicked_tree: break
                                        except Exception:
                                            continue
                                    
                                    if clicked_tree: 
                                        self.log(f"🌳 Berhasil memilih FotoTree: {selected_tree}")
                                        break
                                    
                                    if not is_setup_data:
                                        try:
                                            first_opt = self.page.locator("[role='option'], div[class*='option']").first
                                            if first_opt.is_visible(timeout=500):
                                                opt_txt = (first_opt.text_content() or "").strip()
                                                if opt_txt and "pilih" not in opt_txt.lower():
                                                    first_opt.click(force=True)
                                                    clicked_tree = True
                                                    self.log(f"🌳 FotoTree dipilih: {opt_txt}")
                                                    break
                                        except: pass
                                    
                                    if not clicked_tree:
                                        self.page.wait_for_timeout(1000)

                                if not clicked_tree:
                                    # Fallback: Klik opsi pertama yang muncul di dropdown jika ada
                                    try:
                                        first_opt = self.page.locator("[role='option'], div[class*='option'], li[class*='item']").first
                                        if first_opt.is_visible(timeout=1000):
                                            self.log("🌳 Memilih opsi pertama yang tersedia di daftar...")
                                            first_opt.click(force=True)
                                            clicked_tree = True
                                    except:
                                        pass

                                if clicked_tree:
                                    self._notify_tree_update(selected_tree, "exact", "live")
                                    self.page.wait_for_timeout(800)
                                else:
                                    # USER FIX: Cek apakah sebenarnya sudah terisi meski klik gagal
                                    try:
                                        final_val = tree_input.input_value() or ""
                                        if self._normalize_search_text(final_val) == self._normalize_search_text(selected_tree):
                                            self.log(f"✅ FotoTree sudah aktif: {final_val}")
                                            clicked_tree = True
                                            self._notify_tree_update(selected_tree, "exact", "live")
                                    except: pass
                                    
                                    if not clicked_tree:
                                        self.log("ℹ️ Sedang mencocokkan FotoTree dengan daftar...")
                            else:
                                self._resolved_tree = requested_tree
                    except Exception as e:
                        self.log(f"⚠️ FotoTree realtime tidak bisa diisi: {str(e)}")

                if not requested_location:
                    self.log("ℹ️ Lewati lokasi upload (kosong)")
                    self.state = AutoState.SUBMIT
                    self.state_start_time = time.time()
                    return True

                try:
                    loc_trigger = self.page.locator(SELECTORS["loc_trigger"]).first
                    trigger_visible = False
                    try:
                        if loc_trigger.is_visible(timeout=2000):
                            trigger_visible = True
                    except:
                        pass
                    
                    if not trigger_visible:
                        if elapsed > 15:
                            self.log("❌ Gagal menemukan input lokasi (Timeout 15s). Membatalkan batch ini demi keamanan.")
                            self._mark_batch(self.current_batch_files, 'failed')
                            self.failed_count += len(self.current_batch_files)
                            self.active_count = 0
                            self.file_index += len(self.current_batch_files)
                            self.state = AutoState.OPEN_UPLOAD_PAGE
                            self.state_start_time = time.time()
                            return True
                        return True

                    current_val = ""
                    try:
                        current_val = loc_trigger.input_value() or loc_trigger.text_content() or ""
                    except:
                        pass
                    
                    # USER FIX: Jika lokasi sudah terisi koordinat (lat/lng), anggap sudah OK untuk menghindari loop
                    is_coords = "lat:" in current_val.lower() and "lng:" in current_val.lower()
                    if current_val.strip() and (is_coords or self._normalize_search_text(current_val) == self._normalize_search_text(requested_location)):
                        self.log(f"✅ Lokasi sudah terisi: {current_val.strip()}")
                        self.state = AutoState.SUBMIT
                        self.state_start_time = time.time()
                        return True

                    self.log(f"📍 Klik pilih lokasi realtime (Target: {requested_location})")
                    loc_trigger.click(force=True)
                    self.page.wait_for_timeout(1000)
                    
                    search_input = self.page.locator(SELECTORS["loc_search"]).first
                    try:
                        search_input.wait_for(state="visible", timeout=4000)
                    except:
                        if elapsed < 20:
                            self.log("🔄 Modal belum muncul, mencoba klik ulang...")
                            loc_trigger.click(force=True)
                            return True
                        self.log("⚠️ Modal lokasi tidak muncul. Lanjut submit.")
                        self.state = AutoState.SUBMIT
                        self.state_start_time = time.time()
                        return True
                    
                    if search_input.is_visible():
                        suggestion_found = False
                        is_setup_data = bool(self.config.get("setup_metadata_active"))
                        max_attempts = 1 if is_setup_data else 3

                        for search_attempt in range(max_attempts):
                            self.log(f"⌨️ Mencari Lokasi: {requested_location}")
                            self._fill_location_search_input(search_input, requested_location, wait_ms=2000)

                            target_location = requested_location
                            if not is_setup_data:
                                target_location = self._resolve_realtime_choice(requested_location, kind="location") or requested_location
                            
                            display_location = target_location

                            selectors_to_click = [
                                self.page.get_by_text(display_location, exact=True),
                                self.page.locator(f"div:has-text('{display_location}')"),
                                self.page.locator(f"[role='option']:has-text('{display_location}')")
                            ]
                            
                            for locator in selectors_to_click:
                                try:
                                    if locator.count() > 0:
                                        first_match = locator.first
                                        if first_match.is_visible(timeout=1000):
                                            txt = (first_match.text_content() or "").lower()
                                            if "simpan" in txt or "pilih" in txt: continue
                                            
                                            first_match.click(force=True)
                                            suggestion_found = True
                                            self.log(f"📍 Lokasi dipilih: {display_location}")
                                            break
                                except: continue
                                
                            if suggestion_found: break
                            
                            if not is_setup_data:
                                try:
                                    first_option = self.page.locator("[role='option'], div[class*='option'], div[class*='item']").first
                                    if first_option.is_visible(timeout=500):
                                        opt_text = (first_option.text_content() or "").strip()
                                        if opt_text and "pilih" not in opt_text.lower():
                                            first_option.click(force=True)
                                            suggestion_found = True
                                            self.log(f"📍 Lokasi otomatis: {opt_text}")
                                            break
                                except: pass
                            
                            if not suggestion_found:
                                self.page.wait_for_timeout(1000)

                        if not suggestion_found:
                            self.page.keyboard.press("Enter")
                            self.page.wait_for_timeout(1200)

                        # 4. Simpan
                        save_selectors = [
                            SELECTORS["loc_save"],
                            "button:has-text('Simpan Perubahan')",
                            "button:has-text('Simpan')",
                            "div[role='button']:has-text('Simpan')",
                            "button:has-text('Pilih Lokasi')",
                            "span:has-text('Simpan Perubahan')"
                        ]
                        saved = False
                        for s_sel in save_selectors:
                            try:
                                # Cari semua elemen yang cocok dan klik yang visible
                                btns = self.page.locator(s_sel)
                                for i in range(btns.count()):
                                    btn = btns.nth(i)
                                    if btn.is_visible(timeout=800):
                                        btn.click(force=True)
                                        self.log("💾 Lokasi telah diamankan.")
                                        saved = True
                                        break
                                if saved: break
                            except: continue
                        
                        if saved:
                            # Percepat: kurangi dari 1500ms ke 600ms
                            self.page.wait_for_timeout(600)
                            
                        # Verifikasi Akhir: Cek apakah modal masih terbuka
                        if search_input.is_visible(timeout=300) and elapsed < 40:
                            self.page.keyboard.press("Enter")
                            self.page.wait_for_timeout(600)

                        # Verifikasi singkat
                        self.page.wait_for_timeout(500)
                        final_val = ""
                        try: final_val = loc_trigger.input_value() or loc_trigger.text_content() or ""
                        except: pass
                        
                        is_final_coords = "lat:" in final_val.lower() and "lng:" in final_val.lower()
                        if not final_val.strip() and not is_final_coords and elapsed < 45:
                            self.log("⚠️ Lokasi belum terisi di field. Mencoba ulang...")
                            return True
                except Exception as e:
                    self.log(f"❌ Error FILL_LOCATION: {str(e)}")
                    if elapsed < 25: return True
                
                self.state = AutoState.SUBMIT
                self.state_start_time = time.time()

            # -------------------------------------------------
            # SUBMIT
            # -------------------------------------------------
            elif self.state == AutoState.SUBMIT:
                self.active_count = len(self.current_batch_files)
                # Anti-Infinite Loop: Jika batch sudah ditandai selesai, jangan submit lagi
                if self.batch_finished:
                    self.state = AutoState.CONFIRM_SUCCESS
                    self.state_start_time = time.time()
                    return True

                # Retry Protection
                if self.submit_retries >= 3:
                    self.batch_finished = True
                    self.state = AutoState.CONFIRM_SUCCESS
                    self.state_start_time = time.time()
                    return True

                try:
                    # 1. Proactive Modal/Toast Closing
                    # Sangat penting jika ada toast "Data FotoTree dihapus" yang menghalangi klik
                    try:
                        ok_btn = self.page.locator(SELECTORS["modal_ok"]).last
                        if ok_btn.is_visible(timeout=500):
                            ok_btn.click(force=True)
                            self.page.wait_for_timeout(500)
                            self.log("🧹 Membersihkan notifikasi/toast yang menghalangi...")
                    except: pass

                    # Mode Delay (Hanya pada percobaan pertama)
                    delay = self.mode_config.get("delay_submit", 0.5)
                    if self.mode == UploadMode.TURBO:
                        delay = 0 # Instant submit for Turbo
                    
                    if delay > 0 and self.submit_retries == 0:
                        time.sleep(delay)

                    # Prioritaskan selector yang lebih spesifik
                    submit_btn = self.page.locator(SELECTORS["submit_button"]).last
                    
                    if not submit_btn.is_visible():
                        # Fallback ke teks murni jika selector gagal
                        submit_btn = self.page.locator(f"text='{SELECTORS['submit_text']}'").last
                    
                    if submit_btn.is_visible():
                        # USER FIX: Deteksi tombol mati yang lebih canggih (Pointer Events & Opacity)
                        is_disabled = submit_btn.evaluate("""el => {
                            const style = window.getComputedStyle(el);
                            return el.disabled || 
                                   el.getAttribute('aria-disabled') === 'true' || 
                                   el.classList.contains('disabled') ||
                                   style.pointerEvents === 'none' ||
                                   parseFloat(style.opacity) < 0.6;
                        }""")

                        if is_disabled:
                            # Recovery 1: Cek field wajib yang mungkin kosong
                            try:
                                price_inp = self.page.locator(SELECTORS["price_input"]).first
                                if price_inp.count() > 0:
                                    cur_price = (price_inp.input_value() or "").strip()
                                    if not cur_price and str(self.price or "").strip():
                                        price_inp.fill(str(self.price))
                                        self.page.wait_for_timeout(250)
                            except: pass

                            # Recovery 2: Deep Reset (Jika macet > 6 detik sesuai instruksi memory)
                            if elapsed > 6:
                                self.log("⚠️ Tombol Unggah tetap mati. Melakukan Deep Reset metadata...")
                                self._clear_shared_tree_location_value()
                                self.page.wait_for_timeout(1000)
                                self.state = AutoState.FILL_LOCATION # Ulangi dari pengisian lokasi
                                self.state_start_time = time.time()
                                return True

                            if int(elapsed) % 2 == 0:
                                self.log("Menunggu proses website...")
                            return True

                        # Klik dengan Force agar menembus overlay transparan jika ada
                        self.log(f"Sedang mengunggah...")
                        submit_btn.click(timeout=3000, force=True)
                        self.last_submit_at = time.time()
                        self.submit_retries += 1
                        
                        self.state = AutoState.CONFIRM_SUCCESS
                        self.state_start_time = time.time()
                    elif elapsed > 5:
                         self.log(f"Tombol Unggah tidak ditemukan, memverifikasi hasil...")
                         self.state = AutoState.CONFIRM_SUCCESS 
                         self.state_start_time = time.time()
                except Exception as e:
                    if elapsed > 5:
                        self.log(f"⚠️ Kendala klik submit: {str(e)}. Verifikasi digital...")
                        self.state = AutoState.CONFIRM_SUCCESS
                        self.state_start_time = time.time()

            # -------------------------------------------------
            # CONFIRM_SUCCESS
            # -------------------------------------------------
            elif self.state == AutoState.CONFIRM_SUCCESS:
                if not self.batch_finished:
                    self.active_count = len(self.current_batch_files)
                # Anti-Infinite Loop: Jika sudah batch_finished atau confirm sukses, selesaikan batch
                if self.batch_finished or self.confirm_upload():
                    # Double check to prevent double counting
                    if self.current_batch_files:
                        batch_len = len(self.current_batch_files)
                        self.turbo_errors = 0
                        
                        success_files = []
                        failed_files = []

                        # Jika terdeteksi bukti visual sukses ATAU redirect ke profil, 
                        # maka batch dianggap sukses mutlak.
                        # TAPI: Jangan anggap sukses jika batch_finished dipicu oleh error/gangguan server.
                        is_visual_success = getattr(self, 'visual_success_detected', False) or getattr(self, 'redirect_success_detected', False)
                        is_error_stop = getattr(self, 'batch_failed_after_retry', False)

                        # AMBIL DATA DIGITAL (JSON) sebagai pembanding
                        responses_to_process = getattr(self, 'api_responses', [])
                        json_success_count = 0
                        if responses_to_process:
                            for resp in responses_to_process:
                                if not isinstance(resp, (dict, list)): continue
                                if isinstance(resp, list):
                                    json_success_count += len(resp)
                                else:
                                    msg = str(resp.get('message', '')).upper()
                                    # Tambahkan pengecekan string parsial untuk keandalan
                                    resp_str = str(resp).upper()
                                    is_dup = msg == 'CONFLICT' or 'DUPLICATE' in resp_str or 'ALREADY' in resp_str
                                    if (msg == 'OK' and ('result' in resp or 'data' in resp)) or is_dup:
                                        json_success_count += 1
                                        if is_dup: self.duplicate_count += 1

                        # LOGIKA PENENTUAN SUKSES (HYBRID)
                        # Jika website menampilkan modal "Diunggah! Tetapi..." (success_data['partial'] di confirm_upload),
                        # itu biasanya karena DUPLIKAT/CONFLICT. Kita harus menganggapnya SUKSES di tracker 
                        # agar tidak diulang-ulang (karena file sudah ada di server).
                        is_visual_partial = getattr(self, 'visual_success_detected', False) or getattr(self, 'batch_finished', False)
                        
                        if is_visual_success and not is_error_stop:
                            self.log(f"✔ Batch selesai secara visual & diverifikasi.")
                            success_files = self.current_batch_files
                            failed_files = []
                            self.auto_close_tab = True # Izinkan tutup tab otomatis
                        elif is_visual_partial and not is_error_stop:
                            # Jika visual menunjukkan selesai dengan catatan (modal duplikat muncul), 
                            # kita tandai sukses dan izinkan tutup tab agar tidak stuck.
                            self.log(f"✔ Selesai (Konten Baru / Duplikat terdeteksi).")
                            success_files = self.current_batch_files
                            failed_files = []
                            self.auto_close_tab = True # Izinkan tutup tab otomatis
                        else:
                            # Jika tidak ada bukti visual, gunakan data digital (JSON) secara ketat
                            if json_success_count >= len(self.current_batch_files):
                                success_files = self.current_batch_files
                                failed_files = []
                            else:
                                success_files = self.current_batch_files[:json_success_count]
                                failed_files = self.current_batch_files[json_success_count:]
                                
                                if is_error_stop and not success_files:
                                    failed_files = self.current_batch_files
                                    success_files = []

                        # Eksekusi Penandaan Tracker
                        if success_files:
                            self._mark_batch(success_files, 'success')
                            self.uploaded_count += len(success_files)

                        if failed_files:
                            self._mark_batch(failed_files, 'failed')
                            self.failed_count += len(failed_files)
                            for f in failed_files:
                                fname = os.path.basename(f)
                                self.log(f"⚠️ Gagal: {fname} (Cek internet/RAM)")
                            
                        # Update progress
                        self.active_count = 0
                        self.file_index += batch_len
                        
                        # Jika ada yang gagal murni (bukan timeout/network loss), 
                        # kita tetap biarkan tab terbuka jika batch_failed_after_retry aktif
                        if getattr(self, 'batch_failed_after_retry', False):
                            self.log(f"⚠️ Tab {self.tab_id}: Berhenti karena kendala pada {len(failed_files)} file.")
                            self.current_batch_files = []
                            self.is_running = False # STOP engine untuk tab ini
                            return False
                        
                        # Jika ini batch terakhir dan sukses, tutup page SEGERA
                        # TAPI: Jangan tutup jika ada kegagalan atau pernah ada gangguan server
                        is_last_batch = (self.file_index >= len(self.all_files))
                        if is_last_batch:
                            if not failed_files and not getattr(self, 'batch_failed_after_retry', False):
                                try:
                                    # Beri delay sebentar agar user bisa melihat status sukses terakhir
                                    self.log("ℹ Menunggu konfirmasi visual sebelum ringkasan akhir...")
                                    self.page.wait_for_timeout(3000)
                                    self.page.close()
                                    self.page_closed = True
                                except:
                                    pass
                            else:
                                self.log("ℹ Batch terakhir selesai dengan catatan. Browser tetap terbuka.")

                        self.current_batch_files = [] # Clear batch after processing
                        self.last_api_response = None # Reset untuk batch berikutnya
                        self.api_responses = [] # Reset daftar respon untuk batch berikutnya
                    
                    if self.file_index >= len(self.all_files):
                        self.state = AutoState.DONE
                        # Tutup page jika sudah selesai semua (Termasuk jika ada Duplikat/Partial Success)
                        # Kita gunakan flag auto_close_tab yang kita set di CONFIRM_SUCCESS
                        should_close = (self.failed_count == 0) or getattr(self, 'auto_close_tab', False)
                        
                        if should_close:
                            try:
                                # Beri delay sebelum penutupan akhir
                                self.log("ℹ Verifikasi akhir hasil unggah...")
                                self.page.wait_for_timeout(3000)
                                self.page.close()
                                self.page_closed = True
                                self.log(f"Tab {self.tab_id}: Ditutup otomatis (Selesai/Duplikat).")
                            except:
                                pass
                        else:
                            self.log("ℹ Proses selesai dengan beberapa kendala. Browser tetap terbuka.")
                        return False
                        
                    self.state = AutoState.OPEN_UPLOAD_PAGE
                    self.state_start_time = time.time()
                    return True
                
                # If not confirmed yet, check for timeout or errors
                # Reset timer if uploading indicator is visible
                if self.page.locator(SELECTORS["uploading"]).first.is_visible():
                    self.state_start_time = time.time()
                
                # Adaptive Timeout: 20 detik per foto (Min 45s, Max 120s)
                dynamic_timeout = min(120, max(45, len(self.current_batch_files) * 20))
                
                # USER FIX: Agresif Retry jika tombol Unggah masih muncul & aktif
                # Jika sudah 8 detik tapi form belum hilang/proses belum jalan, balik ke SUBMIT
                if elapsed > 8 and not self.page.locator(SELECTORS["uploading"]).first.is_visible():
                    try:
                        submit_btn = self.page.locator(SELECTORS["submit_button"]).last
                        if submit_btn.is_visible(timeout=500):
                            is_active = submit_btn.evaluate("el => !el.disabled && window.getComputedStyle(el).pointerEvents !== 'none'")
                            if is_active:
                                self.log("🔄 Proses tidak jalan, mencoba klik Unggah ulang...")
                                self.state = AutoState.SUBMIT
                                self.state_start_time = time.time()
                                return True
                    except: pass

                if elapsed > dynamic_timeout:
                    if self.submit_retries >= 3:
                        if self.current_batch_files:
                            batch_len = len(self.current_batch_files)
                            self.batch_finished = True
                            self.failed_count += batch_len # Tandai sebagai gagal, bukan upload sukses
                            self.active_count = 0
                            for f in self.current_batch_files:
                                self.log(f"⏱️ Timeout: {os.path.basename(f)} (PC/Internet lambat)")
                                
                            self.log(f"⚠️ Tab {self.tab_id}: Melebihi batas waktu. Browser tetap terbuka.")
                            self.log(f"ℹ File tetap di folder asal.")
                                
                            self.file_index += batch_len
                            self.current_batch_files = []
                            self.is_running = False # STOP engine untuk tab ini (HYBRID)
                            return False # Stop tab
                        self.state = AutoState.OPEN_UPLOAD_PAGE
                        self.state_start_time = time.time()
                    else:
                        # Retry click submit
                        self.state = AutoState.SUBMIT
                        self.state_start_time = time.time()
                
                # Check for explicit errors (Hanya jika belum batch_finished)
                error_text = self.page.locator(SELECTORS["error_text"]).first
                if error_text.is_visible():
                    err_content = (error_text.text_content() or "").strip()
                    if "Duplikat" in err_content or "sudah pernah" in err_content:
                        # Tandai sebagai selesai agar diproses oleh blok pemindah file utama di atas
                        self.batch_finished = True
                        self.duplicate_count += len(self.current_batch_files)
                        return True
                    else:
                        # Jika ini tepat setelah submit, beri grace period untuk verifikasi visual/redirect.
                        if self.last_submit_at and (time.time() - self.last_submit_at) < 12:
                            self.log(f"ℹ Tab {self.tab_id}: Menunggu konfirmasi pasca-submit...")
                            return True

                        # Coba klik 'Ulangi' maksimal 3x sebelum memutuskan gagal.
                        try:
                            retry_btn = self.page.locator(SELECTORS["modal_retry"]).first
                            if self.modal_retry_count < 3 and retry_btn.is_visible(timeout=1000):
                                # Pastikan button benar-benar bisa diklik (tidak terhalang)
                                retry_btn.scroll_into_view_if_needed()
                                retry_btn.click(force=True, timeout=2000)
                                self.modal_retry_count += 1
                                self.log(f"ℹ Tab {self.tab_id}: Klik Ulangi ({self.modal_retry_count}/3). Menunggu proses ulang...")
                                
                                # BERI JEDA LEBIH LAMA: Agar server punya waktu memproses
                                self.page.wait_for_timeout(8000) 
                                
                                # RESET TIMER & Submit Status
                                self.state_start_time = time.time()
                                self.last_submit_at = time.time() 
                                return True
                        except Exception as e:
                            print(f"[Tab {self.tab_id}] Gagal klik ulangi: {e}")
                            pass

                        # Error lain (seperti gangguan server yang eksplisit)
                        self.log(f"❌ Tab {self.tab_id}: Terdeteksi gangguan server.")
                        # JANGAN pindahkan ke DONE jika murni error server, agar tidak dianggap sukses palsu
                        self.batch_finished = True
                        self.batch_failed_after_retry = True # Trigger agar tab tetap terbuka
                        self.state = AutoState.CONFIRM_SUCCESS # Paksa verifikasi digital
                        return True
                
                # Turbo mode error fallback
                if self.mode == UploadMode.TURBO and elapsed > 10:
                    self.turbo_errors += 1
                    if self.turbo_errors >= 3:
                        self.log(f"Menyesuaikan sistem...")
                        self.mode = UploadMode.SAFE
                        self.mode_config = MODE_CONFIG[UploadMode.SAFE]
                
                return True

            # -------------------------------------------------
            # DONE / ERROR
            # -------------------------------------------------
            elif self.state == AutoState.DONE:
                return False

            elif self.state == AutoState.ERROR:
                self.log(f"Terjadi kesalahan. Mengulang...")
                self.state = AutoState.OPEN_UPLOAD_PAGE
                self.state_start_time = time.time()
                self.retries += 1

        except Exception as e:
            # Jika browser/tab ditutup, hentikan proses secara instan
            err_str = str(e)

            # Error transien saat redirect / re-render setelah klik Unggah
            # Jangan langsung dianggap gagal karena sering terjadi saat upload sebenarnya berhasil.
            transient_markers = [
                "Execution context was destroyed",
                "Cannot find context with specified id",
                "Frame was detached",
                "frame has been detached",
                "Navigation interrupted",
                "net::ERR_ABORTED",
            ]
            if any(m in err_str for m in transient_markers):
                self.log("ℹ Navigasi ulang terdeteksi, memverifikasi hasil unggahan...")
                self.state = AutoState.CONFIRM_SUCCESS
                self.state_start_time = time.time()
                return True

            if any(msg in err_str for msg in ["Target closed", "Page closed", "Browser closed", "context or browser has been closed"]):
                self.log(f"⚠️ Sistem ditutup. Menandai file sisa...")
                if self.current_batch_files:
                    self._mark_batch(self.current_batch_files, 'failed')
                    self.failed_count += len(self.current_batch_files)
                    self.current_batch_files = []
                self.is_running = False
                return False
            
            try:
                # Log detail ke terminal untuk dev
                print(f"[Tab {self.tab_id}] Exception in run_step: {e}")
                
                # Sederhanakan log error ke UI (throttle agar tidak spam)
                now = time.time()
                if now - self._last_exception_log_at >= 1.0:
                    headline, steps = self._error_guidance(err_str)
                    self.log(headline)
                    if steps and (now - self._last_guidance_log_at >= 6.0):
                        for s in steps[:3]:
                            self.log(f"ℹ️ {s}")
                        self._last_guidance_log_at = now
                    self._last_exception_log_at = now

                # Coba verifikasi ulang: jika sebenarnya sudah sukses (mis. redirect ke profile), jangan tandai gagal.
                if self.current_batch_files:
                    try:
                        browser_state = self.page.evaluate("""() => {
                            const text = document.body ? document.body.innerText : "";
                            const url = window.location.href || "";
                            const isSuccessText = /Selesai!|Berhasil diunggah|Success|Diunggah.*Tetapi|gagal diunggah/i.test(text);
                            const isProfile = url.toLowerCase().includes('/profile/');
                            return { url, isSuccessText, isProfile };
                        }""")
                        if browser_state.get("isProfile") or browser_state.get("isSuccessText"):
                            self.log("✔ Verifikasi ulang: upload terdeteksi berhasil.")
                            self._mark_batch(self.current_batch_files, 'success')
                            self.uploaded_count += len(self.current_batch_files)
                            self.file_index += len(self.current_batch_files)
                            self.current_batch_files = []
                            self.state = AutoState.OPEN_UPLOAD_PAGE
                            self.state_start_time = time.time()
                            return True
                    except Exception:
                        pass

                # Jika exception terjadi sangat dekat setelah klik submit, jangan langsung fail.
                if self.current_batch_files and self.last_submit_at and (time.time() - self.last_submit_at) < 12:
                    now = time.time()
                    if now - self._last_post_submit_wait_log_at >= 1.5:
                        self.log("ℹ Exception pasca-submit, menunggu konfirmasi hasil...")
                        self._last_post_submit_wait_log_at = now
                    self.state = AutoState.CONFIRM_SUCCESS
                    self.state_start_time = time.time()
                    return True
                
                # Jika terlalu banyak retries di batch yang sama, hentikan tab ini
                if self.retries >= 5:
                    self.log(f"⚠️ Terlalu banyak kegagalan. Menghentikan tab ini.")
                    if self.current_batch_files:
                        self._mark_batch(self.current_batch_files, 'failed')
                        self.log("ℹ File tetap di folder asal.")
                        self.failed_count += len(self.current_batch_files)
                        self.file_index += len(self.current_batch_files)
                        self.current_batch_files = []
                    self.is_running = False
                    return False

                self.active_count = 0 # Reset active count on error
                
                # Mark failed files in tracker
                if self.current_batch_files:
                    self._mark_batch(self.current_batch_files, 'failed')
                    self.failed_count += len(self.current_batch_files)
                    self.log(f"ℹ File tetap di folder asal.")
                    
                    self.file_index += len(self.current_batch_files)
                    self.current_batch_files = []
                    
                self.state = AutoState.OPEN_UPLOAD_PAGE
                self.state_start_time = time.time()
                self.retries += 1
                
                # Beri jeda agar tidak spamming loop jika error terus menerus
                time.sleep(1)
            except Exception as nested_e:
                print(f"[Tab {self.tab_id}] Nested Exception: {nested_e}")
                self.log(f"❌ Kesalahan sistem kritis.")
                self.is_running = False
                return False
            
        return True
