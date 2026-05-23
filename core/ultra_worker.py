
import os
import sys
import time
import json
import mimetypes
import requests
from PySide6.QtCore import QThread, Signal
from core.license import check_license, get_app_data_dir, get_app_data_dir_by_name

class UltraWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    progress_signal = Signal(int, int, int, int, int) # uploaded, failed, duplicate, active, total
    fallback_signal = Signal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._is_running = True
        self.token = None
        self.uploaded_count = 0
        self.failed_count = 0
        self.duplicate_count = 0
        self._fallback_emitted = False
        
    def stop(self):
        self._is_running = False

    def _get_tracker_base_dirs(self):
        try:
            ultra_base = get_app_data_dir_by_name("AutoYuUltra")
        except Exception:
            ultra_base = None
        try:
            pro_base = get_app_data_dir()
        except Exception:
            pro_base = None
        bases = []
        if ultra_base:
            bases.append(ultra_base)
        if pro_base and pro_base not in bases:
            bases.append(pro_base)
        return bases

    def _read_first_existing_text(self, paths):
        for p in paths:
            if not p:
                continue
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return f.read().strip(), p
                except Exception:
                    continue
        return None, None

    def _write_text(self, path, content):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            return True
        except Exception:
            return False

    def get_token(self):
        token_paths = []
        for base in self._get_tracker_base_dirs():
            token_paths.append(os.path.join(base, "trackers", "api_token.txt"))
        token, from_path = self._read_first_existing_text(token_paths)
        return token

    def get_headers(self):
        header_paths = []
        for base in self._get_tracker_base_dirs():
            header_paths.append(os.path.join(base, "trackers", "api_headers.json"))
        
        for p in header_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    continue
        return None

    def _load_smart_metadata(self):
        for base in self._get_tracker_base_dirs():
            metadata_file = os.path.join(base, "trackers", "api_metadata.json")
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        return json.load(f) or {}
                except Exception:
                    continue
        return {}

    def _load_ultra_schema(self):
        for base in self._get_tracker_base_dirs():
            schema_file = os.path.join(base, "trackers", "api_ultra_schema.json")
            if os.path.exists(schema_file):
                try:
                    with open(schema_file, "r", encoding="utf-8") as f:
                        return json.load(f) or {}
                except Exception:
                    continue
        return {}

    def _get_mime_type(self, file_path, is_video):
        ext = os.path.splitext(file_path)[1].lower()
        if is_video:
            if ext == ".mov":
                return "video/quicktime"
            if ext == ".mp4":
                return "video/mp4"
            guessed = mimetypes.guess_type(file_path)[0]
            return guessed or "application/octet-stream"
        if ext == ".png":
            return "image/png"
        if ext in (".jpg", ".jpeg"):
            return "image/jpeg"
        guessed = mimetypes.guess_type(file_path)[0]
        return guessed or "application/octet-stream"

    def _post_with_retry(self, session, url, headers, data, file_tuple, max_attempts=3):
        last_exc = None
        last_status = None
        last_text = ""
        for attempt in range(1, max_attempts + 1):
            if not self._is_running:
                break
            try:
                try:
                    fobj = file_tuple[1]
                    if hasattr(fobj, "seek"):
                        fobj.seek(0)
                except Exception:
                    pass
                file_field = str(headers.get("_ultra_file_field") or "file")
                if file_field.startswith("_"):
                    file_field = "file"
                files = {file_field: file_tuple}
                resp = session.post(url, headers=headers, data=data, files=files, timeout=(10, 120))
                last_status = resp.status_code
                try:
                    last_text = resp.text or ""
                except Exception:
                    last_text = ""

                if resp.status_code in (200, 201, 401, 409, 403, 404):
                    return resp, None

                if resp.status_code in (429, 500, 502, 503, 504):
                    backoff = 1.2 * attempt
                    time.sleep(backoff)
                    continue

                return resp, None
            except Exception as e:
                last_exc = e
                backoff = 1.0 * attempt
                time.sleep(backoff)

        err = {"exception": last_exc, "status_code": last_status, "text": last_text}
        try:
            if last_exc is not None:
                err["exception_type"] = type(last_exc).__name__
        except Exception:
            pass
        return None, err

    def run(self):
        self.log_signal.emit("🚀 <b>AutoYu ULTRA Engine</b> dimulai...")
        try:
            # 1. License Check
            app_type = str(self.config.get("app_type") or "pro").lower()
            if app_type == "ultra":
                app_type = "pro"
            is_valid, status, _, _ = check_license(app_type=app_type)
            if not is_valid:
                self.log_signal.emit(f"❌ Lisensi tidak valid: {status}")
                self.finished_signal.emit()
                return

            # 2. Get Token & Headers
            self.token = self.get_token()
            captured_headers = self.get_headers()
            
            if not self.token:
                self.log_signal.emit("❌ <b>Token tidak ditemukan!</b>")
                self.log_signal.emit("ℹ️ <b>Cara Memperbaiki:</b>")
                self.log_signal.emit("1. Di ULTRA, klik tombol <b>LOGIN & SETUP METADATA</b>.")
                self.log_signal.emit("2. Login di browser yang muncul.")
                self.log_signal.emit("3. Upload manual 1 file sampai berhasil (sekali saja).")
                self.log_signal.emit("4. Tutup browser, lalu jalankan ULTRA ENGINE lagi.")
                self.finished_signal.emit()
                return
            
            self.log_signal.emit("🔑 Token akses terdeteksi. Memulai Direct API Upload...")

            # 3. Scan Files
            source_folder = self.config.get('folder')
            if not source_folder or not os.path.exists(source_folder):
                self.log_signal.emit("❌ Folder sumber tidak ditemukan!")
                self.finished_signal.emit()
                return

            price = str(self.config.get("price", "")).strip()
            if not price:
                self.log_signal.emit("❌ Harga wajib diisi untuk ULTRA.")
                self.finished_signal.emit()
                return

            all_files = []
            for root, _, files in os.walk(source_folder):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov')):
                        all_files.append(os.path.join(root, f))
            
            total_files = len(all_files)
            if total_files == 0:
                self.log_signal.emit("ℹ️ Tidak ada file untuk diunggah di folder tersebut.")
                self.finished_signal.emit()
                return

            self.log_signal.emit(f"📦 Ditemukan {total_files} file. Memulai proses Ultra Speed...")

            # 4. Upload Loop
            schema = self._load_ultra_schema()
            url = schema.get("url") or "https://api.fotoyu.com/gs/v3/creations"
            
            # Load Smart Metadata (FotoTree & Lokasi) jika ada
            smart_meta = self._load_smart_metadata()
            if smart_meta:
                self.log_signal.emit("✨ <b>Smart Metadata Detected</b>: Menggunakan FotoTree/Lokasi dari setup terakhir.")

            # Priority 1: Captured Headers (Real), Priority 2: Standard Fallback
            headers = {
                "Authorization": self.token,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Origin": "https://www.fotoyu.com",
                "Referer": "https://www.fotoyu.com/upload",
                "Accept": "application/json"
            }
            if captured_headers:
                headers.update(captured_headers)
                self.log_signal.emit("🌐 <b>Browser Fingerprint Match</b>: Menggunakan header asli dari browser.")

            file_field = str(schema.get("file_field") or "file").strip() or "file"
            headers["_ultra_file_field"] = file_field
            
            # Diagnostic Log (VERSI TERBARU V100)
            self.log_signal.emit(f"🛠️ <b>Debug Info</b>: Endpoint={url} | Field={file_field} | Method=POST")

            session = requests.Session()
            for idx, file_path in enumerate(all_files):
                if not self._is_running:
                    break

                filename = os.path.basename(file_path)
                self.log_signal.emit(f"📤 [{idx+1}/{total_files}] Mengunggah: {filename}...")
                
                try:
                    is_video = file_path.lower().endswith(('.mp4', '.mov'))
                    
                    # Gunakan skema fields dari pancingan terakhir
                    data = schema.get("fields", {}).copy()
                    
                    # Override dengan input user saat ini
                    data["price"] = price
                    data["description"] = str(self.config.get('desc', ''))
                    data["is_video"] = "true" if is_video else "false"
                    
                    # Tambahkan ID FotoTree/Lokasi jika tersedia dari pancingan Smart Metadata
                    if smart_meta.get("tree_id"): data["tree_id"] = smart_meta["tree_id"]
                    if smart_meta.get("location_id"): data["location_id"] = smart_meta["location_id"]
                    
                    with open(file_path, "rb") as f:
                        mime_type = self._get_mime_type(file_path, is_video=is_video)
                        file_tuple = (filename, f, mime_type)
                        response, err = self._post_with_retry(session, url, headers, data, file_tuple, max_attempts=3)
                        if response is not None and response.status_code == 400:
                            try:
                                body = (response.text or "").lower()
                            except Exception:
                                body = ""
                            if "invalid format" in body:
                                try:
                                    f.seek(0)
                                except Exception:
                                    pass
                                alt_tuple = (filename, f)
                                response_alt, err_alt = self._post_with_retry(session, url, headers, data, alt_tuple, max_attempts=1)
                                if response_alt is not None:
                                    response, err = response_alt, err_alt
                                else:
                                    try:
                                        f.seek(0)
                                    except Exception:
                                        pass
                                    alt_tuple2 = (filename, f, "application/octet-stream")
                                    response_alt2, err_alt2 = self._post_with_retry(session, url, headers, data, alt_tuple2, max_attempts=1)
                                    if response_alt2 is not None:
                                        response, err = response_alt2, err_alt2
                    
                    if response is None:
                        self.failed_count += 1
                        exc = err.get("exception") if err else None
                        exc_type = err.get("exception_type") if err else None
                        status_code = err.get("status_code") if err else None
                        text = err.get("text") if err else ""
                        if exc_type:
                            msg = f"{exc_type}: {str(exc) or '(no message)'}"
                        elif exc:
                            msg = f"{type(exc).__name__}: {str(exc) or '(no message)'}"
                        elif status_code:
                            msg = f"HTTP {status_code}"
                        else:
                            msg = "Koneksi/timeout (tanpa detail)"
                        if text:
                            snippet = text.strip().replace("\n", " ")[:160]
                            self.log_signal.emit(f"❌ {filename} gagal: {msg} | {snippet}")
                        else:
                            self.log_signal.emit(f"❌ {filename} gagal: {msg}")
                    elif response.status_code in [200, 201, 409]:
                        if response.status_code == 409:
                            self.duplicate_count += 1
                            self.log_signal.emit(f"⚠️ {filename} duplikat.")
                        else:
                            self.uploaded_count += 1
                    else:
                        self.failed_count += 1
                        snippet = ""
                        try:
                            snippet = (response.text or "").strip().replace("\n", " ")[:160]
                        except Exception:
                            snippet = ""
                        if snippet:
                            self.log_signal.emit(f"❌ {filename} gagal (HTTP {response.status_code}) | {snippet}")
                        else:
                            self.log_signal.emit(f"❌ {filename} gagal (HTTP {response.status_code})")
                        if response.status_code == 400 and "invalid format" in snippet.lower():
                            self.log_signal.emit("ℹ️ ULTRA: Format body API tidak cocok. Jalankan LOGIN & SETUP METADATA sekali lagi agar ULTRA menangkap skema field upload terbaru.")
                            if not self._fallback_emitted:
                                self._fallback_emitted = True
                                try:
                                    self.fallback_signal.emit("API_INVALID_FORMAT")
                                except Exception:
                                    pass
                                self._is_running = False
                                break
                
                except Exception as e:
                    self.failed_count += 1
                    self.log_signal.emit(f"❌ Error pada {filename}: {str(e)}")

                # Emit progress
                self.progress_signal.emit(self.uploaded_count, self.failed_count, self.duplicate_count, 1, total_files)
                
                # Jeda sangat singkat agar server tidak overload
                time.sleep(0.05)

            self.log_signal.emit("✅ <b>Proses Selesai!</b>")
            self.log_signal.emit(f"📊 Statistik: {self.uploaded_count} Sukses, {self.failed_count} Gagal, {self.duplicate_count} Duplikat.")
            self.finished_signal.emit()

        except Exception as e:
            self.log_signal.emit(f"💥 CRITICAL ERROR: {str(e)}")
            self.finished_signal.emit()
