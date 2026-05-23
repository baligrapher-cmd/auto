import requests
import webbrowser
from PySide6.QtCore import QThread, Signal

# URL untuk cek versi terbaru
UPDATE_JSON_URL = "https://pramana.web.id/autoyu/download/update.json"
DOWNLOAD_PAGE_URL = "https://pramana.web.id/autoyu/download/"

class UpdateChecker(QThread):
    update_available = Signal(dict) # Mengirimkan data update jika tersedia

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            # Gunakan timeout pendek agar tidak menghambat startup
            response = requests.get(UPDATE_JSON_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Di version.json biasanya strukturnya {"version": "3.x.x", "changelog": "...", "url": "..."}
                latest_version = data.get("version")
                
                if latest_version and self._is_newer(latest_version, self.current_version):
                    self.update_available.emit(data)
        except Exception:
            # Gagal cek update bukan masalah kritis, abaikan saja
            pass

    def _is_newer(self, latest, current):
        """Membandingkan string versi (misal 3.0.1 > 3.0.0)"""
        try:
            l_parts = [int(p) for p in latest.split('.')]
            c_parts = [int(p) for p in current.split('.')]
            # Bandingkan part demi part
            for l, c in zip(l_parts, c_parts):
                if l > c: return True
                if l < c: return False
            return len(l_parts) > len(c_parts)
        except Exception:
            return str(latest) > str(current)

def open_download_page(custom_url=None):
    """Membuka link download di browser bawaan pengguna."""
    webbrowser.open(custom_url or DOWNLOAD_PAGE_URL)
