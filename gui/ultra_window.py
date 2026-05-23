
import sys
import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                                QLabel, QLineEdit, QPushButton, QTextEdit, 
                                QFileDialog, QFrame, QProgressBar, QComboBox, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QColor
from gui.main_window import (MainWindow, FOTOYU_STYLESHEET, load_settings, 
                             save_settings, check_license, AUTO_YU_VERSION)
from core.ultra_worker import UltraWorker

ULTRA_STYLESHEET = FOTOYU_STYLESHEET + """
    QMainWindow { background-color: #0F172A; }
    .ultra_card {
        background-color: #1E293B;
        border: 2px solid #7C3AED;
        border-radius: 12px;
    }
    .ultra_title {
        color: #F472B6;
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 2px;
    }
    .ultra_btn {
        background: linear-gradient(135deg, #7C3AED 0%, #EC4899 100%);
        background-color: #7C3AED;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
    }
    .ultra_btn:hover { background-color: #6D28D9; border: 1px solid #F472B6; }
    .status_badge {
        background-color: #334155;
        color: #38BDF8;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 11px;
    }
"""

class UltraWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self.app_type = "pro"
        self.is_running = False
        self.setWindowTitle(f"AutoYu ULTRA (v{AUTO_YU_VERSION})")
        self.setStyleSheet(ULTRA_STYLESHEET)
        
        # Override UI to be more "Ultra"
        self._setup_ultra_ui()
        self._make_ultra_compact()
        self.update_token_status()
        self.btn_setup.clicked.connect(self._on_ultra_setup_clicked)
        try:
            self.start_btn.clicked.connect(self._on_ultra_start_clicked)
        except Exception:
            pass

    def _setup_ultra_ui(self):
        # Update Header
        for label in self.findChildren(QLabel):
            if "AutoYu" in label.text() and label.property("class") == "header_logo":
                label.setText("AutoYu ULTRA")
                label.setStyleSheet("color: #F472B6; font-size: 28px; font-weight: 900;")
        
        # Tambahkan Badge "ULTRA PERFORMANCE"
        api_badge = QLabel("⚡ ULTRA PERFORMANCE")
        api_badge.setProperty("class", "status_badge")
        # Cari header layout
        header = self.findChild(QFrame, "header_panel")
        if header:
            header.layout().insertWidget(2, api_badge)

    def update_token_status(self):
        # Simulasi cek token
        worker = UltraWorker(self.get_current_config() or {})
        token = worker.get_token()
        
        if token:
            self.status_account.setText("🔑 Token Active")
            self.status_account.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            self.status_account.setText("⚠️ Token Missing")
            self.status_account.setStyleSheet("color: #EF4444; font-weight: bold;")

    def _on_ultra_start_clicked(self):
        try:
            self.log_message("🟣 ULTRA: Tombol LAUNCH diklik.")
        except Exception:
            pass

    def _on_ultra_add_account_clicked(self):
        try:
            self.log_message("🟣 ULTRA: Tombol Tambah Akun diklik.")
        except Exception:
            pass
        self._ensure_ultra_account_selected()

    def _ensure_ultra_account_selected(self):
        try:
            current = str(self.account_combo.currentText() or "").strip()
        except Exception:
            current = ""
        if current:
            return True

        try:
            settings = load_settings() or {}
        except Exception:
            settings = {}
        accounts = settings.get("accounts") or []
        accounts = [str(a) for a in accounts if str(a).strip()]

        base_name = "ULTRA"
        name = base_name
        counter = 1
        while name in accounts or (self.account_combo.findText(name) >= 0):
            counter += 1
            name = f"{base_name}-{counter}"

        try:
            self.account_combo.blockSignals(True)
            self.account_combo.addItem(name)
            self.account_combo.setCurrentText(name)
            self.account_combo.blockSignals(False)
        except Exception:
            return False

        try:
            accounts.append(name)
            settings["accounts"] = accounts
            settings["current_account"] = name
            save_settings(settings)
        except Exception:
            pass

        try:
            self.update_account_status(name)
        except Exception:
            pass

        try:
            self.log_message(f"✅ Akun dibuat otomatis: {name}")
        except Exception:
            pass

        return True

    def _on_ultra_setup_clicked(self):
        try:
            self.log_message("🟣 ULTRA: Tombol LOGIN & SETUP METADATA diklik.")
        except Exception:
            pass
        try:
            self.on_start(login_only=True)
        except Exception as e:
            try:
                self.log_message(f"❌ ULTRA: Error saat setup: {str(e)}")
            except Exception:
                pass

    def _stop_current_ultra_job(self):
        try:
            w = getattr(self, "worker", None)
        except Exception:
            w = None
        if not w:
            return
        try:
            if hasattr(w, "stop"):
                w.stop()
        except Exception:
            pass
        try:
            if hasattr(w, "quit"):
                w.quit()
        except Exception:
            pass
        try:
            if hasattr(w, "wait"):
                w.wait(2000)
        except Exception:
            pass

    def _make_ultra_compact(self):
        """Menyederhanakan GUI Ultra: Standalone & Pro Workflow."""
        # 1. Ukuran Jendela Compact
        self.setMinimumSize(850, 600)
        self.resize(900, 650)

        # 2. Sembunyikan semua elemen yang tidak perlu (SANGAT BERSIH)
        for i in range(self.content_layout.count()):
            w = self.content_layout.itemAt(i).widget()
            if isinstance(w, QFrame) and w.property("class") == "card":
                title_label = w.findChild(QLabel)
                if title_label:
                    title_text = title_label.text().upper()
                    # SEMBUNYIKAN: Mode Unggahan & Konfigurasi Sistem (karena kita akan susun ulang)
                    if "MODE UNGGAHAN" in title_text or "KONFIGURASI SISTEM" in title_text:
                        w.setVisible(False)

        # 3. Buat Panel Input Baru yang Mandiri & Ringkas
        self.ultra_form = QFrame()
        self.ultra_form.setStyleSheet("background-color: #1E293B; border-radius: 12px; border: 1px solid #334155;")
        form_layout = QGridLayout(self.ultra_form)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)

        # Row 0: Akun & Tombol Setup
        lbl_acc = QLabel("👤 Akun Fotoyu:")
        lbl_acc.setStyleSheet("color: #94A3B8; font-weight: bold; border: none;")
        self.btn_add_account_ultra = QPushButton("➕ Tambah Akun")
        self.btn_add_account_ultra.setStyleSheet("""
            QPushButton {
                background-color: #0F172A;
                color: #38BDF8;
                border: 1px solid #334155;
                padding: 8px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { border: 1px solid #38BDF8; }
        """)
        self.btn_add_account_ultra.clicked.connect(self._on_ultra_add_account_clicked)

        self.btn_setup = QPushButton("🔑 LOGIN & SETUP METADATA")
        self.btn_setup.setStyleSheet("""
            QPushButton {
                background-color: #0F172A;
                color: #F472B6;
                border: 2px dashed #F472B6;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F472B6; color: white; }
        """)
        
        form_layout.addWidget(lbl_acc, 0, 0)
        form_layout.addWidget(self.account_combo, 0, 1)
        form_layout.addWidget(self.btn_add_account_ultra, 0, 2)
        form_layout.addWidget(self.btn_setup, 0, 3)

        # Row 1: Folder
        lbl_folder = QLabel("📁 Folder Foto:")
        lbl_folder.setStyleSheet("color: #94A3B8; font-weight: bold; border: none;")
        form_layout.addWidget(lbl_folder, 1, 0)
        form_layout.addWidget(self.path_input, 1, 1)
        
        # Action buttons for folder
        folder_btn_layout = QHBoxLayout()
        folder_btn_layout.addWidget(self.browse_btn)
        folder_btn_layout.addWidget(self.reset_tracker_btn)
        form_layout.addLayout(folder_btn_layout, 1, 2, 1, 2)

        # Row 2: Harga & Deskripsi
        lbl_price = QLabel("💰 Harga Konten:")
        lbl_price.setStyleSheet("color: #94A3B8; font-weight: bold; border: none;")
        form_layout.addWidget(lbl_price, 2, 0)
        form_layout.addWidget(self.price_input, 2, 1, 1, 2)

        lbl_desc = QLabel("📝 Deskripsi:")
        lbl_desc.setStyleSheet("color: #94A3B8; font-weight: bold; border: none;")
        form_layout.addWidget(lbl_desc, 3, 0)
        form_layout.addWidget(self.desc_input, 3, 1, 1, 2)

        # Masukkan form baru ke layout utama (di atas log)
        self.content_layout.insertWidget(0, self.ultra_form)

        # 4. Sembunyikan Helper & Elemen Sisa
        for attr in ['engine_helper', 'upload_helper', 'auto_helper', 'manual_helper', 'example_label', 'dynamic_helper']:
            if hasattr(self, attr): getattr(self, attr).setVisible(False)
        
        # 5. Fokuskan Log Panel
        if hasattr(self, 'log_text'):
            self.log_text.setMinimumHeight(150)
            self.log_text.setStyleSheet("""
                QTextEdit {
                    background-color: #020617; 
                    color: #2DD4BF; 
                    font-family: 'Consolas'; 
                    font-size: 11px;
                    border: 1px solid #1E293B;
                    padding: 10px;
                }
            """)

        # 6. Tombol Jalankan Gradient
        if hasattr(self, 'start_btn'):
            self.start_btn.setFixedHeight(55)
            self.start_btn.setText("🚀 LAUNCH ULTRA ENGINE")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7C3AED, stop:1 #EC4899);
                    color: white;
                    font-size: 16px;
                    font-weight: 900;
                    border-radius: 12px;
                }
                QPushButton:hover { border: 2px solid white; }
            """)

        # Sembunyikan status bar
        if self.findChild(QFrame, "status_bar"):
            self.findChild(QFrame, "status_bar").setVisible(False)

        self.log_message("✅ <b>AUTO YU ULTRA STANDALONE</b>: Siap digunakan.")

    def on_start(self, login_only=False):
        try:
            if self.is_running and not login_only:
                self.log_message("🛑 ULTRA: Menghentikan proses yang sedang berjalan...")
                self._stop_current_ultra_job()
                self.on_finished()
                return

            config = self.get_current_config()
            if not config: 
                self.log_message("❌ Gagal mengambil konfigurasi.")
                return

            if login_only:
                if not config.get("current_account"):
                    if not self._ensure_ultra_account_selected():
                        self.log_message("❌ ULTRA: Gagal menyiapkan akun.")
                        return
                    config = self.get_current_config() or config
                self.log_text.clear()
                self.log_message("🌐 <b>MEMBUKA SETUP BROWSER...</b>")
                self.log_message("1. Silakan Login di jendela browser yang muncul.")
                self.log_message("2. <b>PENTING</b>: Upload 1 foto manual sampai sukses.")
                self.log_message("3. Setelah sukses, token akan tersimpan otomatis.")
                
                from core.worker import AutomationWorker
                self.worker = AutomationWorker(config)
                self.worker.config["login_only"] = True
                self.worker.config["setup_ultra"] = True
                self.worker.log_signal.connect(self.log_message)
                self.worker.finished_signal.connect(self.on_finished)
                self.is_running = True
                self.btn_setup.setText("⏳ PROSES SETUP...")
                self.worker.start()
                return

            tmp_worker = UltraWorker(config)
            if not tmp_worker.get_token():
                self.log_text.clear()
                self.log_message("❌ <b>Token belum ada.</b>")
                self.log_message("Klik <b>LOGIN & SETUP METADATA</b>, lalu upload manual 1 file sampai berhasil.")
                self.update_token_status()
                return

            # MODE ULTRA: Upload via API
            self.log_text.clear()
            self.log_message("🚀 <b>MENGAKTIFKAN ENGINE ULTRA...</b>")
            
            self.worker = UltraWorker(config)
            self.worker.log_signal.connect(self.log_message)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.fallback_signal.connect(self._on_ultra_fallback_required)
            self.worker.finished_signal.connect(self.on_finished)
            
            self.is_running = True
            self._last_ultra_config = config
            self.start_btn.setText("🛑 STOP ULTRA ENGINE")
            self.start_btn.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold; border-radius: 12px;")
            
            QTimer.singleShot(200, self.worker.start)
        except Exception as e:
            try:
                self.log_message(f"❌ ULTRA: CRITICAL di on_start: {str(e)}")
            except Exception:
                pass

    def _on_ultra_fallback_required(self, reason):
        try:
            if not getattr(self, "is_running", False):
                return
        except Exception:
            return
        try:
            self.log_message("⚠️ ULTRA: Direct API ditolak server. Beralih ke Engine Browser (lebih stabil).")
        except Exception:
            pass

        cfg = getattr(self, "_last_ultra_config", None) or (self.get_current_config() or {})
        if not cfg:
            self.log_message("❌ ULTRA: Gagal ambil konfigurasi untuk fallback.")
            self.on_finished()
            return

        try:
            from core.worker import AutomationWorker
            self.worker = AutomationWorker(cfg)
            self.worker.log_signal.connect(self.log_message)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_finished)
            self.is_running = True
            self.start_btn.setText("🛑 STOP (BROWSER)")
            self.start_btn.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold; border-radius: 12px;")
            QTimer.singleShot(200, self.worker.start)
        except Exception as e:
            try:
                self.log_message(f"❌ ULTRA: Fallback gagal: {str(e)}")
            except Exception:
                pass
            self.on_finished()

    def on_finished(self):
        self.is_running = False
        if hasattr(self, 'btn_setup'): self.btn_setup.setText("🔑 LOGIN & SETUP METADATA")
        self.start_btn.setText("🚀 LAUNCH ULTRA ENGINE")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7C3AED, stop:1 #EC4899);
                color: white;
                font-size: 16px;
                font-weight: 900;
                border-radius: 12px;
            }
            QPushButton:hover { border: 2px solid white; }
        """)
        self.update_token_status()
        self.log_message("🏁 Engine Selesai.")
