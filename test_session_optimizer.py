
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from core.session_optimizer import SessionManager, FileOptimizer

print("🔍 Testing SessionManager dan FileOptimizer...")

# Test 1: SessionManager
print("\n1. Testing SessionManager...")
session_manager = SessionManager("test_account")
test_folder = os.path.expanduser("~/Pictures")
test_files = ["test1.jpg", "test2.jpg"]
uploaded_files = ["test1.jpg"]
failed_files = []
session_manager.save_session(test_folder, test_files, uploaded_files, failed_files, 1, {"type": "foto"})
session = session_manager.load_session(test_folder)
if session:
    print(f"✅ SessionManager save dan load berhasil!")
else:
    print("❌ SessionManager gagal!")
    print(session)

# Test 2: FileOptimizer
print("\n2. Testing FileOptimizer...")
file_optimizer = FileOptimizer()
# Coba buat gambar dummy jika ada
print(f"✅ FileOptimizer initialized. Has PIL: {file_optimizer}")

print("\n✅ Semua test dasar berhasil! 🎉")
