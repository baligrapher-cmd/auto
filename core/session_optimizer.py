
import os
import json
import time
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from core.license import get_app_data_dir

# Try to import PIL for image compression, fallback gracefully
HAS_PIL = False
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    pass


class SessionManager:
    """Manajemen session upload untuk fitur Auto-Resume"""
    
    def __init__(self, account_name: str = "default"):
        self.app_data_dir = get_app_data_dir()
        self.sessions_dir = os.path.join(self.app_data_dir, "sessions")
        self.account_name = account_name
        self._ensure_dir()
    
    def _ensure_dir(self):
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir, exist_ok=True)
    
    def _get_session_file(self, folder_path: str) -> str:
        """Dapatkan nama file session berdasarkan path folder"""
        import hashlib
        # Normalisasi path untuk konsistensi di semua OS
        abs_path = os.path.abspath(os.path.expanduser(folder_path))
        if os.name == 'nt':
            abs_path = abs_path.lower()
        folder_hash = hashlib.md5(abs_path.encode('utf-8')).hexdigest()[:12]
        account_safe = self.account_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        return os.path.join(self.sessions_dir, f"session_{account_safe}_{folder_hash}.json")
    
    def save_session(self, folder_path: str, files: List[str], 
                     uploaded_files: List[str], failed_files: List[str],
                     current_index: int, config: Dict) -> bool:
        """Simpan state session saat ini"""
        try:
            session_data = {
                "version": "1.0",
                "folder_path": folder_path,
                "account_name": self.account_name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "files": files,
                "uploaded_files": uploaded_files,
                "failed_files": failed_files,
                "current_index": current_index,
                "config": config
            }
            
            session_file = self._get_session_file(folder_path)
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[SessionManager] Error saving session: {e}")
            return False
    
    def load_session(self, folder_path: str) -> Optional[Dict]:
        """Muat session terakhir untuk folder tertentu"""
        try:
            session_file = self._get_session_file(folder_path)
            if os.path.exists(session_file):
                with open(session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[SessionManager] Error loading session: {e}")
        return None
    
    def delete_session(self, folder_path: str) -> bool:
        """Hapus session setelah upload selesai"""
        try:
            session_file = self._get_session_file(folder_path)
            if os.path.exists(session_file):
                os.remove(session_file)
            return True
        except Exception as e:
            print(f"[SessionManager] Error deleting session: {e}")
            return False
    
    def has_resumable_session(self, folder_path: str) -> Tuple[bool, int]:
        """Cek apakah ada session yang bisa diresume, return (has_session, remaining_files)"""
        session = self.load_session(folder_path)
        if session:
            remaining = len(session.get("files", [])) - session.get("current_index", 0)
            if remaining > 0:
                return True, remaining
        return False, 0


class FileOptimizer:
    """Optimizer file untuk kompresi sebelum upload"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.app_data_dir = get_app_data_dir()
        self.temp_dir = temp_dir or os.path.join(self.app_data_dir, "optimized_temp")
        self._ensure_dir()
    
    def _ensure_dir(self):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
    
    def optimize_image(self, file_path: str, quality: int = 85, 
                      max_width: Optional[int] = 2000, 
                      max_height: Optional[int] = 2000) -> Optional[str]:
        """
        Optimisasi gambar sebelum upload
        Returns path ke file terkompresi, atau None jika gagal
        """
        if not HAS_PIL:
            return None
            
        try:
            img = Image.open(file_path)
            
            # Check jika perlu resize
            original_width, original_height = img.size
            new_width, new_height = original_width, original_height
            
            if max_width and original_width > max_width:
                ratio = max_width / original_width
                new_width = max_width
                new_height = int(original_height * ratio)
                
            if max_height and new_height > max_height:
                ratio = max_height / new_height
                new_height = max_height
                new_width = int(new_width * ratio)
            
            # Resize jika diperlukan
            if (new_width, new_height) != (original_width, original_height):
                img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Simpan file terkompresi
            file_name = os.path.basename(file_path)
            optimized_path = os.path.join(self.temp_dir, f"optimized_{file_name}")
            
            # Convert to RGB if RGBA for JPEG compatibility
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            img.save(optimized_path, quality=quality, optimize=True)
            
            return optimized_path
        except Exception as e:
            print(f"[FileOptimizer] Error optimizing {file_path}: {e}")
            return None
    
    def should_optimize(self, file_path: str, size_threshold_mb: float = 2.0) -> bool:
        """Cek apakah file perlu dioptimisasi (berdasarkan ukuran)"""
        if not HAS_PIL:
            return False
            
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            return file_size_mb > size_threshold_mb
        except Exception:
            return False
    
    def cleanup_temp_files(self):
        """Bersihkan file temporary"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            print(f"[FileOptimizer] Error cleaning up: {e}")
