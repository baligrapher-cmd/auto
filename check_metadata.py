
import os
import sys
import json
from pathlib import Path

def get_app_data_dir():
    app_name = "AutoYuPro"
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        base_dir = os.path.join(appdata, app_name)
    elif sys.platform == "darwin":
        base_dir = os.path.join(os.path.expanduser("~/Library/Application Support"), app_name)
    else:
        base_dir = os.path.join(os.path.expanduser("~/.config"), app_name)
    return base_dir

base_dir = get_app_data_dir()
tracker_dir = os.path.join(base_dir, "trackers")
print(f"Checking tracker dir: {tracker_dir}")
if os.path.exists(tracker_dir):
    for filename in os.listdir(tracker_dir):
        if filename.startswith("api_metadata"):
            filepath = os.path.join(tracker_dir, filename)
            print(f"\n--- {filename} ---")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(json.dumps(data, indent=2))
            except Exception as e:
                print(f"Error reading: {e}")
else:
    print("Tracker dir doesn't exist!")

