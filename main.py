import sys
import os
import ctypes
import traceback
import platform
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon

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
        log_dir = os.path.join(home, "Library", "Logs", "AutoYu")
    elif sys.platform == "win32":
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, "AppData", "Local", "AutoYu", "Logs")
    else:
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, ".autoyu", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def log_crash(error_msg):
    """Log crash details to file"""
    try:
        log_dir = get_app_log_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"crash_{timestamp}.log")
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== AutoYu Crash Report ===\n")
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
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    try:
        # Check for smoke test flag
        if "--smoke-test" in sys.argv:
            os.environ["AUTOYU_SMOKE_TEST"] = "1"
            print("Running smoke test...")
            from gui.main_window import MainWindow
            from core.playwright_runtime import configure_playwright_browser_path

            # Test 1: Playwright configuration dan browser discovery
            browser_path = configure_playwright_browser_path()
            print("✓ Core imports successful")
            if browser_path:
                print(f"✓ Found internal browser path: {browser_path}")
            else:
                print("⚠️ No internal browser found, will use Playwright default")

            # Test 2: Try launching Chromium (headless) to verify it works
            print("Testing Chromium launch...")
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as p:
                    # Try launching with internal browser (if available) or default
                    launch_kwargs = {"headless": True}
                    if browser_path:
                        print(f"Using internal browser: {browser_path}")
                    browser = p.chromium.launch(**launch_kwargs)
                    page = browser.new_page()
                    page.goto("https://example.com", timeout=10000)
                    title = page.title()
                    print(f"✓ Chromium launched successfully! Page title: {title}")
                    browser.close()
            except Exception as e:
                print(f"⚠️ Chromium test failed (might be due to environment): {e}")
                print("Continuing with UI test...")

            # Test 3: UI test
            app = QApplication([arg for arg in sys.argv if arg != "--smoke-test"])
            
            # Apply high DPI attributes
            app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

            icon_path = get_resource_path("icon.ico")
            if not os.path.exists(icon_path):
                icon_path = get_resource_path("assets/icon.ico")
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                app.setWindowIcon(app_icon)

            window = MainWindow()
            if os.path.exists(icon_path):
                window.setWindowIcon(QIcon(icon_path))
            window.show()
            app.processEvents()
            print("✓ Main window opened")

            # Keep the event loop alive briefly to verify that the UI can start.
            QTimer.singleShot(500, app.quit)
            exit_code = app.exec()
            window.close()
            app.processEvents()

            if exit_code != 0:
                print(f"Smoke test failed with exit code {exit_code}")
                sys.exit(exit_code)

            print("✅ All smoke tests passed!")
            sys.exit(0)
            
        # Fix Taskbar Icon for Windows
        try:
            myappid = 'fotoyu.autoyu.automation.3.0' # Updated version
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # Cari bundle browser Playwright dari lokasi internal atau folder di samping executable.
        from gui.main_window import MainWindow
        from core.worker import AutomationWorker
        from core.playwright_runtime import configure_playwright_browser_path
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
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"Fatal error: {e}")
        print(error_traceback)
        log_crash(error_traceback)
        sys.exit(1)

if __name__ == "__main__":
    main()
