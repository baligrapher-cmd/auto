import sys
import os
import json
import time
import re
import ctypes
import shutil
import math
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                QRadioButton, QTextEdit, QSpinBox, QFileDialog, QGroupBox, QMessageBox, QFrame, QGridLayout, QDialog, QCheckBox, QScrollArea, QLayout, QProgressBar, QStyle, QComboBox, QInputDialog, QCompleter)
from core.license import get_hwid, install_license, install_license_text, check_license, activate_license
from core.state_machine import UploadMode
from core.updater import UpdateChecker, open_download_page
from PySide6.QtCore import Qt, Signal, Slot, QDateTime, QUrl, QTimer, QEvent, QProcess, QThread
from PySide6.QtGui import QIcon, QClipboard, QFont, QDesktopServices, QTextCursor
from PySide6.QtMultimedia import QSoundEffect

AUTO_YU_VERSION = "3.0.4"
UPDATE_CHECK_URL = "https://pramana.web.id/autoyu/download/update.json"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

# ==========================================
# SETTINGS PERSISTENCE
# ==========================================
GLOBAL_SKIP_SAVE = False

def get_app_data_dir():
    if sys.platform == 'darwin':
        path = os.path.expanduser("~/Library/Application Support/AutoYuPro")
    else:
        path = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
    return path

APP_SETTINGS_DIR = get_app_data_dir()
SETTINGS_FILE = os.path.join(APP_SETTINGS_DIR, "user_settings.json")

def save_settings(config):
    if GLOBAL_SKIP_SAVE:
        return False
    try:
        os.makedirs(APP_SETTINGS_DIR, exist_ok=True)
        tmp_path = SETTINGS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(SETTINGS_FILE):
            try:
                shutil.copyfile(SETTINGS_FILE, SETTINGS_FILE + ".bak")
            except Exception:
                pass
        os.replace(tmp_path, SETTINGS_FILE)
        return True
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False

def load_settings():
    candidates = [
        SETTINGS_FILE,
        SETTINGS_FILE + ".bak",
        SETTINGS_FILE + ".tmp",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return None

# ==========================================
# LEGAL DIALOG (Terms of Service)
# ==========================================
class LegalDialog(QDialog):
    def __init__(self, parent=None, version="2.0", is_reagreement=False):
        super().__init__(parent)
        self.setWindowTitle("AutoYu Legal Agreement")
        self.setMinimumSize(600, 750)
        self.version = version
        self.is_reagreement = is_reagreement
        self.agreed = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog { background-color: #0F172A; border: 1px solid #334155; }
            QLabel { color: #F8FAFC; font-family: 'Inter', sans-serif; }
            QCheckBox { color: #CBD5E1; font-weight: 600; font-size: 14px; padding: 5px; }
            QCheckBox::indicator { width: 22px; height: 22px; border-radius: 6px; border: 2px solid #334155; background-color: #1E293B; }
            QCheckBox::indicator:checked { background-color: #4F46E5; border: 2px solid #4F46E5; }
            QScrollBar:vertical { border: none; background: #0B1220; width: 10px; border-radius: 5px; margin: 0px; }
            QScrollBar::handle:vertical { background: #334155; min-height: 30px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #4F46E5; }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # Title Section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        
        title = QLabel("AutoYu Legal Agreement")
        title.setStyleSheet("font-size: 26px; font-weight: 900; color: #FFFFFF; letter-spacing: -1.5px;")
        
        subtitle = QLabel("Terms of Service & Privacy Policy")
        subtitle.setStyleSheet("font-size: 13px; font-weight: 800; color: #818CF8; text-transform: uppercase; letter-spacing: 2px;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        if self.is_reagreement:
            sub = QLabel(f"Versi baru ({self.version}) tersedia. Harap setujui ulang untuk melanjutkan.")
            sub.setStyleSheet("background-color: rgba(239, 68, 68, 0.15); color: #FCA5A5; font-weight: 700; padding: 14px; border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 13px;")
            layout.addWidget(sub)

        # Content Area
        doc_tabs = QScrollArea()
        doc_tabs.setWidgetResizable(True)
        doc_tabs.setFrameShape(QFrame.NoFrame)
        doc_tabs.setStyleSheet("background-color: #0B1220; border: 1px solid #1E293B; border-radius: 12px;")
        
        doc_content = QWidget()
        doc_content.setStyleSheet("background-color: transparent;")
        doc_layout = QVBoxLayout(doc_content)
        doc_layout.setContentsMargins(24, 24, 24, 24)
        doc_layout.setSpacing(20)
        
        # TOS Section
        tos_header = QFrame()
        tos_header.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-radius: 8px; padding: 6px 12px;")
        tos_header_layout = QHBoxLayout(tos_header)
        tos_title = QLabel("1. SYARAT DAN KETENTUAN (TERMS OF SERVICE)")
        tos_title.setStyleSheet("font-weight: 900; color: #A5B4FC; font-size: 12px; letter-spacing: 0.5px;")
        tos_header_layout.addWidget(tos_title)
        doc_layout.addWidget(tos_header)
        
        tos_text = QTextEdit()
        tos_text.setReadOnly(True)
        tos_text.setFrameShape(QFrame.NoFrame)
        tos_text.setHtml("""
            <div style="color: #CBD5E1; font-family: 'Inter', sans-serif; line-height: 1.8; font-size: 13px;">
                <h3 style="color: #FFFFFF; margin-bottom: 8px; font-size: 16px;">AutoYu V3 – Professional Automation Engine</h3>
                <p><i>Terakhir diperbarui: 15 APRIL 2026</i></p>
                <p>Dokumen ini merupakan Perjanjian Elektronik yang sah dan mengikat sesuai dengan peraturan perundang-undangan di Republik Indonesia (UU ITE & PDP).</p>
                
                <h4 style="color: #F8FAFC; margin-top: 20px; font-size: 14px; border-bottom: 1px solid #1E293B; padding-bottom: 5px;">1. STATUS HUKUM</h4>
                <p>Persetujuan melalui tombol “SETUJU & LANJUTKAN” memiliki kekuatan hukum yang sama dengan tanda tangan basah.</p>
                
                <h4 style="color: #F8FAFC; margin-top: 20px; font-size: 14px; border-bottom: 1px solid #1E293B; padding-bottom: 5px;">2. TANGGUNG JAWAB PENGGUNA</h4>
                <p>Pengguna bertanggung jawab penuh atas akun dan konten. Pengembang tidak berafiliasi dengan platform pihak ketiga mana pun.</p>
                
                <h4 style="color: #F8FAFC; margin-top: 20px; font-size: 14px; border-bottom: 1px solid #1E293B; padding-bottom: 5px;">3. PEMBATASAN LISENSI</h4>
                <p>Lisensi bersifat terbatas, non-eksklusif, dan terikat pada satu identitas perangkat (HWID).</p>
            </div>
        """)
        tos_text.setFixedHeight(250)
        doc_layout.addWidget(tos_text)

        # Privacy Section
        priv_header = QFrame()
        priv_header.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-radius: 8px; padding: 6px 12px;")
        priv_header_layout = QHBoxLayout(priv_header)
        priv_title = QLabel("2. KEBIJAKAN PRIVASI (PRIVACY POLICY)")
        priv_title.setStyleSheet("font-weight: 900; color: #A5B4FC; font-size: 12px; letter-spacing: 0.5px;")
        priv_header_layout.addWidget(priv_title)
        doc_layout.addWidget(priv_header)
        
        priv_text = QTextEdit()
        priv_text.setReadOnly(True)
        priv_text.setFrameShape(QFrame.NoFrame)
        priv_text.setHtml("""
            <div style="color: #CBD5E1; font-family: 'Inter', sans-serif; line-height: 1.8; font-size: 13px;">
                <h3 style="color: #FFFFFF; margin-bottom: 8px; font-size: 16px;">Data & Keamanan</h3>
                <p>AutoYu <b>TIDAK</b> mengumpulkan password atau media Anda. Data yang diproses hanya terbatas pada validasi lisensi (HWID, IP, License Key).</p>
                <p>Seluruh pemrosesan data dilakukan sesuai dengan UU No. 27 Tahun 2022 tentang PDP.</p>
            </div>
        """)
        priv_text.setFixedHeight(150)
        doc_layout.addWidget(priv_text)

        doc_tabs.setWidget(doc_content)
        layout.addWidget(doc_tabs)

        # Agreement Checkbox
        self.check_agree = QCheckBox("Saya telah membaca dan menyetujui Ketentuan & Privasi (v2.0)")
        self.check_agree.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.check_agree)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.btn_cancel = QPushButton("BATAL")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(45)
        self.btn_cancel.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                color: #94A3B8; 
                border: 1px solid #334155; 
                border-radius: 8px; 
                font-weight: 700; 
            }
            QPushButton:hover { background-color: #1E293B; color: #F8FAFC; }
        """)
        
        self.btn_accept = QPushButton("SETUJU & LANJUTKAN")
        self.btn_accept.setEnabled(False)
        self.btn_accept.setCursor(Qt.PointingHandCursor)
        self.btn_accept.setFixedHeight(45)
        self.btn_accept.setStyleSheet("""
            QPushButton { 
                background-color: #4F46E5; 
                color: white; 
                border-radius: 8px; 
                font-weight: 800; 
                font-size: 14px;
            }
            QPushButton:disabled { background-color: #1E293B; color: #475569; border: 1px solid #334155; }
            QPushButton:hover { background-color: #6366F1; }
        """)
        
        btn_layout.addWidget(self.btn_cancel, 1)
        btn_layout.addWidget(self.btn_accept, 2)
        layout.addLayout(btn_layout)

        # Connect signals
        self.check_agree.stateChanged.connect(lambda state: self.btn_accept.setEnabled(state == 2))
        self.btn_accept.clicked.connect(self.accept_legal)
        self.btn_cancel.clicked.connect(self.reject)

    def accept_legal(self):
        self.agreed = True
        self.accept()

# ==========================================
# DRAG & DROP LINE EDIT
# ==========================================
class DragDropLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("class", "drag_drop_input")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.setStyleSheet("border: 2px dashed #6366F1; background-color: #1E293B;")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            
            urls = event.mimeData().urls()
            if urls:
                # Ambil path dan bersihkan dari karakter aneh (terutama di Windows/Mac)
                file_path = urls[0].toLocalFile()
                
                # Normalisasi path universal
                file_path = os.path.normpath(file_path)
                
                # Normalisasi path untuk Windows (hilangkan prefix / jika ada di awal drive letter)
                if os.name == 'nt' and file_path.startswith('/') and len(file_path) > 2 and file_path[2] == ':':
                    file_path = file_path[1:]
                
                if os.path.isdir(file_path):
                    self.setText(file_path)
                    # Trigger manual signal because sometimes setText doesn't trigger it in some environments
                    self.textChanged.emit(file_path)
                else:
                    # Accessing main window via parent if possible, otherwise use global style
                    # Since this is likely inside a custom QLineEdit, we try to use its parent
                    try:
                        self.window().show_custom_message("Folder Saja", "Silakan drag & drop folder saja!", "warning")
                    except:
                        QMessageBox.warning(self, "Folder Saja", "Silakan drag & drop folder saja!")
        else:
            event.ignore()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel:
            if isinstance(source, QSpinBox):
                return True # Block wheel scroll
        return super().eventFilter(source, event)

# ==========================================
# FOTOYU DESIGN SYSTEM (Clean & Purple)
# ==========================================
FOTOYU_STYLESHEET = """
QMainWindow {
    background-color: #0F172A;
}
QScrollArea {
    border: none;
    background-color: #0F172A;
}
QWidget#scroll_content {
    background-color: #0F172A;
}
QWidget {
    font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif;
    font-size: 15px;
    color: #E2E8F0;
}

/* FIX VISIBILITAS DIALOG DI LIGHT MODE */
QDialog, QMessageBox, QInputDialog {
    background-color: #0F172A;
    color: #E2E8F0;
}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #E2E8F0;
}
QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    background-color: #1E293B;
    color: #FFFFFF;
    border: 1px solid #334155;
    padding: 6px 12px;
    border-radius: 6px;
    min-width: 80px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
    background-color: #334155;
    border-color: #4F46E5;
}

QToolTip {
    background-color: #1E293B;
    color: #FFFFFF;
    border: 1px solid #6366F1;
    padding: 8px;
    border-radius: 6px;
    font-weight: 500;
}

/* HEADER */
QFrame#header_panel {
    background-color: #0B1220;
    border-bottom: 1px solid #1E293B;
    max-height: 50px;
    min-height: 50px;
}
QLabel[class="header_logo"] {
    font-size: 18px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -1px;
}
QLabel[class="header_subtitle"] {
    font-size: 12px;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel[class="license_badge_pro"] {
    color: #94A3B8;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
    border: none;
    padding: 0px;
}

/* CARD STYLE */
QFrame[class="card"] {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
}

QLabel[class="card_title"] {
    font-size: 13px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
}

/* INPUT LABELS */
QLabel[class="field_label"] {
    font-size: 14px;
    font-weight: 700;
    color: #E2E8F0;
}

/* PILL / TILE CONTROL */
QRadioButton {
    spacing: 6px;
    color: #CBD5E1;
    font-weight: 600;
}
QRadioButton::indicator {
    width: 12px;
    height: 12px;
    border-radius: 6px;
    border: 1px solid #334155;
}
QRadioButton::indicator:checked {
    background-color: #4F46E5;
    border: 2px solid #1E293B;
}
QRadioButton[class="pill_pro"] {
    padding: 6px 14px;
    border-radius: 8px;
    background-color: #0F172A;
    border: 1px solid #334155;
    color: #CBD5E1;
    font-weight: 700;
    text-align: center;
    min-height: 14px;
}
QRadioButton[class="pill_pro"]:hover {
    border-color: #4F46E5;
}
QRadioButton[class="pill_pro"]:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
    color: #FFFFFF;
    border: none;
}

/* INPUT FIELDS */
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #0B1220;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-weight: 500;
}

/* Fix for QSpinBox internal alignment and background */
QSpinBox::up-button, QSpinBox::down-button {
    width: 0px;
    border: none;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #6366F1;
    background-color: #0F172A;
}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background-color: #0B1220;
    color: #475569;
    border: 1px solid #1E293B;
}

QSpinBox {
    selection-background-color: #4F46E5;
}


QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: url(none);
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6366F1;
    width: 0;
    height: 0;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid #334155;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
    color: #E2E8F0;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1E293B;
    border-left: 1px solid #334155;
    width: 20px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #334155;
}
QSpinBox::up-arrow {
    image: url(none); /* Fallback to text arrows */
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 5px solid #94A3B8;
    width: 0;
    height: 0;
}
QSpinBox::down-arrow {
    image: url(none);
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #94A3B8;
    width: 0;
    height: 0;
}

/* BUTTONS */
QPushButton {
    font-weight: 700;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton[class="primary_pro"] {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
    color: #FFFFFF;
    border: none;
    font-size: 15px;
}
QPushButton[class="primary_pro"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338CA, stop:1 #6D28D9);
}
QPushButton[class="primary"] {
    background-color: #0F172A;
    color: #FFFFFF;
    border: 2px dashed #4F46E5;
    border-radius: 8px;
    padding: 10px;
    font-weight: 800;
}
QPushButton[class="primary"]:hover {
    background-color: #1E293B;
    border-color: #818CF8;
}
QPushButton[class="danger_pro"] {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
}
QPushButton[class="danger_pro"]:hover {
    background-color: #B91C1C;
}
QPushButton[class="secondary_pro"] {
    background-color: #1E293B;
    border: 1px solid #334155;
    color: #E2E8F0;
}
QPushButton[class="secondary_pro"]:hover {
    background-color: #2D3748;
    border-color: #4F46E5;
}
QPushButton[class="retry_dashed"] {
    background-color: rgba(239, 68, 68, 0.06);
    color: #EF4444;
    border: 2px dashed #EF4444;
}
QPushButton[class="retry_dashed"]:hover {
    background-color: rgba(239, 68, 68, 0.12);
}
QPushButton[class="retry_dashed"]:disabled {
    background-color: rgba(148, 163, 184, 0.06);
    color: #64748B;
    border: 2px dashed #64748B;
}

/* UPDATE NOTIFICATION */
QFrame#update_notif {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
    border-radius: 10px;
    margin: 4px 12px;
}
QLabel#update_label {
    color: #FFFFFF;
    font-weight: 800;
    font-size: 13px;
    padding: 8px 12px;
}
QPushButton#update_btn {
    background-color: #FFFFFF;
    color: #4F46E5;
    font-weight: 900;
    font-size: 12px;
    border-radius: 6px;
    padding: 4px 12px;
    margin: 6px 12px;
}
QPushButton#update_btn:hover {
    background-color: #F8FAFC;
}

/* LOG PANEL */
QTextEdit[class="log_pro"] {
    background-color: #0B1220;
    color: #94A3B8;
    border: 1px solid #1E293B;
    border-radius: 8px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 14px;
    padding: 8px;
}

/* STATUS BAR */
QFrame#status_bar {
    background-color: #0B1220;
    border-top: 1px solid #1E293B;
    max-height: 28px;
    min-height: 28px;
}

/* FOOTER PANEL (Action Buttons) */
QFrame#footer_panel {
    background-color: #0B1220;
    border-top: 1px solid #1E293B;
    padding: 12px 16px;
}

/* DIALOGS & INPUT DIALOG */
QInputDialog {
    background-color: #0F172A;
}
QInputDialog QLabel {
    color: #F8FAFC;
    font-weight: 700;
}
QInputDialog QLineEdit {
    background-color: #0B1220;
    color: #FFFFFF;
    border: 1px solid #4F46E5;
    padding: 10px;
    border-radius: 6px;
}
QInputDialog QPushButton {
    background-color: #1E293B;
    color: #FFFFFF;
    border: 1px solid #334155;
    min-width: 80px;
    padding: 6px;
}
QInputDialog QPushButton:hover {
    background-color: #4F46E5;
}
"""
"""
QLabel[class="status_label"] {
    font-size: 14px;
    font-weight: 600;
    color: #475569;
}
QLabel[class="status_value"] {
    font-size: 14px;
    font-weight: 700;
    color: #94A3B8;
}

