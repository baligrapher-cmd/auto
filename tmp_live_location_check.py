import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.worker import AutomationWorker
from gui.lite_window import LiteWindow


KEYWORD = "Jakarta Marathon"
TIMEOUT_MS = 120000
SOURCE_POOL = Path(r"C:\Users\PRAMANA VISUAL\Pictures\autoyu\processed")


def find_sample_image():
    for path in SOURCE_POOL.rglob("*"):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.is_file():
            return path
    raise FileNotFoundError(f"Tidak ada file gambar di {SOURCE_POOL}")


def main():
    sample = find_sample_image()
    temp_dir = Path(tempfile.mkdtemp(prefix="autoyu_live_manual_"))
    temp_file = temp_dir / sample.name
    shutil.copy2(sample, temp_file)

    app = QApplication(sys.argv)
    window = LiteWindow()
    window.hide()

    if window.account_combo.findText("autoyu") >= 0:
        window.account_combo.setCurrentText("autoyu")

    window.path_input.setText(str(temp_dir))
    window.price_input.setText("40000")
    window.location_input.setText(KEYWORD)
    window.chk_auto_location.setChecked(True)

    config = window.get_current_config()
    config["login_only"] = False
    config["current_account"] = window.account_combo.currentText() or "autoyu"
    config["location"] = KEYWORD
    config["auto_location"] = True
    config["folder"] = str(temp_dir)
    config["tabs"] = 1
    config["batch_size"] = 1
    config["type"] = "foto"
    config["auto_calc"] = False
    config["is_lite"] = True

    worker = AutomationWorker(config)
    logs = []
    result = {
        "resolved_name": None,
        "match_type": None,
        "source": None,
        "ui_value": None,
        "status": "timeout",
    }

    def on_log(message):
        logs.append(str(message))

    def finish(status):
        result["status"] = status
        result["ui_value"] = window.location_input.text().strip()
        if worker.isRunning():
            worker.stop()
        QTimer.singleShot(300, app.quit)

    def on_location_resolved(name, match_type, source):
        window.on_location_resolved(name, match_type, source)
        result["resolved_name"] = str(name)
        result["match_type"] = str(match_type)
        result["source"] = str(source)
        finish("resolved")

    def on_license_error():
        finish("license_error")

    def on_finished():
        if result["status"] == "timeout":
            result["status"] = "finished_without_resolution"
            result["ui_value"] = window.location_input.text().strip()
        QTimer.singleShot(100, app.quit)

    worker.log_signal.connect(on_log)
    worker.location_resolved_signal.connect(on_location_resolved)
    worker.license_error_signal.connect(on_license_error)
    worker.finished_signal.connect(on_finished)

    QTimer.singleShot(TIMEOUT_MS, lambda: finish("timeout"))
    worker.start()
    app.exec()
    if worker.isRunning():
        worker.wait(3000)

    print("LIVE_TEST_STATUS:", result["status"])
    print("LIVE_TEST_KEYWORD:", KEYWORD)
    print("LIVE_TEST_SOURCE:", result["source"])
    print("LIVE_TEST_MATCH_TYPE:", result["match_type"])
    print("LIVE_TEST_RESOLVED:", result["resolved_name"])
    print("LIVE_TEST_UI_VALUE:", result["ui_value"])
    print("LIVE_TEST_LOG_COUNT:", len(logs))
    for line in logs[-25:]:
        print("LOG:", line)

    shutil.rmtree(temp_dir, ignore_errors=True)

    if result["status"] != "resolved":
        return 1
    if not result["resolved_name"] or result["ui_value"] != result["resolved_name"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
