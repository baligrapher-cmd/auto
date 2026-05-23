import os
import sys
import time
import shutil
import threading
from PySide6.QtCore import QCoreApplication
from core.worker import AutomationWorker
from core.state_machine import UploadMode

# Initialize QCoreApplication for Signals
app = QCoreApplication(sys.argv)

def real_simulation():
    test_dir = os.path.abspath("real_test_env")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    source_dir = os.path.join(test_dir, "source")
    os.makedirs(source_dir)
    
    # Create 5 dummy files
    files = []
    for i in range(5):
        f_path = os.path.join(source_dir, f"photo_{i}.jpg")
        with open(f_path, "wb") as f:
            f.write(b"fake image content")
        files.append(f_path)
    
    config = {
        "current_account": "test_acc",
        "folder": source_dir,
        "tabs": 1,
        "batch_size": 5,
        "type": "foto",
        "auto_calc": False,
        "mode": UploadMode.SAFE
    }
    
    worker = AutomationWorker(config)
    
    # Override login detection to proceed immediately
    worker._login_confirmed = True 
    
    def on_log(msg):
        print(f"[LOG] {msg}")

    worker.log_signal.connect(on_log)
    
    def run_worker():
        worker.run()
        print("[WORKER] Stopped.")
        app.quit()

    thread = threading.Thread(target=run_worker)
    thread.start()
    
    print("[TEST] Menunggu browser terbuka...")
    # Wait for browser to be initialized
    for _ in range(30):
        if worker.context and worker.context.browser:
            print("[TEST] Browser terdeteksi!")
            break
        time.sleep(1)
    else:
        print("[TEST] Browser tidak terbuka dalam 30 detik.")
        worker._is_running = False
        app.quit()
        return

    time.sleep(5) # Biarkan berjalan sebentar
    
    print("[TEST] SIMULASI: Menutup browser secara paksa...")
    try:
        # Menutup browser secara paksa
        if worker.context:
            worker.context.browser.close()
    except Exception as e:
        print(f"[TEST] Browser closed with error (expected): {e}")

    # Tunggu worker menyelesaikan cleanup
    print("[TEST] Menunggu cleanup selesai...")
    thread.join(timeout=30)
    
    # Verifikasi folder
    failed_dir = os.path.join(source_dir, "failed")
    processed_dir = os.path.join(source_dir, "processed")
    
    failed_files = os.listdir(failed_dir) if os.path.exists(failed_dir) else []
    processed_files = os.listdir(processed_dir) if os.path.exists(processed_dir) else []
    
    print("\n--- HASIL AKHIR SIMULASI ---")
    print(f"File di FAILED: {len(failed_files)}")
    print(f"File di PROCESSED: {len(processed_files)}")
    
    if len(failed_files) == 5:
        print("\n✅ BERHASIL: Semua file sisa berhasil diamankan ke folder 'failed'!")
    else:
        print("\n❌ GAGAL: Masih ada file yang tertinggal atau hilang.")
    
    app.quit()

if __name__ == "__main__":
    # Run simulation in a thread to keep app loop responsive if needed
    sim_thread = threading.Thread(target=real_simulation)
    sim_thread.start()
    sys.exit(app.exec())
