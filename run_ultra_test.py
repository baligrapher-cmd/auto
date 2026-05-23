
import os
import sys
import time
from core.ultra_worker import UltraWorker
from core.license import get_app_data_dir

def run_test():
    print("=== PENGUJIAN MODE ULTRA (DIRECT API) ===")
    
    config = {
        "folder": r"D:\demo",
        "price": "15000",
        "desc": "Testing Ultra Mode API",
        "app_type": "pro",
        "current_account": "TestAccount"
    }
    
    worker = UltraWorker(config)
    
    # Track logs
    def on_log(msg):
        print(f"LOG: {msg}")
        
    def on_progress(uploaded, failed, duplicate, active, total):
        print(f"PROGRESS: {uploaded}/{total} (Gagal: {failed}, Duplikat: {duplicate})")

    worker.log_signal.connect(on_log)
    worker.progress_signal.connect(on_progress)
    
    print(f"Mulai pengujian pada folder: {config['folder']}")
    worker.run() # Run synchronous for testing
    print("Pengujian selesai.")

if __name__ == "__main__":
    run_test()
