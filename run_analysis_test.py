
import sys
import os
import time
import json
from PySide6.QtCore import QCoreApplication
from core.worker import AutomationWorker

def run_test():
    # Setup minimal app for signals
    app = QCoreApplication(sys.argv)
    
    config = {
        "current_account": "1",
        "folder": r"C:\Users\PRAMANA VISUAL\Desktop\New folder (4)",
        "price": "38000",
        "desc": "Test Upload Analysis",
        "location": "",
        "tabs": 1,
        "batch_size": 10,
        "mode": "SAFE",
        "type": "foto",
        "auto_calc": False
    }
    
    worker = AutomationWorker(config)
    
    def on_log(msg):
        print(f"LOG: {msg}")
        
    def on_finished():
        print("Test Finished.")
        app.quit()
        
    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)
    
    print("Starting Worker...")
    worker.start()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()
