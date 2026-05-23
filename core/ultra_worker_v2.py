import os
import sys
import time
import json
import mimetypes
import requests
from PySide6.QtCore import QThread, Signal
from core.license import check_license, get_app_data_dir, get_app_data_dir_by_name

class UltraWorkerV2(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    progress_signal = Signal(int, int, int, int, int)
    fallback_signal = Signal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._is_running = True
        self.token = None
        self.uploaded_count = 0
        self.failed_count = 0
        self.duplicate_count = 0
        
    def stop(self):
        self._is_running = False

    def _get_tracker_base_dirs(self):
        bases = []
        try:
            u = get_app_data_dir_by_name("AutoYuUltra")
            if u: bases.append(u)
        except: pass
        try:
            p = get_app_data_dir()
            if p and p not in bases: bases.append(p)
        except: pass
        return bases

    def _read_first_existing_text(self, paths):
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return f.read().strip(), p
                except: continue
        return None, None

    def get_token(self):
        paths = [os.path.join(b, "trackers", "api_token.txt") for b in self._get_tracker_base_dirs()]
        token, _ = self._read_first_existing_text(paths)
        return token

    def get_headers(self):
        paths = [os.path.join(b, "trackers", "api_headers.json") for b in self._get_tracker_base_dirs()]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f: return json.load(f)
                except: continue
        return {}

    def _load_smart_metadata(self):
        for b in self._get_tracker_base_dirs():
            p = os.path.join(b, "trackers", "api_metadata.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f: return json.load(f) or {}
                except: continue
        return {}

    def _load_ultra_schema(self):
        for b in self._get_tracker_base_dirs():
            p = os.path.join(b, "trackers", "api_ultra_schema.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f: return json.load(f) or {}
                except: continue
        return {}

    def _get_mime_type(self, file_path, is_video):
        ext = os.path.splitext(file_path)[1].lower()
        if is_video:
            if ext == ".mov": return "video/quicktime"
            return "video/mp4"
        if ext == ".png": return "image/png"
        return "image/jpeg"

    def _post_with_retry(self, session, url, headers, data, file_tuple, max_attempts=3):
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            if not self._is_running: break
            try:
                if hasattr(file_tuple[1], "seek"): file_tuple[1].seek(0)
                files = {"file": file_tuple}
                print(f"DEBUG: POST to {url} with headers {list(headers.keys())}")
                resp = session.post(url, headers=headers, data=data, files=files, timeout=(15, 120))
                print(f"DEBUG: Status {resp.status_code}")
                return resp, None
            except Exception as e:
                last_exc = e
                time.sleep(1.0 * attempt)
        return None, last_exc

    def run(self):
        self.log_signal.emit("🚀 <b>Engine V2</b> started...")
        try:
            # Skip License Check for Testing
            # is_valid, status, _, _ = check_license(app_type="pro")
            # if not is_valid:
            #    self.log_signal.emit(f"❌ License Error: {status}")
            #    self.finished_signal.emit()
            #    return
            pass

            # 2. Get Data
            self.token = self.get_token()
            captured_headers = self.get_headers() or {}
            schema = self._load_ultra_schema() or {}
            
            if not self.token:
                self.log_signal.emit("❌ Token not found.")
                self.finished_signal.emit()
                return
            
            # 3. Scan Files
            folder = self.config.get('folder')
            files_to_upload = []
            if folder and os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov')):
                        files_to_upload.append(os.path.join(folder, f))
            
            if not files_to_upload:
                self.log_signal.emit("ℹ️ No files.")
                self.finished_signal.emit()
                return

            # 4. Upload Loop
            url = schema.get("url") or "https://api.fotoyu.com/gs/v3/creations"
            headers = {
                "Authorization": self.token,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                "Origin": "https://www.fotoyu.com",
                "Referer": "https://www.fotoyu.com/",
                "Accept": "application/json"
            }
            headers.update(captured_headers)
            
            self.log_signal.emit(f"🛠️ Uploading {len(files_to_upload)} files...")

            session = requests.Session()
            for idx, file_path in enumerate(files_to_upload):
                if not self._is_running: break
                filename = os.path.basename(file_path)
                
                try:
                    is_video = file_path.lower().endswith(('.mp4', '.mov'))
                    # Build fields
                    fields = schema.get("fields", {}).copy()
                    fields.update({
                        "price": str(self.config.get("price", "9000")),
                        "description": str(self.config.get("desc", "denpasar")),
                        "is_video": "true" if is_video else "false"
                    })
                    
                    with open(file_path, "rb") as f:
                        mime = self._get_mime_type(file_path, is_video)
                        response, exc = self._post_with_retry(session, url, headers, fields, (filename, f, mime))
                    
                    if response:
                        if response.status_code in [200, 201]:
                            self.uploaded_count += 1
                            self.log_signal.emit(f"✅ {filename} SUCCESS")
                        elif response.status_code == 409:
                            self.duplicate_count += 1
                            self.log_signal.emit(f"⚠️ {filename} DUPLICATE")
                        else:
                            self.failed_count += 1
                            self.log_signal.emit(f"❌ {filename} FAILED ({response.status_code}): {response.text[:100]}")
                    else:
                        self.failed_count += 1
                        self.log_signal.emit(f"❌ {filename} ERROR: {str(exc)}")
                
                except Exception as e:
                    self.failed_count += 1
                    self.log_signal.emit(f"❌ Exception: {str(e)}")

                self.progress_signal.emit(self.uploaded_count, self.failed_count, self.duplicate_count, 1, len(files_to_upload))

            self.log_signal.emit("✅ All done.")
            self.finished_signal.emit()

        except Exception as e:
            self.log_signal.emit(f"💥 Fatal: {str(e)}")
            self.finished_signal.emit()