/* CHECKBOX */
QCheckBox {
    spacing: 12px;
    color: #CBD5E1;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 1px solid #334155;
    background-color: #0F172A;
}
QCheckBox::indicator:checked {
    background-color: #4F46E5;
    border: 1px solid #4F46E5;
}
"""

class LicenseDialog(QDialog):
    def __init__(self, parent=None, app_type="pro"):
        super().__init__(parent)
        self.app_type = app_type
        self.setWindowTitle(f"AutoYu V3 {'LITE' if app_type == 'lite' else 'PRO'} - License Management")
        self.setFixedSize(480, 720)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog { background-color: #0F172A; border: 1px solid #334155; }
            QLabel { color: #F8FAFC; font-family: 'Inter', -apple-system, sans-serif; }
            QLabel[class="status_active"] { color: #10B981; font-weight: 900; font-size: 20px; }
            QLabel[class="status_inactive"] { color: #F43F5E; font-weight: 900; font-size: 20px; }
            QLabel[class="status_desc"] { color: #CBD5E1; font-size: 13px; line-height: 1.4; font-weight: 500; }
            QLabel[class="footer_pro"] { color: #64748B; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; }
            QLabel[class="dialog_header"] { font-size: 24px; font-weight: 900; color: #FFFFFF; letter-spacing: -1px; }
            QFrame[class="card"] { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; }
            QLabel[class="card_title"] { font-size: 11px; font-weight: 900; color: #818CF8; text-transform: uppercase; letter-spacing: 1.2px; }
            QLineEdit { background-color: #0B1220; border: 1px solid #334155; border-radius: 8px; color: #FFFFFF; selection-background-color: #4F46E5; padding: 10px; }
            QLineEdit:focus { border-color: #4F46E5; background-color: #0F172A; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(35, 35, 35, 35)
        
        # 1. Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        header = QLabel("License Management")
        header.setProperty("class", "dialog_header")
        header_sub = QLabel("Professional Automation Engine V3")
        header_sub.setStyleSheet("color: #6366F1; font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;")
        header_layout.addWidget(header)
        header_layout.addWidget(header_sub)
        layout.addLayout(header_layout)
        
        # 2. Status Card
        status_card = QFrame()
        status_card.setProperty("class", "card")
        sc_layout = QHBoxLayout(status_card)
        sc_layout.setContentsMargins(20, 20, 20, 20)
        
        self.status_icon = QLabel("●")
        f = self.status_icon.font()
        f.setPointSize(28)
        self.status_icon.setFont(f)
        
        sc_text_layout = QVBoxLayout()
        sc_text_layout.setSpacing(4)
        self.status_title = QLabel("MEMVERIFIKASI...")
        self.status_title.setStyleSheet("font-size: 16px; font-weight: 900; color: #FFFFFF;")
        self.status_desc = QLabel("Harap tunggu sebentar sementara sistem memverifikasi lisensi perangkat Anda.")
        self.status_desc.setProperty("class", "status_desc")
        self.status_desc.setWordWrap(True)
        
        sc_text_layout.addWidget(self.status_title)
        sc_text_layout.addWidget(self.status_desc)
        
        sc_layout.addWidget(self.status_icon)
        sc_layout.addSpacing(15)
        sc_layout.addLayout(sc_text_layout)
        sc_layout.addStretch()
        
        layout.addWidget(status_card)
        
        # 4. Activation Card
        act_card = QFrame()
        act_card.setProperty("class", "card")
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(20, 20, 20, 20)
        act_layout.setSpacing(15)
        
        act_title = QLabel("AKTIVASI ONLINE")
        act_title.setProperty("class", "card_title")
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.license_input.setAlignment(Qt.AlignCenter)
        self.license_input.setStyleSheet("font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 14px; font-weight: 800;")
        self.license_input.setFixedHeight(45)
        
        self.btn_activate = QPushButton("AKTIFKAN SEKARANG")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setFixedHeight(48)
        self.btn_activate.setStyleSheet("""
            QPushButton { 
                background-color: #4F46E5; 
                color: white; 
                border-radius: 8px; 
                font-weight: 900; 
                font-size: 14px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover { background-color: #6366F1; }
            QPushButton:pressed { background-color: #4338CA; }
            QPushButton:disabled { background-color: #1E293B; color: #475569; }
        """)
        self.btn_activate.clicked.connect(self.do_activation)
        
        act_desc = QLabel("Lisensi akan diverifikasi secara online dan dikunci pada ID perangkat (HWID) Anda.")
        act_desc.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 600; line-height: 1.4;")
        act_desc.setWordWrap(True)
        act_desc.setAlignment(Qt.AlignCenter)
        
        act_layout.addWidget(act_title)
        act_layout.addWidget(self.license_input)
        act_layout.addWidget(self.btn_activate)
        act_layout.addWidget(act_desc)

        # HWID Display
        hwid_container = QHBoxLayout()
        hwid_container.setSpacing(5)
        self.hwid_label = QLabel(f"ID: {get_hwid()[:12]}...")
        self.hwid_label.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 700; font-family: monospace;")
        self.btn_copy_hwid = QPushButton("Salin ID")
        self.btn_copy_hwid.setCursor(Qt.PointingHandCursor)
        self.btn_copy_hwid.setFixedSize(60, 22)
        self.btn_copy_hwid.setStyleSheet("""
            QPushButton { 
                background-color: #1E293B; 
                color: #818CF8; 
                border: 1px solid #334155; 
                border-radius: 4px; 
                font-size: 9px; 
                font-weight: 800;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_copy_hwid.clicked.connect(self.copy_hwid)
        hwid_container.addStretch()
        hwid_container.addWidget(self.hwid_label)
        hwid_container.addWidget(self.btn_copy_hwid)
        hwid_container.addStretch()
        act_layout.addLayout(hwid_container)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("background-color: #334155; max-height: 1px;")
        act_layout.addWidget(line)

        # Danger Zone: Reset/Uninstall
        danger_title = QLabel("DANGER ZONE")
        danger_title.setStyleSheet("color: #F43F5E; font-weight: 900; font-size: 10px; letter-spacing: 1px;")
        act_layout.addWidget(danger_title)

        self.btn_reset = QPushButton("CLEAN SYSTEM / RESET SETTINGS")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedHeight(40)
        self.btn_reset.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                color: #F43F5E; 
                border: 1px dashed #F43F5E; 
                border-radius: 6px; 
                font-weight: 800; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(244, 63, 94, 0.1); }
            QPushButton:pressed { background-color: rgba(244, 63, 94, 0.2); }
        """)
        self.btn_reset.clicked.connect(self.do_reset_system)
        act_layout.addWidget(self.btn_reset)

        layout.addWidget(act_card)
        
        # 5. Feedback
        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setAlignment(Qt.AlignCenter)
        self.feedback_lbl.setWordWrap(True)
        self.feedback_lbl.setStyleSheet("font-weight: 800; font-size: 12px; color: #F87171;")
        layout.addWidget(self.feedback_lbl)
        
        layout.addStretch()
        
        # 6. Footer
        copyright = QLabel("AutoYu V3 © 2026 ENTERPRISE EDITION")
        copyright.setAlignment(Qt.AlignCenter)
        copyright.setProperty("class", "footer_pro")
        layout.addWidget(copyright)
        
        # Check initial status
        self.refresh_status()

    def refresh_status(self):
        is_valid, status_code, cust_name, res_data = check_license(force=True, app_type=self.app_type)
        if is_valid:
            self.status_icon.setStyleSheet("color: #10B981") # Emerald Green
            self.status_title.setText("LISENSI AKTIF")
            self.status_title.setProperty("class", "status_active")
            
            display_name = cust_name if cust_name else "User"
            expiry = res_data.get('expiry', 'Lifetime')
            self.status_desc.setText(f"Licensed to: {display_name}\nExpiry: {expiry}\nStatus: Aktif & Online")
            
            self.btn_activate.setEnabled(False)
            self.btn_activate.setText("SUDAH TERAKTIVASI")
            self.btn_activate.setStyleSheet("background-color: #10B981; color: white; border: none; font-weight: 900; font-size: 15px;")
            self.license_input.setEnabled(False)
        elif status_code == "REAGREEMENT_REQUIRED":
            self.status_icon.setStyleSheet("color: #F59E0B") # Amber
            self.status_title.setText("UPDATE DIPERLUKAN")
            self.status_title.setStyleSheet("color: #F59E0B; font-weight: 900; font-size: 20px;")
            
            self.status_desc.setText("Ketentuan Layanan telah diperbarui. Harap aktifkan ulang untuk menyetujui.")
            self.btn_activate.setEnabled(True)
            self.btn_activate.setText("UPDATE PERSETUJUAN")
            self.btn_activate.setProperty("class", "primary_pro")
            self.license_input.setEnabled(True)
        else:
            self.status_icon.setStyleSheet("color: #F43F5E") # Rose Red
            self.status_title.setText("BELUM AKTIF")
            self.status_title.setProperty("class", "status_inactive")
            
            # More descriptive error messages
            if status_code == "LICENSE_EXPIRED":
                self.status_desc.setText("Lisensi Anda telah kadaluarsa.")
            elif status_code == "LICENSE_DISABLED":
                self.status_desc.setText("Lisensi dinonaktifkan oleh admin.")
            elif "CONNECTION_FAILED" in status_code:
                self.status_desc.setText(f"Gagal verifikasi (Koneksi bermasalah).\n{status_code}")
            elif "SERVER_CONNECTION_ERROR" in status_code:
                self.status_desc.setText(f"Server merespon dengan error.\n{status_code}")
            elif "perangkat lain" in str(status_code).lower():
                self.status_desc.setText("Lisensi terkunci di perangkat lain.\nHubungi admin & sertakan ID perangkat Anda.")
            else:
                self.status_desc.setText("Aplikasi belum diaktifkan.")
                
            self.btn_activate.setEnabled(True)
            self.btn_activate.setText("AKTIFKAN SEKARANG")
            self.btn_activate.setProperty("class", "primary")
            self.license_input.setEnabled(True)
            
        # Refresh style
        self.status_title.style().unpolish(self.status_title)
        self.status_title.style().polish(self.status_title)
        self.btn_activate.style().unpolish(self.btn_activate)
        self.btn_activate.style().polish(self.btn_activate)

    def copy_hwid(self):
        hwid = get_hwid()
        QApplication.clipboard().setText(hwid)
        self.btn_copy_hwid.setText("TERSALIN!")
        QTimer.singleShot(2000, lambda: self.btn_copy_hwid.setText("Salin ID"))

    def do_activation(self):
        key = self.license_input.text().strip()
        if not key:
            self.feedback_lbl.setText("❌ Masukkan License Key!")
            self.feedback_lbl.setStyleSheet("color: #EF4444")
            return
            
        # 1. Show Legal Dialog first
        is_reagreement = "UPDATE" in self.btn_activate.text()
        legal = LegalDialog(self, is_reagreement=is_reagreement)
        if not legal.exec():
            self.feedback_lbl.setText("❌ Aktivasi dibatalkan: Persetujuan diperlukan.")
            self.feedback_lbl.setStyleSheet("color: #EF4444")
            return

        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("Memverifikasi...")
        QApplication.processEvents()
        
        success, msg, res_data = activate_license(key, agreed=True, agreement_version="2.0", app_type=self.app_type)
        
        if success:
            self.feedback_lbl.setText(f"✅ {msg}")
            self.feedback_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
            self.refresh_status()
            # Update main window display if it exists
            if self.parent():
                # Check if parent is MainWindow
                if hasattr(self.parent(), "update_license_display"):
                    self.parent().update_license_display()
                # Also check if parent of parent is MainWindow (if nested in layouts)
                elif hasattr(self.parent().parent(), "update_license_display"):
                    self.parent().parent().update_license_display()
        else:
            self.feedback_lbl.setText(f"❌ {msg}")
            self.feedback_lbl.setStyleSheet("color: #EF4444")
            self.btn_activate.setEnabled(True)
            self.btn_activate.setText("AKTIFKAN SEKARANG")

    def do_reset_system(self):
        """Clean all user settings and data trackers to resolve update conflicts"""
        reply = QMessageBox.question(
            self, 
            "Konfirmasi Clean System",
            "Apakah Anda yakin ingin membersihkan sistem?\n\n"
            "Tindakan ini akan:\n"
            "1. Menghapus semua pengaturan akun.\n"
            "2. Menghapus riwayat unggahan (trackers).\n"
            "3. Mereset lisensi dari aplikasi ini.\n\n"
            "Gunakan ini jika aplikasi error setelah update.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            global GLOBAL_SKIP_SAVE
            GLOBAL_SKIP_SAVE = True
            self._skip_save = True
            
            # Stop engine if running
            if hasattr(self, 'on_stop'):
                try:
                    self.on_stop()
                except:
                    pass

            try:
                import stat
                def on_rm_error(func, path, exc_info):
                    os.chmod(path, stat.S_IWRITE)
                    try:
                        func(path)
                    except:
                        pass

                # 1. Clean App Data Dir (AppData)
                app_data = get_app_data_dir()
                if os.path.exists(app_data):
                    shutil.rmtree(app_data, onerror=on_rm_error)
                
                # 2. Clean Local Legacy Files (CWD)
                legacy_files = [
                    "user_settings.json", "user_settings.json.bak", "user_settings.json.tmp",
                    ".upload_tracker.json", ".upload_tracker.json.bak"
                ]
                for f in legacy_files:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
                
                # 3. Clear UI state to prevent any accidental saves from memory
                if hasattr(self, 'account_combo'):
                    self.account_combo.blockSignals(True)
                    self.account_combo.clear()
                    self.account_combo.blockSignals(False)
                
                if hasattr(self, 'status_account'):
                    self.status_account.setText("Sistem Direset")
                
                # 4. Clear internal settings cache if any
                if hasattr(self, 'apply_saved_settings'):
                    # Force update UI to empty state
                    self.status_account.setText("Belum ada akun")
                    self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;")

                # 5. Re-create base dir
                os.makedirs(app_data, exist_ok=True)
                
                QMessageBox.information(
                    self, 
                    "Selesai", 
                    "Sistem telah dibersihkan.\n\nAplikasi akan ditutup. Silakan buka kembali untuk memulai dari awal.",
                    QMessageBox.Ok
                )
                QApplication.quit()
            except Exception as e:
                GLOBAL_SKIP_SAVE = False
                self._skip_save = False
                QMessageBox.critical(self, "Error", f"Gagal membersihkan sistem: {e}")

# ==========================================
# ADD ACCOUNT DIALOG (Custom Dark Theme)
# ==========================================
class AddAccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Akun Baru")
        self.setFixedSize(400, 220)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog { 
                background-color: #0F172A; 
                border: 1px solid #4F46E5; 
                border-radius: 12px;
            }
            QLabel { 
                color: #F8FAFC; 
                font-family: 'Inter', sans-serif; 
                font-size: 14px; 
                font-weight: 700;
            }
            QLineEdit { 
                background-color: #0B1220; 
                border: 2px solid #334155; 
                border-radius: 8px; 
                color: #FFFFFF; 
                padding: 12px; 
                font-size: 15px;
            }
            QLineEdit:focus { 
                border-color: #6366F1; 
                background-color: #0F172A; 
            }
            QPushButton { 
                border-radius: 8px; 
                font-weight: 800; 
                font-size: 13px; 
                padding: 10px;
            }
            QPushButton#btn_ok { 
                background-color: #4F46E5; 
                color: white; 
            }
            QPushButton#btn_ok:hover { 
                background-color: #6366F1; 
            }
            QPushButton#btn_cancel { 
                background-color: transparent; 
                color: #94A3B8; 
                border: 1px solid #334155; 
            }
            QPushButton:hover#btn_cancel { 
                background-color: #1E293B; 
                color: #F8FAFC; 
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        lbl = QLabel("Masukkan Nama Akun:")
        layout.addWidget(lbl)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Contoh: Fotografer_Bali")
        layout.addWidget(self.name_input)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("BATAL")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QPushButton("OK, LANJUT LOGIN")
        self.btn_ok.setObjectName("btn_ok")
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        self.btn_ok.clicked.connect(self.handle_accept)
        
        btn_layout.addWidget(self.btn_cancel, 1)
        btn_layout.addWidget(self.btn_ok, 2)
        layout.addLayout(btn_layout)
        
        self.account_name = ""

    def handle_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Nama akun tidak boleh kosong!")
            return
        self.account_name = name
        self.accept()


class LiveLocationSearchThread(QThread):
    finished_signal = Signal(bool, str, object, str)  # success, keyword, results, message

    def __init__(self, profile_path, keyword, limit=100, max_retries=2):
        super().__init__()
        self.profile_path = profile_path
        self.keyword = keyword
        self.limit = limit
        self.max_retries = max_retries

    def run(self):
        try:
            import asyncio
            from FotoTree_Tools.sync_locations import search_fototrees_live

            # Persistent search: Coba beberapa kali jika gagal
            final_result = {"success": False, "results": [], "message": "Memulai pencarian..."}
            
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    print(f"[LiveSearch] Retry attempt {attempt} for: {self.keyword}")
                
                result = asyncio.run(search_fototrees_live(self.profile_path, self.keyword, self.limit))
                if isinstance(result, dict) and result.get("success") and result.get("results"):
                    final_result = result
                    break
                else:
                    final_result = result if isinstance(result, dict) else final_result
                    if attempt < self.max_retries:
                        time.sleep(1.5) # Jeda antar retry

            self.finished_signal.emit(
                bool(final_result.get("success")),
                self.keyword,
                final_result.get("results", []) or [],
                str(final_result.get("message", ""))
            )
        except Exception as e:
            self.finished_signal.emit(False, self.keyword, [], str(e))

class UpdateCheckThread(QThread):
    update_available_signal = Signal(dict) # data JSON dari server

    def run(self):
        try:
            # Gunakan timeout agar tidak gantung jika server down
            response = requests.get(UPDATE_CHECK_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version", "0.0.0")
                
                # Bandingkan versi (sederhana: string comparison atau bisa lebih kompleks)
                if latest_version > AUTO_YU_VERSION:
                    self.update_available_signal.emit(data)
        except Exception as e:
            print(f"[UpdateCheck] Error: {e}")

class MainWindow(QMainWindow):
    start_signal = Signal(dict)
    stop_signal = Signal()
    continue_signal = Signal()
    new_photo_detected_signal = Signal(int) # Number of new photos detected

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoYu V3 - Upload Assitant")
        
        # Set Window Icon robustly
        icon_path = "icon.ico"
        if not os.path.exists(icon_path):
            # Try PyInstaller path
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, "icon.ico")
            else:
                # Try relative to this file
                icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Fix taskbar icon on Windows
        if sys.platform == 'win32':
            try:
                import ctypes
                myappid = 'pramana.autoyu.v3.pro' # unique string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.setMinimumSize(1150, 740)
        self.resize(1150, 740)
        self.setStyleSheet(FOTOYU_STYLESHEET)
        self.is_login_only = False
        self.app_type = "pro"
        self.last_mode = "foto" # Untuk mengingat mode sebelumnya saat switch settings
        self._skip_save = False
        self._last_loaded_folder = None
        
        # macOS Permission Trigger: Try to touch folder to trigger OS popup
        self._macos_permission_triggered = False
        
        # Central Widget & Main Outer Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_outer_layout = QVBoxLayout(central_widget)
        self.main_outer_layout.setContentsMargins(0, 0, 0, 0)
        self.main_outer_layout.setSpacing(0)

        # 1. HEADER PANEL (Fixed at Top)
        header_panel = QFrame()
        header_panel.setObjectName("header_panel")
        header_layout = QHBoxLayout(header_panel)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(0)
        brand_layout.setAlignment(Qt.AlignVCenter)
        header_logo = QLabel(f"AutoYu V3 (v{AUTO_YU_VERSION})")
        header_logo.setProperty("class", "header_logo")
        header_logo.setStyleSheet("font-size: 18px;")
        header_subtitle = QLabel("Fotoyu Upload assistant by pramana")
        header_subtitle.setProperty("class", "header_subtitle")
        header_subtitle.setStyleSheet("font-size: 10px;")
        brand_layout.addWidget(header_logo)
        brand_layout.addWidget(header_subtitle)
        
        # License Info
        self.license_badge = QLabel("Memverifikasi Lisensi...")
        self.license_badge.setProperty("class", "license_badge_pro")
        self.license_badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Icon Kunci Lisensi
        self.license_icon = QPushButton("🔑")
        self.license_icon.setFixedSize(24, 24)
        self.license_icon.setCursor(Qt.PointingHandCursor)
        self.license_icon.setToolTip("Klik untuk manajemen lisensi / impor lisensi code")
        self.license_icon.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 0px;
                margin-right: 5px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-radius: 12px;
            }
        """)
        self.license_icon.clicked.connect(self.show_license_info)
        
        # Link Panduan
        self.guide_btn = QPushButton("📖 Panduan")
        self.guide_btn.setCursor(Qt.PointingHandCursor)
        self.guide_btn.setToolTip("Klik untuk membuka panduan penggunaan AutoYu")
        self.guide_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                border: 1px solid #1E293B; 
                border-radius: 6px; 
                color: #94A3B8; 
                font-weight: 800; 
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1E293B; color: #FFFFFF; border-color: #4F46E5; }
        """)
        self.guide_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://pramana.web.id/autoyu/panduan/")))

        # WhatsApp Support Button
        self.wa_btn = QPushButton("💬 SUPPORT")
        self.wa_btn.setCursor(Qt.PointingHandCursor)
        self.wa_btn.setToolTip("Hubungi Admin via WhatsApp")
        self.wa_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                border: 1px solid #16A34A; 
                border-radius: 6px; 
                color: #22C55E; 
                font-weight: 800; 
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #14532D; color: #FFFFFF; border-color: #4ADE80; }
        """)
        self.wa_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://wa.me/6287739623456")))

        license_container = QHBoxLayout() # Ubah ke Horizontal agar ikon di samping badge
        license_container.setSpacing(8)
        license_container.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        license_container.addWidget(self.wa_btn)
        license_container.addWidget(self.guide_btn)
        license_container.addWidget(self.license_icon)
        license_container.addWidget(self.license_badge)
        
        header_layout.addLayout(brand_layout)
        header_layout.addStretch()
        header_layout.addLayout(license_container)
        
        self.main_outer_layout.addWidget(header_panel)
        
        # Initial License Check
        self.update_license_display()
        
        # Initial Update Check
        QTimer.singleShot(2000, self.check_for_updates)

        # Update Notification Frame (Hidden by default)
        self.update_frame = QFrame()
        self.update_frame.setObjectName("update_notif")
        self.update_frame.setVisible(False)
        update_notif_layout = QHBoxLayout(self.update_frame)
        update_notif_layout.setContentsMargins(12, 0, 12, 0)
        
        self.update_label = QLabel("🚀 Versi baru tersedia!")
        self.update_label.setObjectName("update_label")
        
        self.update_btn = QPushButton("UPDATE SEKARANG")
        self.update_btn.setObjectName("update_btn")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(lambda: open_download_page(getattr(self, 'latest_update_url', None)))
        
        update_notif_layout.addWidget(self.update_label)
        update_notif_layout.addStretch()
        update_notif_layout.addWidget(self.update_btn)
        
        self.main_outer_layout.addWidget(self.update_frame)

        # 2. SCROLL AREA (Middle)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.viewport().setFocusPolicy(Qt.NoFocus)
        self.main_outer_layout.addWidget(self.scroll_area)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        self.scroll_area.setWidget(scroll_content)
        
        # Main Layout (Vertical inside Scroll)
        self.main_v_layout = QVBoxLayout(scroll_content)
        self.main_v_layout.setContentsMargins(0, 0, 0, 0)
        self.main_v_layout.setSpacing(0)
        
        # 3. SAFE ZONE CONTAINER (Centered, Max Width)
        self.safe_zone = QWidget()
        self.safe_zone_layout = QHBoxLayout(self.safe_zone)
        self.safe_zone_layout.setContentsMargins(0, 0, 0, 0)
        
        # Reduced side stretches to make it wider
        self.safe_zone_layout.addStretch(1)
        
        self.content_container = QWidget()
        self.content_container.setMinimumWidth(800)
        self.content_container.setMaximumWidth(1200)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(16, 8, 16, 8)
        self.content_layout.setSpacing(10)
        
        self.safe_zone_layout.addWidget(self.content_container, 20)
        self.safe_zone_layout.addStretch(1)
        
        self.main_v_layout.addWidget(self.safe_zone)

        # 4. MODALITAS ENGINE (Hidden)
        self.radio_safe = QRadioButton("SAFE")
        self.radio_turbo = QRadioButton("TURBO")
        self.radio_safe.setChecked(True)
        self.radio_turbo.setVisible(False)
        self.radio_turbo.setEnabled(False)
        
        self.radio_safe.toggled.connect(lambda checked: self.update_mode_label("SAFE", "#818CF8") if checked else None)
        self.radio_turbo.toggled.connect(lambda checked: self.update_mode_label("TURBO", "#818CF8") if checked else None)
        
        # Helper label for logic compatibility
        self.engine_helper = QLabel() 

        # 5. MODE UNGGAHAN (Compact)
        upload_card = QFrame()
        upload_card.setProperty("class", "card")
        upload_layout = QVBoxLayout(upload_card)
        upload_layout.setContentsMargins(20, 12, 20, 12)
        upload_layout.setSpacing(8)
        
        upload_header = QHBoxLayout()
        upload_title = QLabel("MODE UNGGAHAN")
        upload_title.setProperty("class", "card_title")
        upload_header.addWidget(upload_title)
        upload_header.addStretch()
        
        # Helper Info for Upload Mode
        self.upload_helper = QLabel("📸 Pilih tipe konten")
        self.upload_helper.setStyleSheet("color: #94A3B8; font-size: 14px; font-style: italic;")
        upload_header.addWidget(self.upload_helper)
        upload_layout.addLayout(upload_header)
        
        upload_group = QHBoxLayout()
        upload_group.setSpacing(10)
        
        self.radio_foto = QRadioButton(" 📷 FOTO")
        self.radio_foto.setChecked(True)
        
        self.radio_video = QRadioButton(" 🎥 VIDEO")
        
        for rb in [self.radio_foto, self.radio_video]:
            rb.setProperty("class", "pill_pro")
            rb.setCursor(Qt.PointingHandCursor)
            rb.setFocusPolicy(Qt.NoFocus)
            rb.toggled.connect(self.update_file_count)
            upload_group.addWidget(rb)
            
        upload_layout.addLayout(upload_group)
        
        self.content_layout.addWidget(upload_card)

        # 6. KONFIGURASI (Compact)
        config_card = QFrame()
        config_card.setProperty("class", "card")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(20, 12, 20, 12)
        config_layout.setSpacing(12)
        
        config_title = QLabel("KONFIGURASI SISTEM")
        config_title.setProperty("class", "card_title")
        config_layout.addWidget(config_title)
        
        # Initialize Auto Calc Checkbox early to avoid race conditions in signals
        self.chk_auto_calc = QCheckBox("Mode Auto")
        self.chk_auto_calc.setProperty("class", "pill_pro")
        self.chk_auto_calc.setToolTip("Otomatis tentukan jumlah TAB dan foto berdasarkan isi folder")
        self.chk_auto_calc.setChecked(True)
        self.chk_auto_calc.setFocusPolicy(Qt.NoFocus)
        self.chk_auto_calc.toggled.connect(self.toggle_auto_calc)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(1, 1)
        
        def add_form_row(label_text, widget_or_layout, row_idx):
            lbl = QLabel(label_text)
            lbl.setProperty("class", "field_label")
            grid.addWidget(lbl, row_idx, 0, Qt.AlignVCenter)
            if isinstance(widget_or_layout, QLayout):
                grid.addLayout(widget_or_layout, row_idx, 1)
            else:
                grid.addWidget(widget_or_layout, row_idx, 1)

        # Folder
        folder_main_layout = QVBoxLayout() # Gunakan Vertical agar rapi
        folder_main_layout.setSpacing(10)

        # Baris 1: Pilihan Sumber
        source_row = QHBoxLayout()
        source_row.setSpacing(15)
        self.radio_src_folder = QRadioButton("📁 Folder Lokal (Komputer)")
        self.radio_src_sd = QRadioButton("🔌 Kartu SD / USB / Flashdisk")
        self.radio_src_folder.setChecked(True)
        source_row.addWidget(self.radio_src_folder)
        source_row.addWidget(self.radio_src_sd)
        source_row.addStretch()
        folder_main_layout.addLayout(source_row)

        # Baris 2: Dropdown Logika (Dinonaktifkan - Selalu Mode Full)
        self.sd_logic_container = QWidget()
        self.sd_logic_container.setVisible(False)
        folder_main_layout.addWidget(self.sd_logic_container)

        # Baris 3: Input Path & Tombol Telusuri
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_input = DragDropLineEdit()
        self.path_input.setMinimumHeight(35)
        self.path_input.textChanged.connect(self.update_file_count)
        
        self.browse_btn = QPushButton("Pilih Folder / Drive")
        self.browse_btn.setProperty("class", "secondary_pro")
        self.browse_btn.setFixedHeight(35)
        self.browse_btn.clicked.connect(self.browse_folder)
        
        # Tombol Mulai Ulang (Reset Tracker) - Solusi "Sat Set" untuk masalah upload macet
        self.reset_tracker_btn = QPushButton("Mulai Ulang Folder Ini")
        self.reset_tracker_btn.setProperty("class", "danger_pro") 
        self.reset_tracker_btn.setToolTip("Gunakan jika Anda ragu / lanjutkan sisa gagal/ server bermasalah. Aplikasi akan upload ulang semua file")
        self.reset_tracker_btn.setFixedHeight(35)
        self.reset_tracker_btn.clicked.connect(self.reset_folder_tracker)
        
        self.file_count_label = QLabel("0 file ditemukan")
        self.file_count_label.setStyleSheet("color: #10B981; font-size: 14px; font-weight: bold;")
        
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(self.browse_btn)
        path_row.addWidget(self.reset_tracker_btn)
        path_row.addWidget(self.file_count_label)
        folder_main_layout.addLayout(path_row)

        # Update tampilan saat pilihan sumber berubah
        def on_src_change():
            # Selalu gunakan Mode Full, tidak perlu toggle visibilitas logic_combo
            self.update_failed_badge()
        
        self.radio_src_sd.toggled.connect(on_src_change)
        self.radio_src_folder.toggled.connect(on_src_change)

        add_form_row("📁 Lokasi Folder", folder_main_layout, 0)
        
        account_row = QHBoxLayout()
        account_row.setSpacing(8)
        self.account_combo = QComboBox()
        self.account_combo.setPlaceholderText("Pilih / Tambah Akun...")
        self.account_combo.setFixedWidth(180) # Slightly wider for better visibility
        self.btn_add_account = QPushButton("Tambah Akun")
        self.btn_remove_account = QPushButton("Hapus Akun")
        self.btn_add_account.setProperty("class","secondary_pro")
        self.btn_remove_account.setProperty("class","secondary_pro")
        
        # Remove inner "Akun:" label for cleaner look and better alignment with row labels
        account_row.addWidget(self.account_combo)
        account_row.addWidget(self.btn_add_account)
        account_row.addWidget(self.btn_remove_account)
        add_form_row("👤 Akun Fotoyu", account_row, 1)

        setup_meta_row = QHBoxLayout()
        setup_meta_row.setSpacing(8)
        self.btn_setup_metadata = QPushButton("LOGIN & SETUP METADATA")
        self.btn_setup_metadata.setProperty("class", "secondary_pro")
        self.btn_setup_metadata.setFixedHeight(42)
        self.btn_setup_metadata.setMinimumWidth(240)
        self.btn_setup_metadata.setToolTip("PENTING: Jalankan ini dulu agar aplikasi 'menangkap' Harga, Deskripsi, dan Lokasi dari website Fotoyu.")
        self.setup_metadata_status = QLabel("Belum ada data Setup Metadata")
        self.setup_metadata_status.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: 900;")
        setup_meta_row.addWidget(self.btn_setup_metadata)
        setup_meta_row.addWidget(self.setup_metadata_status, 1)
        add_form_row("🧩 Setup Metadata", setup_meta_row, 2)

        # Price & FotoTree (Realtime)
        price_tree_row = QHBoxLayout()
        price_tree_row.setSpacing(15)
        
        # UI UPDATE: Aktifkan input Harga agar bisa diubah fotografer
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Harga (contoh: 8000)")
        self.price_input.setFixedWidth(120)
        self.price_input.setStyleSheet("color: #F59E0B; font-weight: 800; font-size: 13px; border: 1px solid #F59E0B;")
        
        # Tampilkan info Harga yang aktif
        self.price_display_lbl = QLabel("Harga:")
        self.price_display_lbl.setStyleSheet("color: #F59E0B; font-weight: 800; font-size: 13px;")

        # USER FIX: Sembunyikan input manual FotoTree agar UI lebih bersih
        # Data FotoTree akan otomatis diambil dari Setup Metadata
        self.fototree_input = QLineEdit()
        self.fototree_input.setVisible(False) 
        self._fototree_locked = False
        self._fototree_suggestion_map = {}
        self._last_tree_manual = False
        self._fototree_live_thread = None
        self._fototree_live_timer = QTimer(self)
        self._fototree_live_timer.setSingleShot(True)
        self._fototree_live_timer.timeout.connect(self._start_fototree_live_search)
        self.fototree_input.textEdited.connect(self._on_fototree_text_edited)
        self.fototree_input.textEdited.connect(self._schedule_fototree_live_search)
        self.fototree_input.textChanged.connect(self._update_mutual_exclusion)

        self.btn_live_tree = QPushButton("LIVE")
        self.btn_live_tree.setVisible(False)
        
        # Tampilkan info FotoTree yang aktif dalam bentuk label (Read-Only)
        self.fototree_display_lbl = QLabel("FotoTree: (Otomatis dari Setup)")
        self.fototree_display_lbl.setStyleSheet("color: #2DD4BF; font-weight: 800; font-size: 13px;")

        self.fototree_status = QLabel("Realtime")
        self.fototree_status.setStyleSheet("color: #2DD4BF; font-size: 11px; font-weight: 800;")
        self.fototree_status.setVisible(False)

        price_tree_row.addWidget(self.price_display_lbl)
        price_tree_row.addWidget(self.price_input)
        price_tree_row.addSpacing(20)
        price_tree_row.addWidget(self.fototree_display_lbl, 1)
        
        add_form_row("💰 Harga & FotoTree", price_tree_row, 3)

        # Location (Realtime Upload)
        location_row = QHBoxLayout()
        location_row.setSpacing(15)

        # USER FIX: Sembunyikan input manual Lokasi
        self.location_input = QLineEdit()
        self.location_input.setVisible(False)
        self.location_input.textChanged.connect(self._update_mutual_exclusion)
        
        # Tampilkan info Lokasi yang aktif
        self.location_display_lbl = QLabel("Lokasi: (Otomatis dari Setup)")
        self.location_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")

        self.location_mode_status = QLabel("Realtime Upload")
        self.location_mode_status.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 700;")
        self.location_mode_status.setVisible(False)

        self.chk_auto_location = QCheckBox("Gunakan Lokasi")
        self.chk_auto_location.setChecked(True)
        self.chk_auto_location.setVisible(False) # Sembunyikan checkbox karena sudah pasti pakai lokasi setup

        # Description
        # UI UPDATE: Aktifkan input Deskripsi agar bisa diubah fotografer
        self.desc_input = QTextEdit()
        self.desc_input.setText("Uploaded via AutoYu V3 Engine") # Default text
        self.desc_input.setPlaceholderText("Masukkan deskripsi di sini...")
        self.desc_input.setMaximumHeight(60)
        self.desc_input.setStyleSheet("color: #E2E8F0; font-size: 12px; border: 1px solid #334155;")
        
        # Tampilkan info Deskripsi yang aktif
        self.desc_display_lbl = QLabel("Deskripsi:")
        self.desc_display_lbl.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 12px;")

        location_row.addWidget(self.location_display_lbl, 1)
        location_row.addSpacing(20)
        location_row.addWidget(self.desc_display_lbl)
        location_row.addWidget(self.desc_input, 2)

        add_form_row("🗺️ Metadata & Deskripsi", location_row, 4)

        # 6. ENGINE OPTIMIZATION (Consolidated & Clean)
        opt_card = QFrame()
        opt_card.setStyleSheet("background-color: rgba(15, 23, 42, 0.3); border: 1px solid #334155; border-radius: 8px;")
        opt_v_layout = QVBoxLayout(opt_card)
        opt_v_layout.setContentsMargins(16, 16, 16, 16)
        opt_v_layout.setSpacing(12)

        # Row 1: Mode Auto & Result Helper
        auto_header = QHBoxLayout()
        auto_header.addWidget(self.chk_auto_calc)
        auto_header.addSpacing(12)
        
        # New: Auto Retry Checkbox
        self.chk_auto_retry = QCheckBox("Auto-Proses Sisa Gagal")
        self.chk_auto_retry.setProperty("class", "pill_pro")
        self.chk_auto_retry.setToolTip("Otomatis lanjutkan sisa gagal setelah tugas selesai")
        self.chk_auto_retry.setChecked(False)
        self.chk_auto_retry.setFocusPolicy(Qt.NoFocus)
        auto_header.addWidget(self.chk_auto_retry)
        auto_header.addSpacing(12)

        self.auto_helper = QLabel("✨ Mode Auto Aktif: Performa dioptimalkan otomatis.")
        self.auto_helper.setStyleSheet("color: #6366F1; font-size: 13px; font-weight: 700;")
        auto_header.addWidget(self.auto_helper)
        auto_header.addStretch()
        opt_v_layout.addLayout(auto_header)

        # Row 2: Manual Controls (Grid)
        self.tabs_spin = QSpinBox()
        self.tabs_spin.setStyleSheet("background-color: #0B1220; border: 1px solid #334155;")
        self.tabs_spin.setRange(1, 50)
        self.tabs_spin.setFixedHeight(35)
        self.tabs_spin.setFocusPolicy(Qt.ClickFocus)
        self.tabs_spin.setEnabled(False)
        self.tabs_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.tabs_spin.installEventFilter(self) # Disable scroll
        
        self.batch_spin = QSpinBox()
        self.batch_spin.setStyleSheet("background-color: #0B1220; border: 1px solid #334155;")
        self.batch_spin.setRange(1, 2000)
        self.batch_spin.setValue(20)
        self.batch_spin.setFixedHeight(35)
        self.batch_spin.setFocusPolicy(Qt.ClickFocus)
        self.batch_spin.setEnabled(False)
        self.batch_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.batch_spin.installEventFilter(self) # Disable scroll
        self.tabs_spin.valueChanged.connect(self._on_tabs_value_changed)
        self.tabs_spin.valueChanged.connect(self.update_dynamic_helper)
        self.batch_spin.valueChanged.connect(self._on_batch_value_changed)
        self.batch_spin.valueChanged.connect(self.update_dynamic_helper)

        manual_grid = QGridLayout()
        manual_grid.setSpacing(12)
        
        lbl_tabs = QLabel("🌐 Jumlah TAB Chrome:")
        lbl_tabs.setProperty("class", "field_label")
        lbl_batch = QLabel("🖼️ Foto / Video per TAB:")
        lbl_batch.setProperty("class", "field_label")

        manual_grid.addWidget(lbl_tabs, 0, 0)
        manual_grid.addWidget(self.tabs_spin, 0, 1)
        manual_grid.addWidget(lbl_batch, 0, 2)
        manual_grid.addWidget(self.batch_spin, 0, 3)
        
        opt_v_layout.addLayout(manual_grid)

        # Row 3: Visual Example (New)
        self.example_label = QLabel()
        self.example_label.setStyleSheet("color: #6366F1; font-size: 12px; font-weight: 600;")
        self.example_label.setText("💡 Contoh: 2500 file → 5 TAB x 500 file/tab")
        opt_v_layout.addWidget(self.example_label)

        # Row 4: Manual Helper Text (Improved)
        self.manual_helper = QLabel()
        self.manual_helper.setStyleSheet("color: #94A3B8; font-size: 12px; font-style: italic;")
        self.manual_helper.setWordWrap(True)
        self.manual_helper.setText("⚙️ Mode Manual: Atur TAB & batch manual untuk kontrol penuh.<br/>💡 Contoh: 2500 file → 5 TAB x 500 file/tab")
        opt_v_layout.addWidget(self.manual_helper)

        # Row 4: Dynamic Helper (New Feature)
        self.dynamic_helper = QLabel()
        self.dynamic_helper.setStyleSheet("""
            QLabel {
                background-color: rgba(99, 102, 241, 0.1);
                border: 1px solid #6366F1;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                color: #E2E8F0;
            }
            QLabel::warning {
                background-color: rgba(239, 68, 68, 0.1);
                border: 1px solid #EF4444;
            }
            QLabel::success {
                background-color: rgba(16, 185, 129, 0.1);
                border: 1px solid #10B981;
            }
        """)
        self.dynamic_helper.setWordWrap(True)
        self.dynamic_helper.setVisible(False)
        opt_v_layout.addWidget(self.dynamic_helper)

        grid.addWidget(opt_card, 6, 0, 1, 2)

        config_layout.addLayout(grid)
        self.content_layout.addWidget(config_card)

        # 6.5. STATUS PROGRESS (New)
        self.progress_card = QFrame()
        self.progress_card.setProperty("class", "card")
        self.progress_card.setVisible(False) # Hidden initially
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(20, 12, 20, 12)
        
        progress_header = QHBoxLayout()
        progress_title = QLabel("PROGRESS UNGGAHAN")
        progress_title.setProperty("class", "card_title")
        progress_header.addWidget(progress_title)
        progress_header.addStretch()
        
        self.progress_stats = QLabel("Menunggu...")
        self.progress_stats.setStyleSheet("color: #6366F1; font-weight: bold; font-size: 14px;")
        progress_header.addWidget(self.progress_stats)
        progress_layout.addLayout(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E293B;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366F1, stop:1 #A855F7);
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        self.progress_eta = QLabel("Perkiraan: —")
        self.progress_eta.setStyleSheet("color: #94A3B8; font-size: 12px;")
        progress_layout.addWidget(self.progress_eta)
        
        stats_row = QHBoxLayout()
        self.stat_success = QLabel("Selesai: 0")
        self.stat_failed = QLabel("Gagal: 0")
        self.stat_duplicate = QLabel("Duplikat: 0")
        self.stat_total = QLabel("Total: 0")
        
        for lbl in [self.stat_success, self.stat_failed, self.stat_duplicate, self.stat_total]:
            lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #94A3B8;")
            stats_row.addWidget(lbl)
        
        self.stat_success.setStyleSheet("font-size: 14px; font-weight: 700; color: #10B981;")
        self.stat_failed.setStyleSheet("font-size: 14px; font-weight: 700; color: #EF4444;")
        
        progress_layout.addLayout(stats_row)
        self.content_layout.addWidget(self.progress_card)

        # 7. LOG PANEL (Integrated)
        log_card = QFrame()
        log_card.setProperty("class", "card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 10, 20, 10)
        
        log_header = QHBoxLayout()
        log_title = QLabel("LOG AKTIVITAS")
        log_title.setProperty("class", "card_title")
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_layout.addLayout(log_header)
        
        self.log_text = QTextEdit()
        self.log_text.setProperty("class", "log_pro")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Menunggu inisialisasi engine...")
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        self.content_layout.addWidget(log_card)

        # 8. ACTION BUTTONS (Fixed at Bottom)
        footer_panel = QFrame()
        footer_panel.setObjectName("footer_panel")
        self.footer_v_layout = QVBoxLayout(footer_panel) # Use Vertical for multiple rows if needed
        self.footer_v_layout.setContentsMargins(16, 8, 16, 8)
        self.footer_v_layout.setSpacing(8)
        
        # Hidden login confirm button row
        self.login_confirm_btn = QPushButton("LANJUTKAN")
        self.login_confirm_btn.setProperty("class", "primary_pro")
        self.login_confirm_btn.setFixedHeight(45)
        self.login_confirm_btn.setVisible(False)
        self.login_confirm_btn.clicked.connect(self.on_login_confirmed)
        self.footer_v_layout.addWidget(self.login_confirm_btn)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # Use stretches to center buttons
        btn_layout.addStretch(1)
        
        self.retry_failed_btn = QPushButton("LANJUTKAN SISA GAGAL")
        self.retry_failed_btn.setProperty("class", "retry_dashed")
        self.retry_failed_btn.setFixedHeight(45)
        self.retry_failed_btn.setMinimumWidth(280) # Increased to prevent clipping
        self.retry_failed_btn.setCursor(Qt.PointingHandCursor)
        self.retry_failed_btn.setEnabled(False)
        self.retry_failed_btn.clicked.connect(self.on_retry_failed)
        
        self.start_btn = QPushButton("JALANKAN OTOMASI")
        self.start_btn.setProperty("class", "primary_pro")
        self.start_btn.setFixedHeight(45)
        self.start_btn.setMinimumWidth(300) # Increased for better visual balance
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(lambda: self.on_start(False))
        
        self.stop_btn = QPushButton("HENTIKAN ENGINE")
        self.stop_btn.setProperty("class", "danger_pro")
        self.stop_btn.setFixedHeight(45)
        self.stop_btn.setMinimumWidth(220) # Increased to prevent clipping
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.on_stop)
        
        btn_layout.addWidget(self.retry_failed_btn, 1)
        btn_layout.addWidget(self.start_btn, 2)
        btn_layout.addWidget(self.stop_btn, 1)
        
        btn_layout.addStretch(1)
        self.footer_v_layout.addLayout(btn_layout)
        
        self.main_outer_layout.addWidget(footer_panel)

        # 9. STATUS BAR (Fixed at Bottom)
        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(16, 0, 16, 0)
        
        def create_status_item(label, value):
            container = QHBoxLayout()
            container.setSpacing(4)
            l = QLabel(f"{label}:")
            l.setProperty("class", "status_label")
            l.setStyleSheet("font-size: 10px;")
            v = QLabel(value)
            v.setProperty("class", "status_value")
            v.setStyleSheet("font-size: 10px; font-weight: 800;")
            container.addWidget(l)
            container.addWidget(v)
            return container, v

        cont_status, self.status_val = create_status_item("Status", "Terhubung")
        sb_layout.addLayout(cont_status)
        sb_layout.addSpacing(16)
        
        cont_engine, self.status_engine = create_status_item("Engine", "SAFE")
        sb_layout.addLayout(cont_engine)
        sb_layout.addSpacing(16)
        
        cont_media, self.status_media = create_status_item("Media", "FOTO")
        sb_layout.addLayout(cont_media)
        sb_layout.addSpacing(16)
        
        cont_account, self.status_account = create_status_item("Akun", "Belum ada akun")
        sb_layout.addLayout(cont_account)
        sb_layout.addSpacing(16)
        
        cont_ram, self.status_ram = create_status_item("RAM", "—")
        sb_layout.addLayout(cont_ram)
        
        sb_layout.addStretch()
        lbl_version = QLabel("AutoYu V3.0.0")
        lbl_version.setProperty("class", "status_label")
        lbl_version.setStyleSheet("font-size: 10px;")
        sb_layout.addWidget(lbl_version)
        
        self.main_outer_layout.addWidget(status_bar)
        self.ram_timer = QTimer()
        self.ram_timer.setInterval(2000)
        self.ram_timer.timeout.connect(self._update_ram_status)
        self.ram_timer.start()
        
        # Initial RAM and Specs detection
        self._update_ram_status()
        self.update_dynamic_helper()

        # Hidden elements for logic compatibility
        self.url_input = QLineEdit()
        self.url_input.setVisible(False)

        # Defaults
        self.radio_safe.setChecked(True)
        self.radio_foto.setChecked(True)
        
        # Trigger initial checkmarks
        self.update_mode_label("SAFE", "#60A5FA")
        self.update_media_status("FOTO")
        
        # Folder path changed signal
        self.path_input.textChanged.connect(self.update_file_count)
        self.path_input.textChanged.connect(self.update_dynamic_helper)
        
        # Media mode signal
        self.radio_foto.toggled.connect(lambda checked: self.update_media_status("FOTO") if checked else None)
        self.radio_video.toggled.connect(lambda checked: self.update_media_status("VIDEO") if checked else None)
        
        # Update file count when media mode toggles
        self.radio_foto.toggled.connect(lambda: self.update_file_count(self.path_input.text()))
        self.radio_foto.toggled.connect(self.update_dynamic_helper)
        self.radio_foto.toggled.connect(self._update_manual_tabs)
        self.radio_video.toggled.connect(lambda: self.update_file_count(self.path_input.text()))
        self.radio_video.toggled.connect(self.update_dynamic_helper)
        self.radio_video.toggled.connect(self._update_manual_tabs)

        # Load saved settings
        self.apply_saved_settings()
        self.update_failed_badge()
        # Refresh folder untuk mengupdate jumlah file yang tersisa (karena sudah pindah ke processed)
        if self.path_input.text():
            self.update_file_count(self.path_input.text())

        # Notification Sound
        self.finish_sound = QSoundEffect()
        snd = None
        if sys.platform.startswith("win"):
            snd = "C:/Windows/Media/notify.wav"
        elif sys.platform == "darwin":
            snd = "/System/Library/Sounds/Glass.aiff"
        if snd and os.path.exists(snd):
            self.finish_sound.setSource(QUrl.fromLocalFile(snd))
        self.finish_sound.setVolume(0.8)
        self._apply_compact_scale()
        self._eta_start_time = None
        self._eta_base_completed = 0
        self._eta_base_progress = 0

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel:
            if source in [self.tabs_spin, self.batch_spin]:
                return True # Block wheel scroll
        return super().eventFilter(source, event)

    def apply_saved_settings(self):
        settings = load_settings()
        if settings:
            accounts = settings.get("accounts") or []
            current_account = settings.get("current_account")
            
            self.account_combo.blockSignals(True)
            self.account_combo.clear()
            for a in accounts:
                self.account_combo.addItem(a)
            
            if current_account and self.account_combo.findText(current_account) >= 0:
                self.account_combo.setCurrentText(current_account)
                self.update_account_status(current_account)
            elif accounts:
                self.account_combo.setCurrentIndex(0)
                self.update_account_status(accounts[0])
            else:
                self.status_account.setText("Belum ada akun")
                self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;") # Red for none
            self.account_combo.blockSignals(False)
            
            # Type
            type_setting = settings.get("type", "foto")
            self.last_mode = type_setting.lower()
            
            # PRIORITAS: Muat pengaturan khusus mode (FOTO/VIDEO) jika tersedia
            mode_settings = settings.get("modes", {}).get(self.last_mode)
            if mode_settings:
                # Gabungkan pengaturan global dengan pengaturan khusus mode
                # Pengaturan khusus mode akan menimpa pengaturan global
                settings.update(mode_settings)

            if type_setting == "video" and hasattr(self, 'radio_video'):
                self.radio_video.setChecked(True)
            else:
                self.radio_foto.setChecked(True)
            
            if settings.get("folder"):
                self.path_input.setText(settings["folder"])
            if settings.get("price"):
                self.price_input.setText(settings["price"])
            if settings.get("fototree"):
                self._set_fototree_value(
                    settings["fototree"],
                    locked=bool(settings.get("fototree_locked", False)),
                    persist=False
                )
            if settings.get("location"):
                self.location_input.setText(self._normalize_text_value(settings["location"]))
            if "auto_location" in settings:
                self.chk_auto_location.setChecked(settings["auto_location"])
            if settings.get("desc"):
                self.desc_input.setText(settings["desc"])
            if settings.get("tabs"):
                self.tabs_spin.setValue(settings["tabs"])
            if settings.get("batch_size"):
                val = settings["batch_size"]
                self.batch_spin.setValue(val)
            if "auto_calc" in settings:
                self.chk_auto_calc.setChecked(settings["auto_calc"])
            if "auto_retry" in settings:
                self.chk_auto_retry.setChecked(settings["auto_retry"])
            
            # Mode dikunci SAFE (utama + lite)
            self.radio_safe.setChecked(True)
            
            self.log_message("✅ Pengaturan sebelumnya berhasil dimuat.")
            
            # Show update notification in logs
            self.log_message("🚀 <b>AutoYu V3.0.0 Resmi Dirilis!</b>")
            self.log_message("✨ <i>Update: FotoTree dan Lokasi sekarang diproses realtime sesuai UI FotoYu.</i>")
        else:
            self.account_combo.clear()
            self.status_account.setText("Belum ada akun")
            self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;")
            self.log_message("🚀 <b>AutoYu V3.0.0 Siap Digunakan!</b>")
            self.log_message("✨ <i>Tips: Klik 'Tambah Akun' untuk mulai login Fotoyu.</i>")
        
        # Initial mutual exclusion check
        self._update_mutual_exclusion()
        
        self.btn_add_account.clicked.connect(self.on_add_account)
        self.btn_remove_account.clicked.connect(self.on_remove_account)
        self.btn_setup_metadata.clicked.connect(self.on_setup_metadata_clicked)
        self.account_combo.currentTextChanged.connect(self.on_account_combo_changed)
        
        # Initial Refresh Setup UI
        self._refresh_setup_metadata_ui()

    def _apply_compact_scale(self):
        try:
            sc = QApplication.primaryScreen()
            h = sc.availableGeometry().height() if sc else 768
            f = 0.85 if h <= 800 else 0.9
        except Exception:
            f = 0.85
        try:
            for lay in self.findChildren(QLayout):
                s = lay.spacing()
                if s >= 0:
                    lay.setSpacing(max(0, int(s * f)))
                m = lay.contentsMargins()
                lay.setContentsMargins(int(m.left() * f), int(m.top() * f), int(m.right() * f), int(m.bottom() * f))
        except Exception:
            pass
        try:
            self.start_btn.setFixedHeight(int(self.start_btn.height() * f))
            self.stop_btn.setFixedHeight(int(self.stop_btn.height() * f))
            self.monitor_username.setFixedHeight(int(self.monitor_username.height() * f))
            self.monitor_interval.setFixedHeight(int(self.monitor_interval.height() * f))
            self.log_text.setMinimumHeight(int(self.log_text.minimumHeight() * f))
            self.log_text.setMaximumHeight(int(self.log_text.maximumHeight() * f))
        except Exception:
            pass

    def update_license_display(self):
        is_valid, status_code, cust_name, res_data = check_license(app_type="pro")
        if is_valid:
            name = cust_name if cust_name else "Premium User"
            expiry = res_data.get('expiry', '2026-12-31')
            self.license_badge.setText(f"Licensed to {name}\nAktif sampai {expiry}")
            self.license_badge.setStyleSheet("color: #94A3B8; font-size: 13px;")
        elif status_code == "REAGREEMENT_REQUIRED":
            self.license_badge.setText("⚠️ Perlu Update Persetujuan")
            self.license_badge.setStyleSheet("color: #F59E0B; font-size: 13px; font-weight: bold;")
        else:
            if "perangkat lain" in str(status_code).lower():
                self.license_badge.setText("⚠️ Lisensi Terkunci di Perangkat Lain")
            else:
                self.license_badge.setText("Lisensi Tidak Aktif")
            self.license_badge.setStyleSheet("color: #EF4444; font-size: 13px;")

    def update_mode_label(self, mode_name, color):
        sender = self.sender()
        if sender and not sender.isChecked():
            return
            
        # Update labels with checkmarks
        self.radio_safe.setText("SAFE" + (" ✓" if mode_name == "SAFE" else ""))
        self.radio_turbo.setText("TURBO" + (" ✓" if mode_name == "TURBO" else ""))

        # Update status bar
        if hasattr(self, 'status_engine'):
            self.status_engine.setText(mode_name)
            self.status_engine.setStyleSheet(f"color: {color}; font-weight: 800;")
        
        # Update helper text based on mode
        if mode_name == "SAFE":
            self.engine_helper.setText("💡 SAFE: Jeda natural, lebih aman dan stabil")
        elif mode_name == "TURBO":
            self.engine_helper.setText("🚀 TURBO: Kecepatan maksimal, pastikan internet kenceng")

    def update_media_status(self, media_type):
        new_mode = media_type.lower()
        
        # 1. Simpan pengaturan mode saat ini sebelum berpindah
        if hasattr(self, 'last_mode') and self.last_mode != new_mode:
            try:
                current_config = self.get_current_config()
                # Hapus key 'type' agar tidak konflik saat loading balik
                current_config.pop('type', None)
                
                settings = load_settings() or {}
                if "modes" not in settings:
                    settings["modes"] = {}
                
                settings["modes"][self.last_mode] = current_config
                save_settings(settings)
            except Exception:
                pass

        if hasattr(self, 'status_media'):
            self.status_media.setText(media_type)
            color = "#60A5FA"
            self.status_media.setStyleSheet(f"color: {color}; font-weight: 800;")
             
        # Update labels with checkmarks
        self.radio_foto.setText(" 📷 FOTO" + (" ✓" if media_type == "FOTO" else ""))
        self.radio_video.setText(" 🎥 VIDEO" + (" ✓" if media_type == "VIDEO" else ""))

        # 2. Muat pengaturan untuk mode baru jika ada
        if hasattr(self, 'last_mode') and self.last_mode != new_mode:
            try:
                settings = load_settings() or {}
                mode_settings = settings.get("modes", {}).get(new_mode)
                if mode_settings:
                    # Update UI fields with saved mode settings
                    if mode_settings.get("folder"):
                        self.path_input.setText(mode_settings["folder"])
                    if mode_settings.get("price"):
                        self.price_input.setText(mode_settings["price"])
                    if mode_settings.get("desc"):
                        self.desc_input.setText(mode_settings["desc"])
                    if mode_settings.get("fototree"):
                        self._set_fototree_value(
                            mode_settings["fototree"],
                            locked=bool(mode_settings.get("fototree_locked", False)),
                            persist=False
                        )
                    if mode_settings.get("location"):
                        self.location_input.setText(self._normalize_text_value(mode_settings["location"]))
                    if "auto_calc" in mode_settings:
                        self.chk_auto_calc.setChecked(mode_settings["auto_calc"])
                    if mode_settings.get("tabs"):
                        self.tabs_spin.setValue(mode_settings["tabs"])
                    if mode_settings.get("batch_size"):
                        self.batch_spin.setValue(mode_settings["batch_size"])
                    
                    self.log_message(f"✅ Pengaturan khusus mode {media_type} dimuat.")
            except Exception:
                pass
        
        self.last_mode = new_mode

        # Update upload helper
        if media_type == "FOTO":
            self.upload_helper.setText("📸 FOTO: Unggah ribuan foto dengan metadata otomatis.")
            self.batch_spin.setMaximum(2000)
        elif media_type == "VIDEO":
            self.upload_helper.setText("🎥 VIDEO: Maks. 25 video/tab agar stabil & tidak gagal upload.")
            self.batch_spin.setMaximum(25)
            self.batch_spin.setToolTip("Direkomendasikan 25 video per tab untuk stabilitas maksimal")
            if self.batch_spin.value() > 25:
                self.batch_spin.setValue(25)
        
        # Trigger re-calc
        self.run_auto_calc()
        self.update_failed_badge()

    def _normalize_text_value(self, value):
        text = str(value or "").strip()
        if not text:
            return ""
        return text

    def _persist_current_settings(self):
        try:
            settings = load_settings() or {}
            accounts = [self.account_combo.itemText(i) for i in range(self.account_combo.count())]
            settings.update(self.get_current_config())
            settings["accounts"] = accounts
            save_settings(settings)
        except Exception:
            pass

    def _set_fototree_value(self, value, locked=False, persist=False):
        clean_text = self._normalize_text_value(value)
        self._fototree_locked = bool(locked and clean_text)
        if self.fototree_input.text().strip() != clean_text:
            self.fototree_input.setText(clean_text)
            
        # Update visual display label
        if hasattr(self, 'fototree_display_lbl'):
            if clean_text:
                self.fototree_display_lbl.setText(f"FotoTree: {clean_text}")
                self.fototree_display_lbl.setStyleSheet("color: #2DD4BF; font-weight: 800; font-size: 13px;")
                # USER FIX: Clear Location display if FotoTree is set
                if hasattr(self, 'location_display_lbl'):
                    self.location_display_lbl.setText("Lokasi: (Otomatis dari Setup)")
                    self.location_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")
                    # Clear hidden input as well
                    self.location_input.blockSignals(True)
                    self.location_input.setText("")
                    self.location_input.blockSignals(False)
            else:
                self.fototree_display_lbl.setText("FotoTree: (Otomatis dari Setup)")
                self.fototree_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")

        if persist:
            self._persist_current_settings()

    def _on_fototree_text_edited(self, _text=None):
        self._fototree_locked = False

    def _update_mutual_exclusion(self):
        """USER FIX: Implement Isi Salah Satu (Mutual Exclusion) logic"""
        tree_text = self.fototree_input.text().strip()
        loc_text = self.location_input.text().strip()

        # Jika FotoTree diisi, disable Lokasi
        if tree_text:
            self.location_input.setEnabled(False)
            self.location_input.setPlaceholderText("Nonaktif (FotoTree Terisi)")
        else:
            self.location_input.setEnabled(True)
            self.location_input.setPlaceholderText("Isi nama lokasi sesuai yang tampil di upload FotoYu")

        # Jika Lokasi diisi, disable FotoTree
        if loc_text:
            self.fototree_input.setEnabled(False)
            self.fototree_input.setPlaceholderText("Nonaktif (Lokasi Terisi)")
            self.btn_live_tree.setEnabled(False)
        else:
            self.fototree_input.setEnabled(True)
            self.fototree_input.setPlaceholderText("Ketik nama FotoTree realtime...")
            self.btn_live_tree.setEnabled(True)

    def _install_fototree_completer(self, display_items, mapping=None, popup=False):
        cleaned_items = [str(item).strip() for item in (display_items or []) if str(item).strip()]
        mapping = mapping or {item: item for item in cleaned_items}
        self._fototree_suggestion_map = mapping

        completer = QCompleter(cleaned_items, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(self._on_fototree_suggestion_selected)
        self.fototree_input.setCompleter(completer)

        if popup and display_items and self.fototree_input.hasFocus():
            completer.complete()

    def _on_fototree_suggestion_selected(self, display_text):
        actual_text = self._fototree_suggestion_map.get(display_text, display_text)
        self._set_fototree_value(actual_text, locked=True, persist=True)

    def _get_active_profile_path(self):
        account_name = self.account_combo.currentText().strip()
        if not account_name:
            return None
        return os.path.join(get_app_data_dir(), "accounts", account_name, "profile")

    def _schedule_fototree_live_search(self, _text=None):
        keyword = self.fototree_input.text().strip()
        if len(keyword) < 3:
            self.fototree_status.setText("Realtime")
            return

        self._last_tree_manual = False
        self.fototree_status.setText("Mencari...")
        self._fototree_live_timer.start(850)

    def _start_fototree_live_search(self):
        self.search_fototree_live(manual=self._last_tree_manual)

    def search_fototree_live(self, manual=False):
        keyword = self._normalize_text_value(self.fototree_input.text())
        if not keyword:
            if manual:
                self.show_custom_message("Keyword Diperlukan", "Isi nama FotoTree dulu untuk pencarian realtime.", "warning")
            return

        profile_path = self._get_active_profile_path()
        if not profile_path or not os.path.exists(profile_path):
            if manual:
                self.show_custom_message("Akun Diperlukan", "Pilih akun FotoYu yang valid terlebih dahulu.", "warning")
            self.fototree_status.setText("Tanpa Akun")
            return

        if self._fototree_live_thread and self._fototree_live_thread.isRunning():
            self._last_tree_manual = manual
            if manual:
                self.log_message("ℹ️ Pencarian FotoTree realtime sedang berjalan, menunggu hasil sebelumnya...")
            return

        self._last_tree_manual = manual
        self.btn_live_tree.setEnabled(False)
        self.btn_live_tree.setText("LIVE...")
        self.fototree_status.setText("FotoYu...")

        self._fototree_live_thread = LiveLocationSearchThread(profile_path, keyword, 100)
        self._fototree_live_thread.finished_signal.connect(self.on_fototree_live_search_finished)
        self._fototree_live_thread.start()

    def on_fototree_live_search_finished(self, success, keyword, results, message):
        self.btn_live_tree.setEnabled(True)
        self.btn_live_tree.setText("LIVE")

        current_keyword = self.fototree_input.text().strip()
        is_stale = keyword.strip() != current_keyword

        tree_names = []
        tree_mapping = {}

        if success and results:
            for item in results:
                item = item or {}
                name = str(item.get("name", "")).strip()
                subtitle = str(item.get("subtitle", "")).strip()
                if not name:
                    continue
                
                # Gunakan display_text yang lebih informatif (Nama | Lokasi)
                display_text = f"{name} | {subtitle}" if subtitle else name
                
                if display_text not in tree_mapping:
                    tree_mapping[display_text] = name
                    tree_names.append(display_text)

        if not is_stale:
            if tree_names:
                self._install_fototree_completer(tree_names, mapping=tree_mapping, popup=True)
                self.fototree_status.setText(f"Live {len(tree_names)}")
                self.fototree_status.setStyleSheet("color: #2DD4BF; font-size: 11px; font-weight: 800;")
            else:
                self.fototree_status.setText("Tidak ada")
                self.fototree_status.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 800;")

        if success and results:
            if not is_stale:
                self.log_message(f"📡 FotoTree realtime: {len(results)} kandidat untuk '{keyword}'.")
        else:
            if self._last_tree_manual or not is_stale:
                self.log_message(f"⚠️ Live FotoTree '{keyword}': {message}")

        if current_keyword != keyword and len(current_keyword) >= 3 and not (self._fototree_live_thread and self._fototree_live_thread.isRunning()):
            self._fototree_live_timer.start(250)

    def _prepare_worker_config(self, login_only=False, retry_failed_only=False):
        config = self.get_current_config()
        if not config:
            return None, None

        worker_config = config.copy()
        worker_config["login_only"] = login_only
        if retry_failed_only:
            worker_config["retry_failed_only"] = True

        if bool(worker_config.get("setup_metadata_active")):
            # Tetap gunakan nilai dari setup_data (sudah di-load di get_current_config)
            # Jangan di-None-kan agar TabAutomation bisa mengisi jika diperlukan
            worker_config["fototree_locked"] = True # Kunci jika dari setup
            return worker_config, {"tree": "setup", "location": "setup"}

        tree_text = self._normalize_text_value(worker_config.get("fototree", ""))
        tree_locked = bool(worker_config.get("fototree_locked", False)) and bool(tree_text)
        is_auto_loc = bool(worker_config.get("auto_location", True))
        loc_text = self._normalize_text_value(worker_config.get("location", ""))

        worker_config["fototree"] = tree_text or None
        worker_config["fototree_locked"] = tree_locked
        if not tree_text:
            tree_mode = "empty"
        elif tree_locked:
            tree_mode = "locked"
        else:
            tree_mode = "keyword"

        if not is_auto_loc:
            worker_config["location"] = None
            location_mode = "disabled"
        elif not loc_text:
            worker_config["location"] = None
            location_mode = "empty"
        else:
            worker_config["location"] = loc_text
            location_mode = "filled"

        return worker_config, {"tree": tree_mode, "location": location_mode}

    def _refresh_drive_list(self):
        """Memperbarui daftar drive eksternal (SD Card / USB)"""
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        self.drive_combo.addItem("Pilih Drive...")
        
        try:
            import psutil
            drives = psutil.disk_partitions()
            for d in drives:
                # Filter removable drives (SD Card, USB)
                if 'removable' in d.opts.lower() or (os.name == 'nt' and 'cdrom' not in d.opts.lower()):
                    try:
                        usage = psutil.disk_usage(d.mountpoint)
                        label = f"{d.mountpoint} ({self._format_bytes(usage.total)})"
                        self.drive_combo.addItem(label, d.mountpoint)
                    except:
                        self.drive_combo.addItem(d.mountpoint, d.mountpoint)
        except Exception as e:
            print(f"Error refresh drives: {e}")
            # Fallback sederhana jika psutil gagal
            if os.name == 'nt':
                import string
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        self.drive_combo.addItem(drive, drive)
        
        self.drive_combo.blockSignals(False)

    def _on_drive_selected(self, index):
        """Dipanggil saat drive dipilih dari dropdown"""
        drive_path = self.drive_combo.itemData(index)
        if drive_path and os.path.exists(drive_path):
            self.path_input.setText(drive_path)
            self.update_file_count(drive_path)

    def on_location_resolved(self, resolved_name, match_type, source):
        resolved_name = self._normalize_text_value(resolved_name)
        if not resolved_name:
            return
        
        # Update hidden input for internal logic
        if self.location_input.text().strip() != resolved_name:
            self.location_input.setText(resolved_name)
            
        # Update visual display label
        if hasattr(self, 'location_display_lbl'):
            self.location_display_lbl.setText(f"Lokasi: {resolved_name}")
            self.location_display_lbl.setStyleSheet("color: #10B981; font-weight: 800; font-size: 13px;")
            # USER FIX: Clear FotoTree display if Location is resolved
            if hasattr(self, 'fototree_display_lbl'):
                self.fototree_display_lbl.setText("FotoTree: (Otomatis dari Setup)")
                self.fototree_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")
                # Clear hidden input as well
                self.fototree_input.blockSignals(True)
                self.fototree_input.setText("")
                self.fototree_input.blockSignals(False)
                self._fototree_locked = False
            
        self.location_mode_status.setText("Dipilih Live")
        self.location_mode_status.setStyleSheet("color: #2DD4BF; font-size: 11px; font-weight: 800;")
        self._persist_current_settings()

    def update_account_status(self, account_name):
        if hasattr(self, 'status_account'):
            if account_name:
                self.status_account.setText(account_name)
                self.status_account.setStyleSheet("color: #10B981; font-weight: 800;")
            else:
                self.status_account.setText("Belum ada akun")
                self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;")

    def browse_folder(self):
        initial_dir = ""
        try:
            if self.radio_src_sd.isChecked():
                candidates = self._find_sd_candidates()
                if candidates:
                    initial_dir = candidates[0]
            else:
                if self.path_input.text() and os.path.isdir(self.path_input.text()):
                    initial_dir = self.path_input.text()
        except Exception:
            pass
        if not initial_dir:
            initial_dir = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Konten", initial_dir)
        if folder:
            # Normalisasi path untuk macOS/Linux agar tidak ada karakter aneh
            folder = os.path.normpath(folder)
            self.path_input.setText(folder)
            self.update_file_count(folder)

    def reset_folder_tracker(self):
        """
        Logika 'Mulai Ulang Folder Ini': Menghapus riwayat tracker agar file dideteksi ulang dari nol.
        Solusi 'Sat Set' untuk masalah upload macet atau angka deteksi salah.
        """
        folder_path = self.path_input.text()
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Peringatan", "Pilih folder yang valid terlebih dahulu.")
            return

        # USER UPDATE: Tanpa konfirmasi tambahan, langsung eksekusi "Sat Set"
        try:
            import hashlib
            # Normalisasi path persis seperti engine
            abs_path = os.path.abspath(folder_path)
            if abs_path.endswith(':'): abs_path += os.sep
            
            # SINKRONISASI LOGIKA HASH (PENTING: Gunakan .lower() dan 12 digit pertama)
            hash_path = abs_path
            # macOS/Linux are case-sensitive, only lowercase on Windows
            if os.name == 'nt':
                hash_path = hash_path.lower()
            folder_hash = hashlib.md5(hash_path.encode('utf-8')).hexdigest()[:12]
            
            # Cari lokasi tracker (AppData)
            if sys.platform == 'darwin':
                base_local = os.path.expanduser("~/Library/Application Support/AutoYuPro")
            else:
                base_local = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
            
            tracker_file = os.path.join(base_local, "trackers", f"tracker_{folder_hash}.json")
            local_tracker = os.path.join(abs_path, ".upload_tracker.json")
            
            deleted_count = 0
            for f in [tracker_file, tracker_file + ".bak", local_tracker, local_tracker + ".bak"]:
                if os.path.exists(f):
                    try:
                        # Windows: Pastikan file tidak hidden sebelum hapus
                        if os.name == 'nt':
                            import ctypes
                            ctypes.windll.kernel32.SetFileAttributesW(f, 128) # 128 = Normal
                        os.remove(f)
                        deleted_count += 1
                    except Exception:
                        pass
            
            # Paksa refresh UI
            self._last_loaded_folder = None
            self.update_file_count(folder_path)
            
            # Update status di UI secara eksplisit agar tombol "Jalankan Otomasi" tahu data sudah bersih
            self.chk_auto_calc.setChecked(True) # Force auto-calc untuk refresh pembagian file
            self.run_auto_calc()
            
            if deleted_count > 0:
                self.log_message(f"🔄 <b>Sapu Bersih:</b> Riwayat folder '{os.path.basename(folder_path)}' dihapus. Memulai ulang otomasi...")
                # Jeda sebentar agar user melihat status
                QTimer.singleShot(1000, self.on_start)
            else:
                self.log_message(f"ℹ️ <b>Info:</b> Tidak ada riwayat lama, memulai otomasi dari awal...")
                QTimer.singleShot(500, self.on_start)
                
        except Exception as e:
            self.log_message(f"⚠️ <b>Error Reset:</b> {e}")
            QMessageBox.critical(self, "Error", f"Gagal menghapus riwayat: {e}")

    def update_file_count(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            self.file_count_label.setText("0 file ditemukan")
            self.update_failed_badge()
            return
            
        # Normalisasi path untuk perbandingan
        folder_path = os.path.abspath(folder_path)
        if folder_path.endswith(':'): folder_path += os.sep

        # Auto-detect SD/removable drive and show helper
        self._auto_detect_sd(folder_path)
        
        # PROAKTIF: Muat konfigurasi pekerjaan sebelumnya jika ada tracker di folder ini
        # HANYA muat jika folder benar-benar baru, agar tidak menimpa pilihan mode (Foto/Video) saat ini
        if folder_path != self._last_loaded_folder:
            self._load_job_config_from_folder(folder_path)
            self._last_loaded_folder = folder_path

        # macOS: Trigger permission popup by trying to read folder
        if sys.platform == "darwin":
            try:
                # This simple os.listdir will force macOS to show the "App wants to access folder" popup
                os.listdir(folder_path)
            except Exception as e:
                print(f"macOS Permission Hint: {e}")
            
        try:
            specs = self.detect_system_specs()
            is_foto = self.radio_foto.isChecked()
            # Hapus batasan limit 10000 file agar tak terbatas
            count = self._count_media_files(folder_path, is_foto, limit=1000000)
            
            if is_foto:
                label_text = f"{count} foto ditemukan"
            else:
                label_text = f"{count} video ditemukan"
            self.file_count_label.setText(label_text)
            if not self.chk_auto_calc.isChecked():
                # MODE MANUAL: Sesuaikan jumlah TAB otomatis berdasarkan jumlah foto per tab (batch)
                # agar semua file di folder baru tercover sesuai keinginan user
                batch = self.batch_spin.value()
                if batch > 0 and count > 0:
                    new_tabs = math.ceil(count / batch)
                    self.tabs_spin.blockSignals(True)
                    self.tabs_spin.setValue(min(new_tabs, self.tabs_spin.maximum()))
                    self.tabs_spin.blockSignals(False)
                self._update_manual_tabs(count)
            
            if count > 0:
                self.file_count_label.setStyleSheet("color: #10B981; font-size: 11px; font-weight: bold; margin-left: 5px;")
                # Trigger auto calc when folder content changes
                self.run_auto_calc()
            else:
                self.file_count_label.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold; margin-left: 5px;")
            self.update_failed_badge()
        except Exception:
            self.file_count_label.setText("Error membaca folder")
            self.file_count_label.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold; margin-left: 5px;")
            self.update_failed_badge()
    
    def _update_manual_tabs(self, count=None):
        try:
            # Tetap izinkan update visual meskipun auto_calc aktif agar sinkron
            if count is None:
                text = self.file_count_label.text()
                m = re.search(r"(\d+)", text)
                count = int(m.group(1)) if m else 0
            
            batch = max(1, int(self.batch_spin.value()))
            tabs = max(1, int(self.tabs_spin.value()))
            is_foto = self.radio_foto.isChecked()
            
            # Update visual example
            actual_batch = batch
            if not is_foto and batch > 25:
                actual_batch = 25
            
            total_will_upload = min(count, tabs * actual_batch)
            if count > 0:
                text = f"💡 Estimasi: {total_will_upload} dari {count} file akan diunggah ({tabs} TAB x {actual_batch} file)"
                if not is_foto and batch > 25:
                    text += "<br/>⚠️ <span style='color: #EF4444;'>Video dibatasi 25/tab demi stabilitas</span>"
                
                self.example_label.setText(text)
                if total_will_upload < count:
                    self.example_label.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: 600;") # Warning color
                else:
                    self.example_label.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;") # Success color
            else:
                self.example_label.setText("💡 Contoh: 2500 file → 5 TAB x 500 file/tab")
                self.example_label.setStyleSheet("color: #6366F1; font-size: 12px; font-weight: 600;")
        except Exception:
            pass
    
    def _auto_detect_sd(self, folder_path):
        # USER FIX: Skip Windows-specific drive detection on macOS/Linux
        if os.name != 'nt':
            # On Mac, we can check for /Volumes path
            if folder_path.startswith('/Volumes/'):
                self.radio_src_sd.setChecked(True)
            return

        try:
            drive, _ = os.path.splitdrive(folder_path)
            if not drive:
                return
            root = drive + "\\"
            # DRIVE_REMOVABLE = 2
            try:
                dtype = ctypes.windll.kernel32.GetDriveTypeW(root)
            except:
                dtype = 0
            # Fallback heuristics: banyak card reader melapor sebagai FIXED (3)
            # Deteksi folder khas SD: DCIM/PRIVATE/MISC di root
            sd_signals = ["DCIM", "PRIVATE", "MISC", "AVCHD", "MP_ROOT", "CANONMSC", "CANONDC", "SONY", "NIKON", "FUJIFILM", "PANASONIC"]
            has_sd_signature = any(os.path.isdir(os.path.join(root, name)) for name in sd_signals)
            in_dcim_path = ("\\DCIM\\" in folder_path) or folder_path.upper().endswith("\\DCIM") or folder_path.upper().endswith("\\DCIM\\")
            if dtype == 2 or has_sd_signature or in_dcim_path:
                self.radio_src_sd.setChecked(True)
            else:
                self.radio_src_folder.setChecked(True)
        except Exception:
            pass
    
    def _find_sd_candidates(self):
        candidates = []
        # USER FIX: Handle macOS removable drives
        if sys.platform == 'darwin':
            try:
                volumes = "/Volumes"
                if os.path.exists(volumes):
                    for name in os.listdir(volumes):
                        path = os.path.join(volumes, name)
                        if os.path.isdir(path) and not name.startswith('.'):
                            # Deteksi folder khas SD
                            sd_signals = ["DCIM", "PRIVATE", "MISC"]
                            if any(os.path.isdir(os.path.join(path, s)) for s in sd_signals):
                                candidates.append(path)
            except:
                pass
            return candidates

        try:
            for code in range(ord('A'), ord('Z')+1):
                drive = chr(code) + ":\\"
                if not os.path.exists(drive):
                    continue
                try:
                    dtype = ctypes.windll.kernel32.GetDriveTypeW(drive)
                except Exception:
                    dtype = 0
                sd_signals = ["DCIM", "PRIVATE", "MISC", "AVCHD", "MP_ROOT", "CANONMSC", "CANONDC", "SONY", "NIKON", "FUJIFILM", "PANASONIC"]
                has_sd_signature = any(os.path.isdir(os.path.join(drive, name)) for name in sd_signals)
                if dtype == 2 or has_sd_signature:
                    candidates.append(drive)
        except Exception:
            pass
        return candidates
    
    def _set_sd_candidate_path(self):
        try:
            candidates = self._find_sd_candidates()
            if candidates:
                self.path_input.setText(candidates[0])
                self.update_file_count(candidates[0])
        except Exception:
            pass

    def toggle_auto_calc(self, checked):
        self.tabs_spin.setEnabled(not checked)
        self.batch_spin.setEnabled(not checked)
        
        if checked:
            self.auto_helper.setText("✨ Mode Auto Aktif: Performa dioptimalkan otomatis.")
            self.auto_helper.setStyleSheet("color: #6366F1; font-size: 13px; font-weight: 700;")
            self.manual_helper.setText("💡 Mode Manual non-aktif. Matikan Mode Auto untuk kontrol penuh.")
            self.run_auto_calc()
            self.update_dynamic_helper()
        else:
            self.auto_helper.setText("💡 Mode Manual Aktif: Kendali penuh di tangan Anda.")
            self.auto_helper.setStyleSheet("color: #F59E0B; font-size: 13px; font-weight: 700;")
            self.manual_helper.setText("⚙️ Atur TAB & Batch manual. Sistem tetap menjaga stabilitas CPU.")
            self._update_manual_tabs()
            self.update_dynamic_helper()

    def _on_batch_value_changed(self, val):
        """Called when batch spin box value changes manually or via code"""
        if self.chk_auto_calc.isChecked():
            return
            
        # Real-time sync: Update tabs based on batch size
        text = self.file_count_label.text()
        m = re.search(r"(\d+)", text)
        count = int(m.group(1)) if m else 0
        if count > 0 and val > 0:
            new_tabs = math.ceil(count / val)
            self.tabs_spin.blockSignals(True)
            self.tabs_spin.setValue(min(new_tabs, self.tabs_spin.maximum()))
            self.tabs_spin.blockSignals(False)
            
        self._update_manual_tabs(count)

    def _on_tabs_value_changed(self, val):
        """Called when tabs spin box value changes manually"""
        if self.chk_auto_calc.isChecked():
            return
            
        # Real-time sync: Update batch size based on number of tabs
        text = self.file_count_label.text()
        m = re.search(r"(\d+)", text)
        count = int(m.group(1)) if m else 0
        if count > 0 and val > 0:
            new_batch = math.ceil(count / val)
            self.batch_spin.blockSignals(True)
            self.batch_spin.setValue(min(new_batch, self.batch_spin.maximum()))
            self.batch_spin.blockSignals(False)
            
        self._update_manual_tabs(count)

    def update_dynamic_helper(self):
        """Update Dynamic Helper with TAB optimal, estimasi waktu, mode rekomendasi, dan warning"""
        if not self.chk_auto_calc.isChecked():
            # Only show dynamic helper in manual mode
            self.dynamic_helper.setVisible(False)
            return
        
        folder_path = self.path_input.text()
        if not folder_path or not os.path.exists(folder_path):
            # Show quick guide when no folder selected
            quick_guide = """
            1. Pilih folder konten (drag & drop atau klik "Telusuri")<br/>
            2. Mode Auto: AI Optimized (REKOMENDASI)<br/>
            3. Mode Manual: Atur TAB & batch manual secara bebas<br/>
            4. Klik "JALANKAN OTOMASI"
            """
            self.dynamic_helper.setText(quick_guide)
            self.dynamic_helper.setProperty("class", "success")
            self.dynamic_helper.setVisible(True)
            return
        
        try:
            total_files = self._count_media_files(folder_path, True, limit=1000000)
            
            if total_files == 0:
                self.dynamic_helper.setVisible(False)
                return
            
            # Get current specs and optimal config
            specs = self.detect_system_specs()
            optimal_config = self.get_optimal_config(total_files)
            
            # Use AI's suggested base values
            ai_tabs_limit = optimal_config["tabs"]
            ai_batch_limit = optimal_config["batch"]
            
            # Current values from UI
            current_batch = self.batch_spin.value()
            current_tabs = self.tabs_spin.value()
            
            # Calculate REAL optimal based on system limits
            is_foto = self.radio_foto.isChecked()
            actual_base_batch = 25 if not is_foto else ai_batch_limit
            
            optimal_tabs = max(1, min(ai_tabs_limit, math.ceil(total_files / actual_base_batch)))
            optimal_batch = math.ceil(total_files / optimal_tabs)
            if not is_foto and optimal_batch > 25:
                optimal_batch = 25
            
            # Estimated time calculation (approx 1-2 detik per file)
            time_per_file = 2.5 if current_batch <= 300 else (1.8 if current_batch <= 600 else 1.2)
            estimated_seconds = total_files * time_per_file / current_tabs
            
            if estimated_seconds < 60:
                estimated_time = f"{int(estimated_seconds)} detik"
            elif estimated_seconds < 3600:
                minutes = int(estimated_seconds / 60)
                estimated_time = f"{minutes} menit"
            else:
                hours = int(estimated_seconds / 3600)
                minutes = int((estimated_seconds % 3600) / 60)
                estimated_time = f"{hours} jam {minutes} menit"
            
            # Check for warnings
            warnings = []
            if current_batch > 1500:
                warnings.append("⚠️ Batch terlalu besar (>1500), risiko browser crash")
            
            if current_tabs > 6:
                warnings.append("⚠️ Jumlah TAB >6, batasi maksimal 6 untuk stabilitas")
            
            if current_tabs < optimal_tabs:
                warnings.append(f"💡 Tambah TAB ke {optimal_tabs} untuk efisiensi")
            
            # Build helper text
            specs_text = ""
            if specs:
                specs_text = f"<b>💻 {specs['os']}</b> | "
                specs_text += f"💾 RAM: <span style='color:#10B981;'>{specs['ram_gb']}GB</span> | "
                specs_text += f"🧠 CPU: <span style='color:#F59E0B;'>{specs['cpu_cores']} cores</span><br/>"
            
            helper_text = f"{specs_text}"
            helper_text += f"📁 File: <span style='color:#6366F1; font-weight:bold;'>{total_files}</span> | "
            helper_text += f"📦 Batch: <span style='color:#10B981; font-weight:bold;'>{current_batch}</span> | "
            helper_text += f"🌐 TAB: <span style='color:#F59E0B; font-weight:bold;'>{current_tabs}</span><br/>"
            
            helper_text += f"🎯 AI Optimal: <span style='color:#10B981;'>{optimal_tabs} TAB Aktif</span> | "
            helper_text += f"⏱️ Estimasi: <span style='color:#6366F1;'>{estimated_time}</span>"
            
            # AI Optimized note - real calculation based on system specs
            ai_note = "✨ AI Optimized (Real-time calculation)"
            helper_text += f"<br/>{ai_note}"
            
            if warnings:
                helper_text += f"<br/>⚠️ <span style='color:#EF4444;'>{' | '.join(warnings)}</span>"
                self.dynamic_helper.setProperty("class", "warning")
            else:
                self.dynamic_helper.setProperty("class", "success")
            
            self.dynamic_helper.setText(helper_text)
            self.dynamic_helper.setVisible(True)
            
        except Exception as e:
            self.dynamic_helper.setVisible(False)

    def run_auto_calc(self):
        if not hasattr(self, 'chk_auto_calc') or not self.chk_auto_calc.isChecked():
            return
            
        if not hasattr(self, 'tabs_spin') or not hasattr(self, 'batch_spin'):
            return

        folder_path = self.path_input.text()
        if not folder_path or not os.path.exists(folder_path):
            return
            
        try:
            specs = self.detect_system_specs()
            is_foto = self.radio_foto.isChecked()
            # Hapus batasan limit 10000 file agar tak terbatas
            count = self._count_media_files(folder_path, is_foto, limit=1000000)
            
            if count == 0:
                return
            
            # Get optimal config based on system specs (REAL calculation, no lies)
            optimal_config = self.get_optimal_config(count)
            base_tabs = optimal_config["tabs"]
            base_batch = optimal_config["batch"]
            
            # AI Optimized calculation - REAL optimal based on file count
            if is_foto:
                # USER FEEDBACK: Stabil pada batch >= 300 foto per tab
                min_ai_batch = 300
                if count <= min_ai_batch:
                    tabs = 1
                    batch = count
                else:
                    # AI mencoba membagi rata dengan target minimal 300 per tab
                    ideal_tabs = max(1, min(base_tabs, math.ceil(count / min_ai_batch)))
                    tabs = ideal_tabs
                    batch = math.ceil(count / tabs)
            else:
                # Mode Video: Tetap limit 25 per tab demi stabilitas
                if count <= 25:
                    tabs = 1
                    batch = count
                else:
                    tabs = max(1, min(base_tabs, math.ceil(count / 25)))
                    batch = math.ceil(count / tabs)
                    if batch > 25: batch = 25
            
            # Hard limit for safety
            if is_foto:
                max_safety_batch = 1500
                if batch > max_safety_batch:
                    batch = max_safety_batch
                    tabs = math.ceil(count / batch)
            
            # Ensure batch is reasonable
            if batch < 10: 
                batch = 10
            
            # Update UI
            self.tabs_spin.blockSignals(True)
            self.batch_spin.blockSignals(True)
            self.tabs_spin.setValue(tabs)
            self.batch_spin.setValue(batch)
            self.tabs_spin.blockSignals(False)
            self.batch_spin.blockSignals(False)
            
            # Trigger manual update to sync labels
            self._update_manual_tabs(count)

            # Extra info for video mode
            if not is_foto:
                specs_info = " (Limit 25 video/tab agar stabil)"
            else:
                specs_info = ""
            if specs:
                specs_info = f" ({specs['os']}, {specs['ram_gb']}GB RAM)"
            
            # AI Optimized calculation with REAL data - NO LIES
            ai_note = "✨ AI Optimized"
            self.auto_helper.setText(f"{ai_note}: Performa dioptimalkan otomatis untuk {count} file{specs_info}")
            self.auto_helper.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 800;")
            
        except Exception:
            pass
    
    def _count_media_files(self, folder_path, is_foto, limit=None):
        if is_foto:
            exts = ('.jpg', '.jpeg', '.png')
        else:
            exts = ('.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.3gp', '.m4v', '.mpg', '.mpeg')
        total = 0
        try:
            for root, dirs, files in os.walk(folder_path):
                # Optimasi: Jangan scan folder 'processed' atau 'failed' buatan aplikasi
                if 'processed' in dirs:
                    dirs.remove('processed')
                if 'failed' in dirs:
                    dirs.remove('failed')
                    
                for name in files:
                    # macOS / Linux: Abaikan file bayangan (._*) dan file sistem (.DS_Store)
                    if name.startswith('._') or name.startswith('.DS_Store'):
                        continue
                        
                    if name.lower().endswith(exts):
                        total += 1
                        if limit and total >= limit:
                            return total
            return total
        except Exception:
            return 0

    def log_message(self, msg):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        
        # Color definitions
        GREEN = "#10B981"
        RED = "#EF4444"
        INDIGO = "#6366F1"
        GRAY = "#94A3B8"
        
        # Detect if this is a summary line or has specific keywords for multi-color
        if "sukses" in msg.lower() and "gagal" in msg.lower():
            # Advanced multi-color formatting for summary lines
            # Example: "Tab 4: 20 sukses, 0 gagal"
            processed_msg = msg
            # Color "N sukses" green
            processed_msg = re.sub(r'(\d+)\s+sukses', fr'<b style="color: {GREEN};">\1 sukses</b>', processed_msg)
            # Color "N gagal" red
            processed_msg = re.sub(r'(\d+)\s+gagal', fr'<b style="color: {RED};">\1 gagal</b>', processed_msg)
            formatted_msg = f'<span style="color: #475569;">[{timestamp}]</span> <span style="color: {GRAY};">{processed_msg}</span>'
        else:
            # Standard single-color formatting
            color = GRAY
            if "SUCCESS" in msg.upper() or "BERHASIL" in msg.upper() or "DONE" in msg.upper() or "SUKSES" in msg.upper():
                color = GREEN
            elif "ERROR" in msg.upper() or "GAGAL" in msg.upper() or "FAILED" in msg.upper():
                color = RED
            elif "INFO" in msg.upper() or "START" in msg.upper():
                color = INDIGO
                
            formatted_msg = f'<span style="color: #475569;">[{timestamp}]</span> <span style="color: {color};">{msg}</span>'
        
        # Safety check: ensure log_text exists before appending
        if not hasattr(self, 'log_text') or self.log_text is None:
            print(f"[{timestamp}] {msg}")
            return

        self.log_text.append(formatted_msg)
        try:
            doc = self.log_text.document()
            max_blocks = 1200
            keep_blocks = 900
            if doc and doc.blockCount() > max_blocks:
                remove_blocks = doc.blockCount() - keep_blocks
                end_block = doc.findBlockByNumber(remove_blocks)
                if end_block.isValid():
                    cursor = QTextCursor(doc)
                    cursor.setPosition(0)
                    cursor.setPosition(end_block.position(), QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.deleteChar()
        except Exception:
            pass
        # Auto scroll
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_progress(self, uploaded, failed, duplicate, active, total):
        if not self.progress_card.isVisible():
            self.progress_card.setVisible(True)
            
        self.progress_bar.setMaximum(total)
        # Real-time progress: completed + current active (clamped to total)
        progress_value = uploaded + failed + active
        if progress_value > total:
            progress_value = total
        self.progress_bar.setValue(progress_value)
        
        percent = 0
        if total > 0:
            percent = int((progress_value / total) * 100)
            
        status_text = f"{percent}% Selesai"
        if active > 0:
            status_text += f" (Sedang memproses {active} file...)"
        
        self.progress_stats.setText(status_text)
        self.stat_success.setText(f"Selesai: {uploaded}")
        self.stat_failed.setText(f"Gagal: {failed}")
        self.stat_duplicate.setText(f"Duplikat: {duplicate}")
        self.stat_total.setText(f"Total: {total}")
        completed = uploaded + failed
        if self._eta_start_time is None and total > 0 and progress_value > 0:
            self._eta_start_time = time.time()
            self._eta_base_completed = completed
            self._eta_base_progress = progress_value
        eta_text = "—"
        if self._eta_start_time is not None:
            elapsed = max(time.time() - self._eta_start_time, 0.001)
            # Prioritaskan perhitungan berbasis progress (completed + active) agar ETA muncul lebih cepat
            delta_progress = max(progress_value - self._eta_base_progress, 0)
            if delta_progress > 0 and elapsed > 1.5:
                rate = delta_progress / elapsed  # item per detik (berbasis progress bar)
                remaining_items = max(total - completed, 0)
                if rate > 0 and remaining_items > 0:
                    seconds = int(remaining_items / rate)
                    h = seconds // 3600
                    m = (seconds % 3600) // 60
                    s = seconds % 60
                    if h > 0:
                        eta_text = f"{h}j {m}m {s}d"
                    else:
                        eta_text = f"{m}m {s}d"
        self.progress_eta.setText(f"Perkiraan selesai: {eta_text}")

    def on_new_photo_detected(self, count):
        pass

    def check_for_updates(self):
        """Menjalankan pengecekan update di thread terpisah."""
        try:
            self.update_checker = UpdateChecker(AUTO_YU_VERSION)
            self.update_checker.update_available.connect(self.show_update_notification)
            self.update_checker.start()
        except Exception as e:
            print(f"Error checking for updates: {e}")

    def show_update_notification(self, data):
        """Menampilkan frame notifikasi update jika tersedia."""
        latest_ver = data.get("version", "???")
        self.latest_update_url = data.get("url")
        
        self.update_label.setText(f"🚀 Versi baru {latest_ver} tersedia! Segera perbarui untuk fitur terbaru.")
        self.update_frame.setVisible(True)
        
        # Log ke panel agar user tahu
        self.log_message(f"✨ Update tersedia: Versi {latest_ver}. Silakan klik tombol update di atas.")
        """Called when watcher detects new photos or resend requests on profile"""
        # Play sound
        if hasattr(self, 'finish_sound'):
            self.finish_sound.play()
            
        self.log_message(f"🔔 NOTIFIKASI: Ada permintaan kirim ulang baru terdeteksi!")
        
        # Show mini-popup
        msg = "🔔 Permintaan Kirim Ulang Baru Terdeteksi!\n\n"
        msg += "Sistem menemukan indikasi permintaan baru di halaman profil Anda.\n"
        msg += "Silakan cek browser untuk melihat detailnya."
        
        self.show_custom_message("Notifikasi Fotoyu", msg, "info")

    def show_finish_notification(self, uploaded, failed):
        """Shows a beautiful summary popup and plays notification sound."""
        # Play sound
        if hasattr(self, 'finish_sound'):
            self.finish_sound.play()

        # Get current account name
        current_account = self.account_combo.currentText() if hasattr(self, 'account_combo') else ""

        # Prepare message
        msg = f"Seluruh proses unggah telah selesai!\n\n"
        msg += f"👤 Akun: {current_account}\n"
        msg += f"✅ Berhasil: {uploaded} file\n"
        if failed > 0:
            msg += f"❌ Gagal: {failed} file\n"

        # Create custom message box
        popup = QMessageBox(self)
        popup.setWindowTitle("AutoYu - Tugas Selesai")
        popup.setText(msg)
        popup.setIcon(QMessageBox.Information)
        
        # Add custom buttons
        upload_new_btn = popup.addButton("📷 UPLOAD FOTO BARU", QMessageBox.ActionRole)
        retry_failed_btn = None
        # Lite mode: jangan tampilkan tombol lanjutan sisa gagal.
        current_cfg = self.get_current_config() if hasattr(self, "get_current_config") else {}
        is_lite = bool(current_cfg.get("is_lite"))
        if failed > 0 and not is_lite:
            retry_failed_btn = popup.addButton("🔄 LANJUTKAN SISA GAGAL", QMessageBox.ActionRole)
        close_btn = popup.addButton("TUTUP", QMessageBox.AcceptRole)
        
        # WAJIB MUNCUL DI DEPAN (ON TOP) & DITENGAH LAYAR
        popup.setWindowFlags(popup.windowFlags() | Qt.WindowStaysOnTopHint | Qt.WindowSystemMenuHint)
        
        popup.setStyleSheet("""
            QMessageBox {
                background-color: #1E293B;
                border: 1px solid #4F46E5;
                border-radius: 8px;
            }
            QLabel {
                color: #E2E8F0;
                font-size: 14px;
                font-weight: 500;
                padding: 10px;
            }
            QPushButton {
                background-color: #6366F1;
                color: white;
                border-radius: 4px;
                padding: 12px 30px;
                font-weight: bold;
                min-width: 180px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton[action="upload_new"] {
                background-color: #10B981;
                min-width: 200px;
            }
            QPushButton[action="upload_new"]:hover {
                background-color: #059669;
            }
            QPushButton[action="retry_failed"] {
                background-color: rgba(239, 68, 68, 0.15);
                color: #EF4444;
                border: 2px dashed #EF4444;
                border-radius: 4px;
                font-weight: 900;
                min-width: 200px;
            }
            QPushButton[action="retry_failed"]:hover {
                background-color: rgba(239, 68, 68, 0.25);
                border: 2px solid #EF4444;
            }
        """)
        
        # Set custom button properties
        for btn in popup.buttons():
            if btn.text() == "📷 UPLOAD FOTO BARU":
                btn.setProperty("action", "upload_new")
            elif btn.text() == "🔄 LANJUTKAN SISA GAGAL":
                btn.setProperty("action", "retry_failed")
            elif btn.text() == "TUTUP":
                btn.setProperty("action", "close")
        
        # Centering Logic (Wajib di tengah layar walau app di minimize)
        popup.show() # Show first to get geometry
        screen_geo = QApplication.primaryScreen().availableGeometry()
        popup_geo = popup.frameGeometry()
        popup_geo.moveCenter(screen_geo.center())
        popup.move(popup_geo.topLeft())
        
        # Force activation
        popup.raise_()
        popup.activateWindow()
        
        # --- AUTO RETRY LOGIC (New) ---
        auto_retry_active = False
        if failed > 0 and not is_lite and self.chk_auto_retry.isChecked() and retry_failed_btn:
            auto_retry_active = True
            remaining_secs = 5
            original_text = "🔄 LANJUTKAN SISA GAGAL"
            
            def on_timeout():
                nonlocal remaining_secs
                if not popup.isVisible():
                    timer.stop()
                    return
                
                if remaining_secs > 0:
                    retry_failed_btn.setText(f"🔄 AUTO-PROSES ({remaining_secs}s)")
                    remaining_secs -= 1
                else:
                    timer.stop()
                    retry_failed_btn.setText(original_text)
                    retry_failed_btn.click() # Simulate click to trigger processing

            timer = QTimer(popup)
            timer.timeout.connect(on_timeout)
            timer.start(1000)
            on_timeout() # First call
        
        result = popup.exec()
        
        # STOP ENGINE IMMEDIATELY when popup is closed/finished
        # This prevents the engine from "working twice" or staying active
        self.stop_signal.emit()
        
        # Check which button was clicked
        clicked_btn = popup.clickedButton()
        if clicked_btn and clicked_btn.property("action") == "upload_new":
            self.browse_folder()
        elif clicked_btn and clicked_btn.property("action") == "retry_failed":
            self.on_continue_failed_from_popup()
        
        self.update_failed_badge()
        # Refresh folder agar jumlah file di UI terupdate (file yang sudah diproses hilang dari folder utama)
        if self.path_input.text():
            self.update_file_count(self.path_input.text())

    def get_current_config(self):
        """Helper to collect all current UI values into a config dict"""
        # We save both the raw text and the checkbox state
        mode_name = "SAFE"
        type_name = "video" if hasattr(self, 'radio_video') and self.radio_video.isChecked() else "foto"
        
        # Selalu gunakan Mode Full (Tracker Only) untuk keandalan dan kebersihan folder
        sd_card_mode = True
        recursive_scan = True
        
        # Load setup metadata if available
        setup_data = self._load_setup_metadata_file()
        is_setup_active = bool(getattr(self, "_setup_metadata_active", False))
        
        # UI UPDATE: Prioritaskan input manual dari UI agar fotografer bisa bebas mengubah
        price = self.price_input.text().strip()
        if not price:
            price = setup_data.get("price") or "3000"
            
        desc = self.desc_input.toPlainText().strip()
        if not desc:
            desc = setup_data.get("desc") or "Uploaded via AutoYu V3 Engine"

        fototree = self._normalize_text_value(self.fototree_input.text())
        location = self._normalize_text_value(self.location_input.text())
        
        # Jika input manual kosong, gunakan data dari setup
        if not fototree and not location:
            fototree = setup_data.get("fototree_name", "")
            location = setup_data.get("location_name", "")
            
        # Pastikan mutlak salah satu kosong jika yang lain terisi
        if fototree:
            location = ""
        elif location:
            fototree = ""

        # Normalisasi path folder agar seragam di seluruh aplikasi
        raw_folder = self.path_input.text()
        normalized_folder = ""
        if raw_folder:
            normalized_folder = os.path.normpath(os.path.abspath(raw_folder))
            if os.name == 'nt' and normalized_folder.endswith(':'):
                normalized_folder += os.sep

        config = {
            "app_type": self.app_type,
            "is_lite": self.app_type == "lite",
            "mode": mode_name,
            "type": type_name,
            "folder": normalized_folder,
            "price": price,
            "desc": desc,
            "fototree": fototree,
            "fototree_locked": bool(self._fototree_locked and fototree),
            "location": location,
            "auto_location": self.chk_auto_location.isChecked(),
            "setup_metadata_active": is_setup_active,
            "tabs": self.tabs_spin.value(),
            "batch_size": self.batch_spin.value(),
            "auto_calc": self.chk_auto_calc.isChecked(),
            "auto_retry": self.chk_auto_retry.isChecked(),
            "current_account": self.account_combo.currentText(),
            "sd_card_mode": sd_card_mode,
            "recursive_scan": recursive_scan
        }
        return config

    def closeEvent(self, event):
        """Saves settings automatically when the window is closed"""
        if getattr(self, "_skip_save", False):
            event.accept()
            return

        try:
            config = self.get_current_config()
            settings = load_settings() or {}
            # Get current account list from UI combo box
            accounts = [self.account_combo.itemText(i) for i in range(self.account_combo.count())]
            settings.update(config)
            settings["accounts"] = accounts
            
            # Simpan juga ke mode-specific settings
            if "modes" not in settings:
                settings["modes"] = {}
            mode_config = config.copy()
            mode_config.pop('type', None)
            settings["modes"][config['type']] = mode_config
            
            save_settings(settings)
        except Exception:
            pass
        event.accept()

    def _get_setup_metadata_file(self, account_name=None):
        if not account_name:
            account_name = str(self.account_combo.currentText() or "").strip()
        
        # Jika tidak ada akun, gunakan default lama agar tidak pecah
        if not account_name or account_name == "Pilih / Tambah Akun":
            return os.path.join(APP_SETTINGS_DIR, "trackers", "api_metadata.json")
            
        # Gunakan file spesifik per akun
        return os.path.join(APP_SETTINGS_DIR, "trackers", f"api_metadata_{account_name}.json")

    def _load_setup_metadata_file(self):
        metadata_file = self._get_setup_metadata_file()
        if not os.path.exists(metadata_file):
            return {}
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _has_setup_metadata(self, data=None):
        data = data if data is not None else self._load_setup_metadata_file()
        keys = ("price", "desc", "fototree_name", "location_name", "tree_id", "location_id")
        return any(self._normalize_text_value(data.get(k, "")) for k in keys)

    def _has_web_setup_done(self):
        try:
            account = self.account_combo.currentText().strip() if hasattr(self, "account_combo") else ""
            if not account:
                return False
            settings = load_settings() or {}
            setup_accounts = settings.get("setup_done_accounts") or {}
            if not isinstance(setup_accounts, dict):
                return False
            return bool(setup_accounts.get(account))
        except Exception:
            return False

    def _refresh_setup_metadata_ui(self):
        data = self._load_setup_metadata_file()
        has_setup = self._has_web_setup_done() or self._has_setup_metadata(data)
        self._setup_metadata_active = has_setup

        if has_setup:
            tree_name = self._normalize_text_value(data.get("fototree_name"))
            loc_name = self._normalize_text_value(data.get("location_name"))
            price = self._normalize_text_value(data.get("price"))
            desc = self._normalize_text_value(data.get("desc"))

            # Update UI Inputs (Kini terlihat dan bisa diedit)
            if price:
                self.price_input.setText(price)
                if hasattr(self, 'price_display_lbl'):
                    self.price_display_lbl.setText("Harga:")
                    self.price_display_lbl.setStyleSheet("color: #F59E0B; font-weight: 800; font-size: 13px;")

            if desc:
                self.desc_input.setPlainText(desc)
                if hasattr(self, 'desc_display_lbl'):
                    self.desc_display_lbl.setText("Deskripsi:")
                    self.desc_display_lbl.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 12px;")
            
            if tree_name:
                self.fototree_input.setText(tree_name)
                self._fototree_locked = True
                if hasattr(self, 'fototree_display_lbl'):
                    self.fototree_display_lbl.setText(f"FotoTree: {tree_name}")
                    self.fototree_display_lbl.setStyleSheet("color: #2DD4BF; font-weight: 800; font-size: 13px;")
                
                # USER FIX: Clear Location if Tree exists in setup
                self.location_input.setText("")
                if hasattr(self, 'location_display_lbl'):
                    self.location_display_lbl.setText("Lokasi: (Otomatis dari Setup)")
                    self.location_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")
                    
            elif loc_name:
                self.location_input.setText(loc_name)
                if hasattr(self, 'location_display_lbl'):
                    self.location_display_lbl.setText(f"Lokasi: {loc_name}")
                    self.location_display_lbl.setStyleSheet("color: #10B981; font-weight: 800; font-size: 13px;")
                
                # USER FIX: Clear Tree if Location exists in setup
                self.fototree_input.setText("")
                self._fototree_locked = False
                if hasattr(self, 'fototree_display_lbl'):
                    self.fototree_display_lbl.setText("FotoTree: (Otomatis dari Setup)")
                    self.fototree_display_lbl.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 13px;")

            summary = []
            if tree_name:
                summary.append(f"🌳 {tree_name}")
            elif loc_name:
                summary.append(f"📍 {loc_name}")
            
            status_text = "READY"
            if summary:
                status_text = " | ".join(summary[:2])
            
            self.setup_metadata_status.setText(status_text)
            self._update_mutual_exclusion()
            self.setup_metadata_status.setStyleSheet("""
                QLabel {
                    color: #10B981;
                    background-color: rgba(16, 185, 129, 0.1);
                    border: 1px solid rgba(16, 185, 129, 0.2);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 800;
                }
            """)
            self.btn_setup_metadata.setText("🔄 PERBARUI METADATA")
            self.btn_setup_metadata.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #94A3B8;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    font-weight: 800;
                    font-size: 12px;
                    padding: 8px 16px;
                }
                QPushButton:hover { 
                    background-color: #334155;
                    color: #F8FAFC;
                }
            """)
        else:
            self.setup_metadata_status.setText("PENDING")
            self.setup_metadata_status.setStyleSheet("""
                QLabel {
                    color: #F59E0B;
                    background-color: rgba(245, 158, 11, 0.1);
                    border: 1px solid rgba(245, 158, 11, 0.2);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 800;
                }
            """)
            self.btn_setup_metadata.setText("📖 SETUP METADATA")
            self.btn_setup_metadata.setStyleSheet("""
                QPushButton {
                    background-color: #6366F1;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 900;
                    font-size: 13px;
                    letter-spacing: 0.5px;
                    padding: 10px 20px;
                }
                QPushButton:hover { 
                    background-color: #4F46E5;
                }
                QPushButton:pressed { 
                    background-color: #4338CA;
                }
            """)

        if has_setup:
            self.fototree_status.setText("✅ Foto Tree Terkunci (Sesuai Setup)")
            self.fototree_status.setStyleSheet("color: #A78BFA; font-size: 11px; font-weight: 800;")

    def on_setup_metadata_clicked(self):
        if not self.account_combo.currentText():
            self.show_custom_message("Akun Diperlukan", "Pilih atau tambah akun Fotoyu terlebih dahulu sebelum setup metadata.", "warning")
            return
        self.on_start(login_only=True, setup_metadata_first=True)

    def on_start(self, login_only=False, setup_metadata_first=False):
        try:
            # 0. License Check - Gunakan tipe aplikasi yang sesuai (pro/lite)
            is_valid, status_code, _, _ = check_license(app_type=self.app_type)
            if not is_valid:
                if status_code == "REAGREEMENT_REQUIRED":
                    self.show_custom_message("Update Diperlukan", "Ada pembaruan Ketentuan Layanan. Silakan buka Manajemen Lisensi (ikon kunci) untuk menyetujui ulang.", "warning")
                self.show_license_info()
                return

            # Validation (skip if login_only)
            if not login_only:
                if not self.account_combo.currentText():
                    self.show_custom_message("Akun Diperlukan", "Silakan tambah atau pilih akun Fotoyu terlebih dahulu!", "warning")
                    return
                if not self.path_input.text():
                    self.show_custom_message("Error", "Folder konten belum dipilih!", "error")
                    return
                if not os.path.isdir(self.path_input.text()):
                    self.show_custom_message("Error", "Folder konten tidak ditemukan! Pastikan Kartu SD / USB sudah terhubung.", "error")
                    return
                if not self._has_web_setup_done() and not self._has_setup_metadata():
                    self.show_custom_message("Setup Metadata", "Wajib jalankan LOGIN & SETUP METADATA terlebih dahulu agar metadata diambil dari web.", "warning")
                    return
                if not self.price_input.text():
                    self.show_custom_message("Error", "Harga wajib diisi!", "error")
                    return
                if not self.desc_input.toPlainText():
                    self.show_custom_message("Error", "Deskripsi wajib diisi!", "error")
                    return
                
            # Monitor Kirim Ulang dihapus dari UI

            config = self.get_current_config()
            if not config:
                self.log_message("❌ ERROR: Gagal mengambil konfigurasi UI.")
                return
                
            settings = load_settings() or {}
            # Get current account list from combo
            accounts = [self.account_combo.itemText(i) for i in range(self.account_combo.count())]
            settings.update(config)
            settings["accounts"] = accounts
            
            # Simpan juga ke mode-specific settings
            if "modes" not in settings:
                settings["modes"] = {}
            mode_config = config.copy()
            mode_config.pop('type', None)
            settings["modes"][config['type']] = mode_config
            
            save_settings(settings)
            
            # Prepare config for worker (process location logic)
            worker_config, field_modes = self._prepare_worker_config(login_only=login_only)
            if not worker_config:
                self.log_message("❌ ERROR: Gagal menyiapkan konfigurasi worker.")
                return
            if not login_only:
                self.log_message("🧩 Info: Menggunakan Lokasi & Foto Tree dari hasil Setup sebelumnya.")

            self.start_btn.setEnabled(False)
            self.start_btn.setText("MEMBUKA BROWSER...")
            self.stop_btn.setEnabled(True)
            self.status_val.setText("Berjalan")
            self.status_val.setStyleSheet("color: #10B981; font-weight: 800;")
            
            # Simpan state login_only untuk UI feedback
            self.is_login_only = bool(login_only and not setup_metadata_first)
            self.is_setup_metadata_only = bool(setup_metadata_first)
            if setup_metadata_first:
                worker_config["setup_metadata_first"] = True
                worker_config["setup_metadata_started_at"] = time.time()
            
            if login_only:
                if setup_metadata_first:
                    self.log_message(f"🧩 Persiapan data awal untuk akun: {worker_config.get('current_account')}")
                    self.log_message("👉 Setelah browser terbuka: upload manual 1 foto dengan data lengkap sampai sukses.")
                else:
                    self.log_message(f"🆕 Menambah akun baru. Silakan login di browser.")
            else:
                self.log_message(f"🚀 Memulai otomasi untuk akun: {worker_config.get('current_account')}")
                
            self.start_signal.emit(worker_config)

            # Auto-scroll down to log panel
            QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))
        except Exception as e:
            self.log_message(f"❌ CRITICAL ERROR di on_start: {str(e)}")
            self.reset_ui()

    def on_add_account(self):
        dialog = AddAccountDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        name = dialog.account_name
        if self.account_combo.findText(name) >= 0:
            self.show_custom_message("Info", f"Akun '{name}' sudah ada.")
            return
            
        self.account_combo.blockSignals(True)
        self.account_combo.addItem(name)
        self.account_combo.setCurrentText(name)
        self.account_combo.blockSignals(False)
        
        self.update_account_status(name)
        settings = load_settings() or {}
        accounts = settings.get("accounts") or []
        accounts.append(name)
        settings["accounts"] = accounts
        settings["current_account"] = name
        save_settings(settings)
        
        self.log_message(f"➕ Akun '{name}' ditambahkan. Membuka browser untuk login...")
        
        # Trigger login immediately after adding
        self.on_start(login_only=True)

    def on_remove_account(self):
        name = self.account_combo.currentText()
        if not name:
            self.show_custom_message("Info", "Tidak ada akun untuk dihapus.")
            return
            
        if not self.show_custom_question("Hapus Akun", f"Apakah Anda yakin ingin menghapus akun '{name}'?"):
            return

        idx = self.account_combo.currentIndex()
        self.account_combo.removeItem(idx)
        
        # Delete physical session/account folder
        try:
            import stat
            def on_rm_error(func, path, exc_info):
                # Error handler for shutil.rmtree to handle read-only files
                os.chmod(path, stat.S_IWRITE)
                func(path)

            base_local = get_app_data_dir()
            account_root = os.path.join(base_local, "accounts", name)
            if os.path.exists(account_root):
                shutil.rmtree(account_root, onerror=on_rm_error)
                self.log_message(f"🗑️ Data session (cookies) akun '{name}' telah dihapus permanen.")
        except Exception as e:
            self.log_message(f"⚠️ Gagal menghapus folder data: {e}")

        settings = load_settings() or {}
        accounts = [a for a in (settings.get("accounts") or []) if a != name]
        settings["accounts"] = accounts
        settings["current_account"] = accounts[0] if accounts else ""
        save_settings(settings)
        
        if not accounts:
            self.status_account.setText("Belum ada akun")
            self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;")
        else:
            self.update_account_status(settings["current_account"])

    def on_account_combo_changed(self, new_account):
        if not new_account:
            return
            
        settings = load_settings() or {}
        current_saved_account = settings.get("current_account")
        
        # If it's the same account, do nothing
        if new_account == current_saved_account:
            return
            
        if hasattr(self, '_is_running') and self._is_running:
            if self.show_custom_question(
                "Konfirmasi Restart", 
                f"Engine sedang berjalan dengan akun lain.\n\nEngine akan dihentikan dan restart dengan akun '{new_account}'.\n\nLanjutkan?"
            ):
                self.on_stop()
                self.update_account_status(new_account)
                settings["current_account"] = new_account
                save_settings(settings)
                # Refresh setup metadata UI for new account
                self._refresh_setup_metadata_ui()
                self.reset_ui()
                self.update_failed_badge()
                self.log_message(f"✅ Akun diganti ke: {new_account}. Silakan jalankan ulang.")
            else:
                # Revert selection without triggering signal again
                self.account_combo.blockSignals(True)
                self.account_combo.setCurrentText(current_saved_account)
                self.account_combo.blockSignals(False)
                return
        else:
            self.update_account_status(new_account)
            settings["current_account"] = new_account
            save_settings(settings)
            self._refresh_setup_metadata_ui()
            self.update_failed_badge()
            self.log_message(f"✅ Akun diganti ke: {new_account}")

    def _save_current_settings(self):
        """Helper to save current UI state to settings file properly (including accounts and modes)"""
        try:
            config = self.get_current_config()
            settings = load_settings() or {}
            
            # Get current account list from combo box
            accounts = [self.account_combo.itemText(i) for i in range(self.account_combo.count())]
            
            # Update global settings
            settings.update(config)
            settings["accounts"] = accounts
            
            # Save to mode-specific settings
            if "modes" not in settings:
                settings["modes"] = {}
            mode_config = config.copy()
            mode_config.pop('type', None)
            settings["modes"][config['type']] = mode_config
            
            save_settings(settings)
            return settings
        except Exception as e:
            print(f"Error saving settings: {e}")
            return None

    def _load_job_config_from_folder(self, folder_path):
        """Mencoba memuat konfigurasi pekerjaan sebelumnya dari tracker JSON"""
        try:
            folder_path = os.path.abspath(folder_path)
            if folder_path.endswith(':'): folder_path += os.sep
            
            # 1. Cek AppData Tracker
            import hashlib
            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()[:12]
            if sys.platform == 'darwin':
                base_local = os.path.expanduser("~/Library/Application Support/AutoYuPro")
            else:
                base_local = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
            tracker_file = os.path.join(base_local, "trackers", f"tracker_{folder_hash}.json")
            
            # 2. Cek Local Tracker as fallback
            if not os.path.exists(tracker_file):
                tracker_file = os.path.join(folder_path, ".upload_tracker.json")

            if os.path.exists(tracker_file):
                with open(tracker_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and '__job_config__' in data:
                        job_config = data['__job_config__']
                        
                        # Apply to UI with signals blocked to prevent recursion
                        self.radio_foto.blockSignals(True)
                        self.radio_video.blockSignals(True)
                        self.tabs_spin.blockSignals(True)
                        self.batch_spin.blockSignals(True)
                        
                        if job_config.get('type'):
                            if job_config['type'] == 'video':
                                self.radio_video.setChecked(True)
                                self.radio_foto.setChecked(False)
                            else:
                                self.radio_foto.setChecked(True)
                                self.radio_video.setChecked(False)
                        
                        if job_config.get('tabs'):
                            self.tabs_spin.setValue(job_config['tabs'])
                        
                        if job_config.get('batch_size'):
                            self.batch_spin.setValue(job_config['batch_size'])
                            
                        self.radio_foto.blockSignals(False)
                        self.radio_video.blockSignals(False)
                        self.tabs_spin.blockSignals(False)
                        self.batch_spin.blockSignals(False)
                        
                        if job_config.get('price'):
                            self.price_input.setText(str(job_config['price']))
                            
                        if job_config.get('desc'):
                            self.desc_input.setText(job_config['desc'])
                            
                        if job_config.get('fototree'):
                            self.fototree_input.setText(job_config['fototree'])
                            
                        if job_config.get('location'):
                            self.location_input.setText(job_config['location'])
                            
                        self.log_message(f"ℹ️ Pengaturan sebelumnya untuk folder ini berhasil dimuat.")
                        
                        # Trigger manual updates that were blocked
                        self.update_media_status("VIDEO" if self.radio_video.isChecked() else "FOTO")
                        return True
        except Exception as e:
            print(f"Error loading job config: {e}")
        return False

    def on_retry_failed(self):
        is_valid, status_code, _, _ = check_license()
        if not is_valid:
            if status_code == "REAGREEMENT_REQUIRED":
                self.show_custom_message("Update Diperlukan", "Ada pembaruan Ketentuan Layanan. Silakan buka Manajemen Lisensi (ikon kunci) untuk menyetujui ulang.", "warning")
            self.show_license_info()
            return
        base_folder = self.path_input.text()
        if not base_folder or not os.path.isdir(base_folder):
            self.show_custom_message("Error", "Folder konten belum dipilih!", "error")
            return

        is_sd_mode = self.radio_src_sd.isChecked()
        tracker_failed = self._count_failed_files_from_tracker(base_folder)
        local_tracker_failed = self._count_failed_files_from_local_tracker(base_folder)
        physical_failed = self._count_failed_files(base_folder)
        count = max(physical_failed, tracker_failed, local_tracker_failed)
        if count == 0:
            self.show_custom_message(
                "Info",
                "Tidak ada file gagal yang terdeteksi untuk dilanjutkan.\n\n"
                "AutoYu akan otomatis mendeteksi file yang belum selesai.\n"
                "Jika sebelumnya aplikasi hang/crash, jalankan ulang 1x lalu coba tombol ini lagi.",
                "info"
            )
            self.update_failed_badge()
            return
            
        # FIX: Load previous job config if available to ensure it follows previous settings (tabs/type)
        self._load_job_config_from_folder(base_folder)
            
        # FIX: Save settings properly instead of overwriting with partial config
        self._save_current_settings()
        
        worker_config, _ = self._prepare_worker_config(retry_failed_only=True)
        if not worker_config:
            self.log_message("❌ ERROR: Gagal menyiapkan konfigurasi worker.")
            return
        try:
            self.log_message(f"🔄 Melanjutkan {count} file yang belum selesai.")
        except Exception:
            pass
        self.start_btn.setEnabled(False)
        self.start_btn.setText("MEMBUKA BROWSER...")
        self.stop_btn.setEnabled(True)
        self.status_val.setText("Berjalan")
        self.status_val.setStyleSheet("color: #10B981; font-weight: 800;")
        self.start_signal.emit(worker_config)

        # Auto-scroll down to log panel
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def on_continue_failed_from_popup(self):
        base_folder = self.path_input.text()
        if not base_folder or not os.path.isdir(base_folder):
            self.show_custom_message("Error", "Folder konten belum dipilih!", "error")
            return

        is_sd_mode = self.radio_src_sd.isChecked()
        tracker_failed = self._count_failed_files_from_tracker(base_folder)
        local_tracker_failed = self._count_failed_files_from_local_tracker(base_folder)
        physical_failed = self._count_failed_files(base_folder)
        count = max(physical_failed, tracker_failed, local_tracker_failed)
        if count == 0:
            self.show_custom_message(
                "Info",
                "Tidak ada file gagal yang terdeteksi untuk dilanjutkan.\n\n"
                "AutoYu akan otomatis mendeteksi file yang belum selesai.",
                "info"
            )
            self.update_failed_badge()
            return
            
        # FIX: Load previous job config if available to ensure it follows previous settings (tabs/type)
        self._load_job_config_from_folder(base_folder)
            
        # FIX: Save settings properly instead of overwriting with partial config
        self._save_current_settings()
        
        worker_config, _ = self._prepare_worker_config(retry_failed_only=True)
        if not worker_config:
            self.log_message("❌ ERROR: Gagal menyiapkan konfigurasi worker.")
            return
        self.start_btn.setEnabled(False)
        self.start_btn.setText("MEMBUKA BROWSER...")
        self.stop_btn.setEnabled(True)
        self.status_val.setText("Berjalan")
        self.status_val.setStyleSheet("color: #10B981; font-weight: 800;")
        self.start_signal.emit(worker_config)

        # Auto-scroll down to log panel
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def _count_failed_files(self, base_dir):
        try:
            # Sesuaikan ekstensi dengan tipe yang dipilih (foto/video)
            if self.radio_video.isChecked():
                exts = ('.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm')
            else:
                exts = ('.jpg', '.jpeg', '.png')
                
            count = 0
            for root, dirs, files in os.walk(base_dir):
                if os.path.basename(root).lower() == 'failed':
                    count += len([f for f in files if f.lower().endswith(exts)])
            return count
        except Exception:
            return 0

    def _count_failed_files_from_tracker(self, folder_path):
        """Menghitung jumlah file gagal dari JSON tracker (khusus Mode FULL)"""
        try:
            import hashlib
            import json
            folder_path = os.path.abspath(folder_path)
            if folder_path.endswith(':'): folder_path += os.sep
            
            # Normalisasi path untuk hash agar case-insensitive di Windows (Sama dengan automation.py)
            hash_path = folder_path
            if os.name == 'nt':
                hash_path = hash_path.lower()
                
            folder_hash = hashlib.md5(hash_path.encode()).hexdigest()[:12]
            
            if sys.platform == 'darwin':
                base_local = os.path.expanduser("~/Library/Application Support/AutoYuPro")
            else:
                base_local = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
            
            tracker_file = os.path.join(base_local, "trackers", f"tracker_{folder_hash}.json")
            
            if os.path.exists(tracker_file):
                try:
                    with open(tracker_file, 'r', encoding='utf-8') as f:
                        tracking_data = json.load(f) or {}
                    if isinstance(tracking_data, dict):
                        return sum(1 for v in tracking_data.values() if isinstance(v, dict) and v.get('status') in ('failed', 'pending'))
                except Exception:
                    bak = tracker_file + ".bak"
                    if os.path.exists(bak):
                        with open(bak, 'r', encoding='utf-8') as f:
                            tracking_data = json.load(f) or {}
                        if isinstance(tracking_data, dict):
                            return sum(1 for v in tracking_data.values() if isinstance(v, dict) and v.get('status') in ('failed', 'pending'))
        except:
            pass
        return 0

    def _count_failed_files_from_local_tracker(self, folder_path):
        try:
            folder_path = os.path.abspath(folder_path)
            if folder_path.endswith(':'): 
                folder_path += os.sep
            tracker_file = os.path.join(folder_path, ".upload_tracker.json")
            if os.path.exists(tracker_file):
                try:
                    with open(tracker_file, 'r', encoding='utf-8') as f:
                        tracking_data = json.load(f) or {}
                    if isinstance(tracking_data, dict):
                        return sum(1 for v in tracking_data.values() if isinstance(v, dict) and v.get('status') in ('failed', 'pending'))
                except Exception:
                    bak = tracker_file + ".bak"
                    if os.path.exists(bak):
                        with open(bak, 'r', encoding='utf-8') as f:
                            tracking_data = json.load(f) or {}
                        if isinstance(tracking_data, dict):
                            return sum(1 for v in tracking_data.values() if isinstance(v, dict) and v.get('status') in ('failed', 'pending'))
        except Exception:
            pass
        return 0

    def update_failed_badge(self):
        folder_path = self.path_input.text()
        if not folder_path or not os.path.isdir(folder_path):
            count = 0
        else:
            # Selalu gunakan tracker (Appdata atau Lokal) sebagai sumber utama
            tracker_failed = self._count_failed_files_from_tracker(folder_path)
            local_tracker_failed = self._count_failed_files_from_local_tracker(folder_path)
            # Fallback fisik tetap ada untuk transisi dari versi lama
            physical_failed = self._count_failed_files(folder_path)
            count = max(tracker_failed, local_tracker_failed, physical_failed)

        if count > 0:
            self.retry_failed_btn.setEnabled(True)
            self.retry_failed_btn.setText(f"LANJUTKAN SISA ({count})")
        else:
            self.retry_failed_btn.setEnabled(False)
            self.retry_failed_btn.setText("LANJUTKAN SISA")

    def on_stop(self):
        self.stop_signal.emit()
        self.stop_btn.setEnabled(False)
        self.status_val.setText("Berhenti...")
        self.status_val.setStyleSheet("color: #F43F5E; font-weight: 800;")
        self.log_message("Menghentikan engine... menunggu batch selesai.")

    def handle_license_error(self):
        """Called when worker detects license error"""
        self.reset_ui()
        self.show_custom_message("Lisensi Bermasalah", "Lisensi tidak aktif atau tidak valid.\n\nSilakan aktivasi lisensi untuk menggunakan software ini.", "warning")
        self.show_license_info()

    def handle_browser_disconnected(self):
        self.reset_ui()
        msg = "Browser/Tab otomasi terputus atau ditutup."
        self.log_message(f"⚠️ <b>Status:</b> {msg}")
        # HILANGKAN POPUP sesuai permintaan user (Ultra Stealth Mode)
        # self.show_custom_message("Browser Terputus", msg, "warning")

    def on_login_confirmed(self):
        self.login_confirm_btn.setVisible(False)
        self.start_btn.setText("OTOMASI BERJALAN")
        self.start_btn.setStyleSheet("background-color: #10B981; color: white;") # Green for ready
        self.continue_signal.emit()

    def on_login_success(self):
        """Called when system detects login automatically"""
        self.login_confirm_btn.setVisible(False)
        
        # Cek apakah ini mode tambah akun (login_only)
        is_login_only = getattr(self, 'is_login_only', False)
        
        if is_login_only:
            self.start_btn.setText("AKUN BERHASIL DISIAPKAN")
            self.start_btn.setStyleSheet("background-color: #10B981; color: white;")
            self.log_message("✅ <b>SUKSES:</b> Login terdeteksi! Akun baru berhasil ditambahkan dan siap digunakan.")
            # HILANGKAN POPUP sesuai permintaan user
            # self.show_custom_message("Berhasil", f"Akun '{self.account_combo.currentText()}' berhasil ditambahkan dan siap digunakan!", "info")
            # Penting: Reset flag agar tidak muncul lagi jika worker lama masih mengirim sinyal
            self.is_login_only = False 
        else:
            self.start_btn.setText("OTOMASI BERJALAN")
            self.start_btn.setStyleSheet("background-color: #10B981; color: white;") # Green for ready
            self.log_message("✨ <b>Status:</b> Sudah Login, Siap Upload!")

    def set_login_mode(self, active):
        if active:
            self.login_confirm_btn.setVisible(True)
            
            if getattr(self, 'is_login_only', False):
                self.login_confirm_btn.setText("SAYA SUDAH LOGIN (KLIK JIKA TIDAK OTOMATIS)")
                self.start_btn.setText("MENYIAPKAN AKUN...")
                self.start_btn.setStyleSheet("background-color: #6366F1; color: white;") # Purple for process
                self.log_message("🔑 <b>MODE TAMBAH AKUN:</b> Browser telah terbuka.")
                self.log_message("👉 <b>Langkah:</b> Silakan Login di browser. Aplikasi akan mendeteksi secara otomatis.")
                self.log_message("💡 <i>Tips: Jika sudah login tapi tidak terdeteksi, klik tombol biru 'SAYA SUDAH LOGIN' di bawah.</i>")
            else:
                self.login_confirm_btn.setText("LANJUTKAN")
                self.start_btn.setText("SILAKAN LOGIN...")
                self.start_btn.setStyleSheet("background-color: #F59E0B; color: white;") # Orange for waiting
                self.log_message("⚠️ <b>STATUS:</b> Menunggu Login.")
                self.log_message("👉 Silakan login manual di browser, lalu klik <b>'LANJUTKAN'</b>.")
        else:
            self.login_confirm_btn.setVisible(False)

    def reset_ui(self):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("JALANKAN OTOMASI")
        self.start_btn.setStyleSheet("") # Reset to default stylesheet class
        self.stop_btn.setEnabled(False)
        self.status_val.setText("Terhubung")
        self.status_val.setStyleSheet("color: #94A3B8; font-weight: 700;")
        # Refresh failed badge after engine finishes
        self.update_failed_badge()
        self._refresh_setup_metadata_ui()
        # Hide progress card after some delay or keep it to show result
        # self.progress_card.setVisible(False)
        self._eta_start_time = None
        self._eta_base_completed = 0
        self._eta_base_progress = 0
        if hasattr(self, "progress_eta"):
            self.progress_eta.setText("Perkiraan: —")
            
        # Auto-scroll to top
        if hasattr(self, "scroll_area"):
            self.scroll_area.verticalScrollBar().setValue(0)

    def show_license_info(self):
        """Shows License Status and Activation Dialog."""
        dlg = LicenseDialog(self, app_type=self.app_type)
        dlg.exec()
        self.login_confirm_btn.setVisible(False)

    def _format_bytes(self, b):
        gb = b / (1024 * 1024 * 1024)
        return f"{gb:.1f} GB"

    def _get_ram_usage(self):
        try:
            import platform
            if platform.system() == "Windows":
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                total = stat.ullTotalPhys
                avail = stat.ullAvailPhys
                used = total - avail
                percent = int(stat.dwMemoryLoad)
                return percent, used, total
            else:
                # macOS / Linux / Unix
                import os
                import subprocess
                try:
                    # Coba gunakan psutil jika tersedia (paling akurat & cross-platform)
                    try:
                        import psutil
                        vm = psutil.virtual_memory()
                        return int(vm.percent), vm.used, vm.total
                    except ImportError:
                        pass

                    # Fallback 1: os.sysconf
                    total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
                    
                    # Fallback 2: sysctl (macOS specific)
                    if total <= 0:
                        cmd = ["sysctl", "-n", "hw.memsize"]
                        total = int(subprocess.check_output(cmd).decode().strip())
                    
                    # Untuk macOS, coba dapatkan used memory via vm_stat jika psutil tidak ada
                    used = 0
                    percent = 0
                    if sys.platform == "darwin":
                        try:
                            # vm_stat memberikan info page count
                            vm_output = subprocess.check_output(["vm_stat"]).decode()
                            pagesize = int(subprocess.check_output(["sysctl", "-n", "hw.pagesize"]).decode())
                            
                            vm_dict = {}
                            for line in vm_output.split('\n')[1:]: # Skip header
                                if ':' in line:
                                    key, val = line.split(':')
                                    vm_dict[key.strip()] = int(val.strip().replace('.', ''))
                            
                            # Used = (Active + Inactive + Wired) * pagesize
                            active = vm_dict.get('Pages active', 0) * pagesize
                            wired = vm_dict.get('Pages wired down', 0) * pagesize
                            used = active + wired
                            percent = int((used / total) * 100) if total > 0 else 0
                        except:
                            pass

                    return percent, used, total 
                except:
                    return None
        except Exception:
            return None

    def _update_ram_status(self):
        res = self._get_ram_usage()
        if res is None:
            if hasattr(self, "status_ram"):
                self.status_ram.setText("—")
            return
        percent, used, total = res
        if hasattr(self, "status_ram"):
            self.status_ram.setText(f"{percent}% ({self._format_bytes(used)}/{self._format_bytes(total)})")

    def detect_system_specs(self):
        """Detect system specs: RAM, CPU cores, OS type"""
        try:
            import platform
            import multiprocessing
            
            # Get RAM info
            ram_info = self._get_ram_usage()
            total_ram_gb = 0
            if ram_info:
                _, _, total_bytes = ram_info
                total_ram_gb = total_bytes / (1024**3)
            
            # Get CPU cores
            cpu_cores = multiprocessing.cpu_count()
            
            # Get OS info
            system = platform.system()
            if system == "Windows":
                os_name = "Windows"
                os_version = platform.release()
            elif system == "Darwin":
                os_name = "macOS"
                os_version = platform.mac_ver()[0]
            elif system == "Linux":
                os_name = "Linux"
                os_version = platform.release()
            else:
                os_name = system
                os_version = platform.release()
            
            return {
                "os": f"{os_name} {os_version}",
                "ram_gb": round(total_ram_gb, 1),
                "cpu_cores": cpu_cores
            }
        except Exception:
            return None

    def show_custom_message(self, title, message, icon_type="info"):
        """Show custom styled message box with dark theme"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        
        if icon_type == "warning":
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #1E293B;
                    border: 1px solid #EF4444;
                    border-radius: 8px;
                }
                QLabel {
                    color: #E2E8F0;
                    font-size: 14px;
                    font-weight: 500;
                    padding: 10px;
                }
                QPushButton {
                    background-color: #EF4444;
                    color: white;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
            """)
        elif icon_type == "error":
            msg.setIcon(QMessageBox.Critical)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #1E293B;
                    border: 1px solid #EF4444;
                    border-radius: 8px;
                }
                QLabel {
                    color: #E2E8F0;
                    font-size: 14px;
                    font-weight: 500;
                    padding: 10px;
                }
                QPushButton {
                    background-color: #EF4444;
                    color: white;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
            """)
        else:  # info
            msg.setIcon(QMessageBox.Information)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #1E293B;
                    border: 1px solid #6366F1;
                    border-radius: 8px;
                }
                QLabel {
                    color: #E2E8F0;
                    font-size: 14px;
                    font-weight: 500;
                    padding: 10px;
                }
                QPushButton {
                    background-color: #6366F1;
                    color: white;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4F46E5;
                }
            """)
        
        msg.exec()

    def show_custom_question(self, title, message):
        """Show custom styled question box with dark theme and returns True if Yes"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1E293B;
                border: 1px solid #6366F1;
                border-radius: 8px;
            }
            QLabel {
                color: #E2E8F0;
                font-size: 14px;
                font-weight: 500;
                padding: 10px;
            }
            QPushButton {
                background-color: #334155;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton[text="Yes"], QPushButton[text="&Yes"] {
                background-color: #6366F1;
            }
            QPushButton[text="Yes"]:hover, QPushButton[text="&Yes"]:hover {
                background-color: #4F46E5;
            }
        """)
        
        res = msg.exec()
        return res == QMessageBox.Yes

    def check_for_updates(self):
        """Mengecek update di background thread"""
        self.update_thread = UpdateCheckThread()
        self.update_thread.update_available_signal.connect(self.handle_update_found)
        self.update_thread.start()

    def handle_update_found(self, data):
        """Menangani jika ada update baru yang ditemukan"""
        latest_version = data.get("version", "0.0.0")
        download_url = data.get("download_url", "https://pramana.web.id/update/autoyu")
        changelog = data.get("changelog", "Tidak ada catatan perubahan.")
        
        msg = f"Update baru AutoYu v{latest_version} telah tersedia!\n\n"
        msg += f"Apa yang baru:\n{changelog}\n\n"
        msg += "Apakah Anda ingin mendownload update sekarang?"
        
        if self.show_custom_question("Update Tersedia", msg):
            QDesktopServices.openUrl(QUrl(download_url))

    def get_optimal_config(self, total_files):
        """Get optimal config based on system specs and Photographer Best Practices (250/tab)"""
        specs = self.detect_system_specs()
        is_foto = self.radio_foto.isChecked()
        
        if not specs:
            return {"tabs": 4, "batch": 250 if is_foto else 25, "mode": "SAFE"}
        
        ram_gb = specs["ram_gb"]
        
        # Photographer Best Practice: 250 photos per tab is the most stable
        # We adjust max tabs based on RAM to prevent system freeze
        if is_foto:
            base_batch = 250
            if ram_gb <= 4:
                max_tabs = 2
            elif ram_gb <= 8:
                max_tabs = 6
            elif ram_gb <= 16:
                max_tabs = 12
            elif ram_gb <= 32:
                max_tabs = 20
            else:
                max_tabs = 30
            return {"tabs": max_tabs, "batch": base_batch, "mode": "SAFE"}
        else:
            # Video Best Practice: 25 per tab
            base_batch = 25
            if ram_gb <= 4:
                max_tabs = 1
            elif ram_gb <= 8:
                max_tabs = 4
            elif ram_gb <= 16:
                max_tabs = 8
            else:
                max_tabs = 12
            return {"tabs": max_tabs, "batch": base_batch, "mode": "SAFE"}

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
