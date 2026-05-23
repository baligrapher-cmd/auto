
import sys
import os
import time
import json
from PySide6.QtCore import QCoreApplication
from core.worker import AutomationWorker

def run_test():
    # Setup minimal app for signals
    app = QCoreApplication(sys.argv)
    
    # Use config from user_settings.json but override folder
    config = {
        "current_account": "1",
        "folder": r"C:\Users\PRAMANA VISUAL\Pictures\asli",
        "price": "38000",
        "desc": "Debug Real Upload",
        "location": "",
        "tabs": 1,
        "batch_size": 3,
        "mode": "SAFE",
        "type": "foto",
        "auto_calc": False
    }
    
    worker = AutomationWorker(config)
    
    # Track JSON responses
    json_responses = []

    def on_log(msg):
        print(f"LOG: {msg}")
        if "DEBUG_JSON_RAW:" in msg:
            try:
                # Extract JSON string
                json_str = msg.split("DEBUG_JSON_RAW:")[1].strip()
                data = json.loads(json_str)
                json_responses.append(data)
                # Save to file for analysis
                filename = f"response_{len(json_responses)}.json"
                with open(filename, "w") as f:
                    json.dump(data, f, indent=4)
                print(f">>> SUCCESS: Captured JSON response to {filename}")
            except Exception as e:
                print(f"ERROR parsing JSON: {e}")
        
    def on_finished():
        print("\n" + "="*50)
        print("Test Finished.")
        if json_responses:
            print(f"Captured {len(json_responses)} JSON responses.")
            print("Check 'last_server_response.json' for the detailed structure.")
        else:
            print("No JSON response captured. Check logs above.")
        print("="*50 + "\n")
        app.quit()
        
    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)
    
    # Auto confirm login if prompted
    worker.login_success_signal.connect(lambda: worker.confirm_login())
    
    print("Starting Worker with Real Files...")
    worker.start()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()
