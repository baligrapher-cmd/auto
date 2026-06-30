
import sys
import os

# === SET ALL QT ENVIRONMENT VARIABLES BEFORE ANY QApplication IS CREATED ===
if sys.platform == "darwin":
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

# High DPI / UI Scaling Settings (CRITICAL for proper display)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "RoundPreferFloor"

# Tambahkan current directory ke sys.path agar bisa import module lokal
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from gui.ultra_window import UltraWindow

def main():
    app = QApplication(sys.argv)
    
    # Apply high DPI attributes
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Set App Icon
    icon_path = os.path.join(current_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = UltraWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
