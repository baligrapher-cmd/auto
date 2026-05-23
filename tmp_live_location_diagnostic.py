import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import core.automation as automation_module
from core.state_machine import AutoState
from core.worker import AutomationWorker


KEYWORD = "Jakarta Marathon"
TIMEOUT_MS = 120000
SOURCE_POOL = Path(r"C:\Users\PRAMANA VISUAL\Pictures\autoyu\processed")
STATE_HISTORY = []
RESOLVE_CALLS = []


def find_sample_image():
    for path in SOURCE_POOL.rglob("*"):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.is_file():
            return path
    raise FileNotFoundError(f"Tidak ada file gambar di {SOURCE_POOL}")


def patch_automation():
    original_run_step = automation_module.TabAutomation.run_step
    original_resolve = automation_module.TabAutomation._resolve_runtime_location

    def patched_resolve(self, keyword):
        RESOLVE_CALLS.append(str(keyword or ""))
        return original_resolve(self, keyword)

    def patched_run_step(self):
        before = getattr(self, "state", None)
        result = original_run_step(self)
        after = getattr(self, "state", None)
        before_name = before.value if before else None
        after_name = after.value if after else None
        STATE_HISTORY.append((before_name, after_name))

        if after == AutoState.SUBMIT and not getattr(self, "_resolved_location", None):
            self.log("DIAG: SUBMIT tercapai tanpa resolved location. Stop untuk analisis.")
            self.is_running = False
            return False
        return result

    automation_module.TabAutomation.run_step = patched_run_step
    automation_module.TabAutomation._resolve_runtime_location = patched_resolve
    return original_run_step, original_resolve


def restore_automation(original_run_step, original_resolve):
    automation_module.TabAutomation.run_step = original_run_step
    automation_module.TabAutomation._resolve_runtime_location = original_resolve


def main():
    sample = find_sample_image()
    temp_dir = Path(tempfile.mkdtemp(prefix="autoyu_live_diag_"))
    temp_file = temp_dir / sample.name
    shutil.copy2(sample, temp_file)

    app = QApplication(sys.argv)
    config = {
        "current_account": "autoyu",
        "folder": str(temp_dir),
        "price": "40000",
        "desc": "Uploaded via AutoYu V3 Engine",
        "location": KEYWORD,
        "auto_location": True,
        "tabs": 1,
        "batch_size": 1,
        "type": "foto",
        "auto_calc": False,
        "is_lite": True,
        "login_only": False,
    }

    original_run_step, original_resolve = patch_automation()
    worker = AutomationWorker(config)
    logs = []
    status = {"value": "timeout"}

    def on_log(message):
        logs.append(str(message))

    def stop_with(status_value):
        if status["value"] == "timeout":
            status["value"] = status_value
        if worker.isRunning():
            worker.stop()
        QTimer.singleShot(500, app.quit)

    worker.log_signal.connect(on_log)
    worker.location_resolved_signal.connect(lambda *_: stop_with("resolved"))
    worker.finished_signal.connect(lambda: QTimer.singleShot(100, app.quit))
    QTimer.singleShot(TIMEOUT_MS, lambda: stop_with("timeout"))

    worker.start()
    app.exec()
    if worker.isRunning():
        worker.wait(3000)

    restore_automation(original_run_step, original_resolve)

    print("DIAG_STATUS:", status["value"])
    print("DIAG_RESOLVE_CALLS:", RESOLVE_CALLS)
    print("DIAG_STATE_HISTORY:", STATE_HISTORY[-30:])
    for line in logs[-40:]:
        print("LOG:", line)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
