
import sys
import os
import ctypes
import multiprocessing
import traceback
import platform
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from gui.lite_window import LiteWindow
from core.worker import AutomationWorker
from core.playwright_runtime import configure_playwright_browser_path


if __name__ == "__main__":
    multiprocessing.freeze_support()


# === SET ALL QT ENVIRONMENT VARIABLES BEFORE ANY QApplication IS CREATED ===
if sys.platform == "darwin":
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

# High DPI / UI Scaling Settings (CRITICAL for proper display)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "RoundPreferFloor"


def get_app_log_dir():
    """Get directory for app logs, create if doesn't exist"""
    if sys.platform == "darwin":
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, "Library", "Logs", "AutoYuLite")
    elif sys.platform == "win32":
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, "AppData", "Local", "AutoYuLite", "Logs")
    else:
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, ".autoyulite", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def log_crash(error_msg):
    """Log crash details to file"""
    try:
        log_dir = get_app_log_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"crash_{timestamp}.log")
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== AutoYu Lite Crash Report ===\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"Architecture: {platform.machine()}\n")
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            if hasattr(sys, '_MEIPASS'):
                f.write(f"MEIPASS: {sys._MEIPASS}\n")
            f.write("\n=== Error Traceback ===\n")
            f.write(error_msg)
        print(f"Crash log saved to: {log_file}")
        return log_file
    except Exception as e:
        print(f"Failed to write crash log: {e}")
        return None


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def main():
    try:
        if "QT_SCALE_FACTOR" not in os.environ:
            os.environ["QT_SCALE_FACTOR"] = "0.9"

        try:
            myappid = "fotoyu.autoyu.lite.3.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # Samakan perilaku browser portable dengan versi utama.
        configure_playwright_browser_path()

        app = QApplication(sys.argv)
        
        # Apply high DPI attributes
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Load Icon
        icon_path = get_resource_path("icon.ico")
        if not os.path.exists(icon_path):
            icon_path = get_resource_path("assets/icon.ico")
            
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            app.setWindowIcon(app_icon)
        else:
            print(f"Warning: Icon not found at {icon_path}")

        window = LiteWindow()
        if os.path.exists(icon_path):
            window.setWindowIcon(QIcon(icon_path))

        worker = None

        def start_automation(config):
            nonlocal worker
            print(f"[MainLite] start_automation triggered with config: {config}")

            if worker and worker.isRunning():
                print("[MainLite] Stopping existing worker...")
                worker.stop()
                worker.wait()

            print("[MainLite] Creating new AutomationWorker...")
            worker = AutomationWorker(config)
            worker.log_signal.connect(window.log_message)
            worker.progress_signal.connect(window.update_progress)
            worker.batch_finished_signal.connect(window.show_finish_notification)
            worker.login_success_signal.connect(window.on_login_success)
            worker.login_required_signal.connect(lambda: window.set_login_mode(True))
            worker.license_error_signal.connect(window.handle_license_error)
            worker.browser_disconnected_signal.connect(window.handle_browser_disconnected)
            worker.location_resolved_signal.connect(window.on_location_resolved)
            worker.fototree_resolved_signal.connect(lambda name, *args: window._set_fototree_value(name, locked=True, persist=True))
            worker.finished_signal.connect(on_finished)

            def handle_continue():
                print("[MainLite] handle_continue triggered")
                if worker and worker.isRunning():
                    worker.confirm_login()

            try:
                window.continue_signal.disconnect()
            except Exception:
                pass
            window.continue_signal.connect(handle_continue)

            print("[MainLite] Starting worker thread...")
            worker.start()

        def stop_automation():
            if worker:
                worker.stop()

        def on_finished():
            window.reset_ui()
            window.log_message("Automation process terminated.")

        window.start_signal.connect(start_automation)
        window.stop_signal.connect(stop_automation)

        window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"Fatal error: {e}")
        print(error_traceback)
        log_crash(error_traceback)
        sys.exit(1)


if __name__ == "__main__":
    main()
