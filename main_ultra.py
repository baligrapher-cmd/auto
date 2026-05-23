
import sys
import os

# Tambahkan current directory ke sys.path agar bisa import module lokal
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui.ultra_window import UltraWindow

def main():
    app = QApplication(sys.argv)
    
    # Set App Icon
    icon_path = os.path.join(current_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = UltraWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
