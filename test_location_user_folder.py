
import sys
import os
import time
import json
from PySide6.QtCore import QCoreApplication
from core.worker import AutomationWorker

def run_test():
    # Setup minimal app for signals
    app = QCoreApplication(sys.argv)
    
    # Folder dari user
    test_folder = r"C:\Users\PRAMANA VISUAL\Pictures\sdszxzxzDSDS"
    
    config = {
        "current_account": "akun 1",
        "folder": test_folder,
        "price": "40000",
        "desc": "test lokasi denpasar user folder",
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
    
    print("Starting Worker for Location Fix Test (User Folder)...")
    print(f"Target Location: {config['location']}")
    print(f"Test Folder: {test_folder}")
    worker.start()
    
    # Run for 5 minutes max or until finished
    from PySide6.QtCore import QTimer
    QTimer.singleShot(300000, lambda: app.quit())
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()
