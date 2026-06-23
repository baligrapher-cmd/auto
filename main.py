import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui.main_window import MainWindow
from core.worker import AutomationWorker
from core.playwright_runtime import configure_playwright_browser_path
 
if sys.platform == "darwin":
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    # Check for smoke test flag
    if "--smoke-test" in sys.argv:
        print("Running smoke test...")
        # Test imports
        import gui.main_window
        import core.worker
        import core.playwright_runtime
        # Configure playwright
        configure_playwright_browser_path()
        print("✓ All imports successful")
        print("✓ Playwright configured")
        print("Smoke test passed!")
        sys.exit(0)
        
    if "QT_SCALE_FACTOR" not in os.environ:
        os.environ["QT_SCALE_FACTOR"] = "0.9"
    # Fix Taskbar Icon for Windows
    try:
        myappid = 'fotoyu.autoyu.automation.3.0' # Updated version
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # Cari bundle browser Playwright dari lokasi internal atau folder di samping executable.
    configure_playwright_browser_path()

    app = QApplication(sys.argv)
    
    # Load Icon
    icon_path = get_resource_path("icon.ico")
    if not os.path.exists(icon_path):
        icon_path = get_resource_path("assets/icon.ico")
        
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    else:
        print(f"Warning: Icon not found at {icon_path}")

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    
    worker = None

    def start_automation(config):
        nonlocal worker
        # Clean up existing worker if any
        if worker and worker.isRunning():
            worker.stop()
            worker.wait()
            
        worker = AutomationWorker(config)
        worker.log_signal.connect(window.log_message)
        worker.progress_signal.connect(window.update_progress)
        worker.batch_finished_signal.connect(window.show_finish_notification)
        worker.login_success_signal.connect(window.on_login_success) # Connect smart button signal
        worker.login_required_signal.connect(lambda: window.set_login_mode(True))
        worker.license_error_signal.connect(window.handle_license_error)
        worker.browser_disconnected_signal.connect(window.handle_browser_disconnected)
        worker.location_resolved_signal.connect(window.on_location_resolved)
        worker.fototree_resolved_signal.connect(lambda name, *args: window._set_fototree_value(name, locked=True, persist=True))
        worker.finished_signal.connect(on_finished)
        
        # Connect confirm login with proper cleanup check
        def handle_continue():
            if worker and worker.isRunning():
                worker.confirm_login()
        
        try:
            window.continue_signal.disconnect()
        except:
            pass
        window.continue_signal.connect(handle_continue)
        
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

if __name__ == "__main__":
    main()
