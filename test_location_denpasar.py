
import sys
import os
import time
import json
from PySide6.QtCore import QCoreApplication
from core.worker import AutomationWorker

def run_test():
    # Setup minimal app for signals
    app = QCoreApplication(sys.argv)
    
    # Target folder (ensure this exists or use a dummy)
    test_folder = os.path.join(os.getcwd(), "live_test_upload_source")
    if not os.path.exists(test_folder):
        os.makedirs(test_folder)
    
    # Create a unique dummy image for each test run to bypass tracker
    timestamp = int(time.time())
    file_path = os.path.join(test_folder, f"test_loc_{timestamp}.jpg")
    with open(file_path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 10 + os.urandom(10))

    config = {
        "current_account": "akun 1",
        "folder": test_folder,
        "price": "40000",
        "desc": "test lokasi denpasar",
        "fototree": "", 
        "location": "Kota Denpasar",
        "tabs": 1,
        "batch_size": 1,
        "mode": "SAFE",
        "type": "foto",
        "is_lite": False
    }
    
    worker = AutomationWorker(config)
    
    def on_log(msg):
        print(f"LOG: {msg}")
        
    def on_finished():
        print("\nTest Finished.")
        app.quit()
        
    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)
    
    print("Starting Worker for Location Fix Test...")
    print(f"Target Location: {config['location']}")
    print(f"Test File: {file_path}")
    worker.start()
    
    # Run for 5 minutes max or until finished
    from PySide6.QtCore import QTimer
    QTimer.singleShot(300000, lambda: app.quit())
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()
