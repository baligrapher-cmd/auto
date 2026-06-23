
import sys
import os
import json
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                                QLabel, QLineEdit, QPushButton, QRadioButton, 
                                QTextEdit, QSpinBox, QFileDialog, QFrame, 
                                QGridLayout, QProgressBar, QComboBox)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtMultimedia import QSoundEffect

# Import components from the original main_window
from gui.main_window import (MainWindow, DragDropLineEdit, FOTOYU_STYLESHEET, 
                             load_settings, save_settings, check_license, AUTO_YU_VERSION)
from core.state_machine import UploadMode

class LiteWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self.app_type = "lite"
        self.setWindowTitle(f"AutoYu V3 LITE (v{AUTO_YU_VERSION}) - Photo Only Edition")

        # 1. Kunci ke Mode Foto
        self.radio_foto.setChecked(True)
        self.radio_video.setVisible(False)
        self.radio_foto.setText(" 📷 MODE FOTO (LITE)")
        self.radio_foto.setEnabled(False) # Tidak bisa diubah
        
        # 2. Batasi Akun (Hanya 1 Akun)
        self.btn_remove_account.setVisible(False)
        self.account_combo.setToolTip("Versi LITE hanya mendukung 1 akun aktif.")
        
        # Cek apakah sudah ada akun, jika belum tampilkan tombol tambah
        self.refresh_account_buttons()
        
        # Sembunyikan fitur-fitur yang tidak diperlukan di versi Lite
        if hasattr(self, 'guide_btn'):
            self.guide_btn.setText("📖 Lite Guide")
            
        # Update License Display for Lite
        self.update_license_display()
        
        self.log_message("ℹ️ <b>Mode LITE Aktif</b>: Hanya mendukung unggahan FOTO.")

        # 3. Hilangkan Mode Auto dan AI Optimize
        self.chk_auto_calc.setChecked(False)
        self.chk_auto_calc.setVisible(False)
        if hasattr(self, 'chk_auto_retry'):
            self.chk_auto_retry.setVisible(False)
        self.auto_helper.setVisible(False)
        self.example_label.setVisible(False)
        self.manual_helper.setVisible(False)
        self.dynamic_helper.setVisible(False)

        # Aktifkan input manual secara permanen di Lite
        self.tabs_spin.setEnabled(True)
        self.batch_spin.setEnabled(True)
        
        # Batasi jumlah tab maksimal sesuai RAM untuk stabilitas (Lite khusus)
        specs = self.detect_system_specs()
        max_lite_tabs = 4  # Default jika gagal deteksi
        if specs:
            ram_gb = specs["ram_gb"]
            if ram_gb <= 4:
                max_lite_tabs = 2
            elif ram_gb <= 8:
                max_lite_tabs = 6
            elif ram_gb <= 16:
                max_lite_tabs = 10
            else:
                max_lite_tabs = 15
        
        # Terapkan batas ke spinbox
        self.tabs_spin.setRange(1, max_lite_tabs)
        # Jika nilai saat ini melebihi batas, turunkan ke batas maksimal
        current_tabs = self.tabs_spin.value()
        if current_tabs > max_lite_tabs:
            self.tabs_spin.setValue(max_lite_tabs)
            self.log_message(f"ℹ️ Jumlah tab disesuaikan ke {max_lite_tabs} untuk stabilitas sistem (RAM: {specs['ram_gb']} GB).")
        
        # Kunci mode upload ke SAFE untuk stabilitas di versi Lite
        self.radio_safe.setChecked(True)
        self.radio_turbo.setEnabled(False)
        self.radio_turbo.setVisible(False)

        # 4. Lite: Hanya mendukung LOKASI (FotoTree dinonaktifkan sebagai insentif Upgrade)
        self.btn_live_tree.setText("UPGRADE")
        self.btn_live_tree.setToolTip("FotoTree hanya tersedia di versi PRO. Klik untuk upgrade!")
        self.btn_live_tree.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 0 5px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        # Ganti aksi tombol menjadi buka link upgrade (opsional) atau abaikan
        try: self.btn_live_tree.clicked.disconnect()
        except: pass
        self.btn_live_tree.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://fotoyu.com/pro")))
        
        self.fototree_input.setPlaceholderText("🌳 Upgrade ke PRO untuk fitur FotoTree")
        self.fototree_input.setReadOnly(True)
        self.fototree_input.setEnabled(False)
        self.fototree_input.setStyleSheet("background-color: #1E293B; color: #64748B; border: 1px dashed #334155;")
        
        self.fototree_status.setText("PRO ONLY")
        self.fototree_status.setStyleSheet("color: #7C3AED; font-size: 10px; font-weight: 900;")

        # Pastikan Lokasi tetap aktif
        self.location_input.setEnabled(True)
        self.location_input.setReadOnly(False)
        self.location_input.textChanged.connect(self._auto_save_lite_settings)
        
        # 5. Buat GUI Lebih Compact
        self._make_compact()
        
        # Connect signals for auto-saving when fields change
        self.path_input.textChanged.connect(self._auto_save_lite_settings)
        self.price_input.textChanged.connect(self._auto_save_lite_settings)
        self.fototree_input.textChanged.connect(self._auto_save_lite_settings)
        self.location_input.textChanged.connect(self._auto_save_lite_settings)
        self.desc_input.textChanged.connect(self._auto_save_lite_settings)
        
        # Reconnect Setup Metadata button explicitly for Lite
        try: self.btn_setup_metadata.clicked.disconnect()
        except: pass
        self.btn_setup_metadata.clicked.connect(self.on_setup_metadata_clicked)
        
        # Karena apply_saved_settings dioverride, pastikan sinyal akun tetap tersambung.
        # Gunakan QTimer agar UI benar-benar siap sebelum menyambungkan sinyal
        QTimer.singleShot(100, self._connect_lite_account_signals)

    def _auto_save_lite_settings(self):
        """Simpan pengaturan secara otomatis saat ada perubahan di input."""
        config = self.get_current_config()
        if config:
            settings = load_settings() or {}
            settings.update(config)
            save_settings(settings)

    def _make_compact(self):
        """Membuat tampilan beneran 'Lite' dan hemat ruang."""
        # 1. Perkecil ukuran jendela default
        self.setMinimumSize(900, 600)
        self.resize(950, 650)
        
        # 2. Sempitkan kontainer utama
        if hasattr(self, 'content_container'):
            self.content_container.setMinimumWidth(600)
            self.content_container.setMaximumWidth(900)
            
        # 3. Hilangkan card 'MODE UNGGAHAN' karena sudah pasti Foto
        # Kita cari card pertama di content_layout (biasanya upload_card)
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if isinstance(widget, QFrame) and widget.property("class") == "card":
                # Card pertama adalah upload_card
                widget.setVisible(False)
                break
        
        # 4. Kurangi spasi dan margin
        self.content_layout.setSpacing(6)
        self.content_layout.setContentsMargins(10, 5, 10, 5)
        
        # 5. Sembunyikan elemen dekoratif yang makan tempat
        if hasattr(self, 'engine_helper'): self.engine_helper.setVisible(False)
        if hasattr(self, 'upload_helper'): self.upload_helper.setVisible(False)
        
        # 6. Perkecil Header
        for label in self.findChildren(QLabel):
            if label.property("class") == "card_title":
                label.setStyleSheet("font-size: 13px; font-weight: 900; color: #6366F1;")
        
        # 7. Sembunyikan elemen terkait Folder Failed & Tombol Lanjutkan (Khusus Lite)
        if hasattr(self, 'retry_btn'): self.retry_btn.setVisible(False)
        if hasattr(self, 'failed_badge'): self.failed_badge.setVisible(False)
        
        # Cari tombol "LANJUTKAN SISA GAGAL" di footer jika ada
        for btn in self.findChildren(QPushButton):
            if "GAGAL" in btn.text().upper():
                btn.setVisible(False)
                
        # 8. Buat Log Panel lebih pendek agar tidak scroll terlalu jauh
        if hasattr(self, 'log_text'):
            self.log_text.setMaximumHeight(120)
            self.log_text.setMinimumHeight(80)
            
        # 8. Kecilkan Footer dan Status Bar
        # Cari footer_panel melalui objectName atau layout
        footer = self.findChild(QFrame, "footer_panel")
        if footer:
            footer.layout().setContentsMargins(10, 4, 10, 4)
            footer.layout().setSpacing(4)
            
        # Sembunyikan status bar yang redundan (Engine & Media selalu sama di Lite)
        if hasattr(self, 'status_engine'):
            # Ambil parent layout dari status_engine
            engine_layout = self.status_engine.parent().layout()
            if engine_layout:
                # Sembunyikan label dan value
                self.status_engine.setVisible(False)
                # Mencari label "Engine:"
                for i in range(engine_layout.count()):
                    w = engine_layout.itemAt(i).widget()
                    if w and "Engine" in w.text(): w.setVisible(False)
                    
        if hasattr(self, 'status_media'):
            media_layout = self.status_media.parent().layout()
            if media_layout:
                self.status_media.setVisible(False)
                for i in range(media_layout.count()):
                    w = media_layout.itemAt(i).widget()
                    if w and "Media" in w.text(): w.setVisible(False)
            
        self.log_message("✨ <b>GUI Compact Aktif</b>: Tampilan dioptimalkan untuk mode LITE.")

    def _connect_lite_account_signals(self):
        """Pastikan aksi akun Lite terhubung tepat sekali."""
        # Disconnect signals from parent class to avoid double calls
        for signal in [self.btn_add_account.clicked, 
                      self.btn_remove_account.clicked, 
                      self.account_combo.currentTextChanged]:
            try:
                signal.disconnect()
            except Exception:
                pass
                
        self.btn_add_account.clicked.connect(self.on_add_account)
        self.btn_remove_account.clicked.connect(self.on_remove_account)
        self.account_combo.currentTextChanged.connect(self.on_account_combo_changed)

    def refresh_account_buttons(self):
        """Tampilkan tombol tambah akun hanya jika akun masih kosong."""
        has_account = self.account_combo.count() > 0
        self.btn_add_account.setVisible(not has_account)
        # Di versi lite, kita beri pilihan untuk hapus akun agar bisa ganti akun
        self.btn_remove_account.setVisible(has_account) 
        self.btn_remove_account.setText("Ganti Akun")

    def update_license_display(self):
        is_valid, status_code, cust_name, res_data = check_license(app_type="lite")
        if is_valid:
            self.license_badge.setText(f"🏷️ Lite: {cust_name}")
            self.license_badge.setStyleSheet("background: #6366F1; color: white; border-radius: 4px; padding: 2px 8px; font-weight: bold;")
        else:
            self.license_badge.setText("🏷️ Lite: Unlicensed")
            self.license_badge.setStyleSheet("background: #EF4444; color: white; border-radius: 4px; padding: 2px 8px; font-weight: bold;")

    def apply_saved_settings(self):
        """Override untuk memastikan hanya 1 akun yang dimuat dan dikunci ke FOTO."""
        settings = load_settings()
        if settings:
            accounts = settings.get("accounts") or []
            current_account = settings.get("current_account")
            
            selected_account = ""
            if current_account and current_account in accounts:
                selected_account = current_account
            elif accounts:
                selected_account = accounts[0]
            lite_accounts = [selected_account] if selected_account else []
            
            self.account_combo.blockSignals(True)
            self.account_combo.clear()
            for a in lite_accounts:
                self.account_combo.addItem(a)
            
            if lite_accounts:
                self.account_combo.setCurrentIndex(0)
                self.update_account_status(lite_accounts[0])
            else:
                self.status_account.setText("Belum ada akun")
                self.status_account.setStyleSheet("color: #EF4444; font-weight: 800;")
            self.account_combo.blockSignals(False)
            
            settings["accounts"] = lite_accounts
            settings["current_account"] = lite_accounts[0] if lite_accounts else ""
            save_settings(settings)
            
            self.refresh_account_buttons()
            
            if settings.get("folder"):
                self.path_input.setText(settings["folder"])
            if settings.get("price"):
                self.price_input.setText(settings["price"])
            
            # LITE: Paksa FotoTree Kosong agar tidak diklik saat automasi
            self.fototree_input.setText("")
            
            if settings.get("location"):
                self.location_input.setText(settings["location"])
            
            self.radio_foto.setChecked(True)
            self.update_media_status("FOTO")
            self.radio_safe.setChecked(True)
            self.chk_auto_calc.setChecked(False)
            
            self.log_message("✅ Pengaturan Lite dimuat.")
        else:
            super().apply_saved_settings()
            self.refresh_account_buttons()
            self.radio_safe.setChecked(True)
            self.chk_auto_calc.setChecked(False)

        # Initial mutual exclusion check
        self._update_mutual_exclusion()

    def get_current_config(self):
        """Kunci konfigurasi runtime Lite agar selalu stabil."""
        config = super().get_current_config()
        if not config:
            return config
        config["is_lite"] = True
        config["type"] = "foto"
        config["mode"] = "SAFE"
        config["auto_calc"] = False
        config["visual_confirm_delay_sec"] = 5
        if not config.get("current_account") and self.account_combo.count() > 0:
            config["current_account"] = self.account_combo.itemText(0)
        return config

    def on_remove_account(self):
        """Ganti akun di versi lite (hapus yang lama lalu izinkan tambah baru)."""
        name = self.account_combo.currentText()
        if not name:
            return
            
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Ganti Akun", 
                                   f"Apakah Anda yakin ingin menghapus akun '{name}' dan menggantinya dengan akun baru?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 1. Hapus data session fisik
            try:
                import shutil
                import stat
                def on_rm_error(func, path, exc_info):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)

                from gui.main_window import get_app_data_dir
                base_local = get_app_data_dir()
                account_root = os.path.join(base_local, "accounts", name)
                if os.path.exists(account_root):
                    shutil.rmtree(account_root, onerror=on_rm_error)
                    self.log_message(f"🗑️ Data session akun '{name}' telah dihapus.")
            except Exception as e:
                self.log_message(f"⚠️ Gagal menghapus data session: {e}")

            # 2. Update settings.json
            from gui.main_window import load_settings, save_settings
            settings = load_settings() or {}
            settings["accounts"] = []
            settings["current_account"] = ""
            save_settings(settings)
            
            # 3. Reset Engine if running
            self.stop_signal.emit()
            
            # 4. Update UI
            self.account_combo.clear()
            self.refresh_account_buttons()
            self.update_account_status("")
            self.log_message(f"✅ Akun '{name}' telah dihapus. Silakan klik 'Tambah Akun' untuk login baru.")

    def on_setup_metadata_clicked(self):
        """Override untuk memastikan setup metadata berfungsi di Lite."""
        print(f"[LiteWindow] Setup Metadata button clicked!")
        if not self.account_combo.currentText():
            self.show_custom_message("Akun Diperlukan", "Pilih atau tambah akun Fotoyu terlebih dahulu sebelum setup metadata.", "warning")
            return
        print(f"[LiteWindow] Calling on_start with setup_metadata_first=True")
        self.on_start(login_only=True, setup_metadata_first=True)

    def on_start(self, login_only=False, setup_metadata_first=False):
        """Memastikan fungsi on_start dipanggil dari kelas induk (MainWindow)."""
        # 0. License Check - Lite Version
        is_valid, status_code, _, _ = check_license(app_type="lite")
        if not is_valid:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Lisensi Tidak Valid", f"Lisensi LITE Anda tidak valid atau telah kadaluarsa (Code: {status_code}).")
            return

        # Sinkronkan config UI ke variabel lokal sebelum memanggil super().on_start()
        # Hal ini krusial karena versi Lite menyembunyikan beberapa elemen UI
        print(f"[LiteWindow] on_start called, login_only={login_only}, setup_metadata_first={setup_metadata_first}")
        from gui.main_window import load_settings, save_settings
        config = self.get_current_config()
        if config:
            print(f"[LiteWindow] Current config: {config}")
            settings = load_settings() or {}
            settings.update(config)
            save_settings(settings)
        else:
            print("[LiteWindow] WARNING: get_current_config() returned None")
            
        super().on_start(login_only, setup_metadata_first)

    def on_add_account(self):
        """Izinkan tambah akun hanya jika masih kosong."""
        if self.account_combo.count() >= 1:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Versi LITE", "Versi LITE hanya mendukung 1 akun. Silakan 'Ganti Akun' untuk masuk dengan akun lain.")
            return
        
        # Jalankan dialog tambah akun
        from gui.main_window import AddAccountDialog, QDialog
        dialog = AddAccountDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name = dialog.account_name
            self.account_combo.addItem(name)
            self.account_combo.setCurrentText(name)
            self.refresh_account_buttons()
            self.update_account_status(name)
            
            # Simpan ke settings
            from gui.main_window import load_settings, save_settings
            settings = load_settings() or {}
            settings["accounts"] = [name]
            settings["current_account"] = name
            save_settings(settings)
            
            self.log_message(f"➕ Akun '{name}' ditambahkan. Membuka browser untuk login...")
            
            # Gunakan QTimer singkat agar UI sinkron dulu
            QTimer.singleShot(500, lambda: self.on_start(login_only=True))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiteWindow()
    window.show()
    sys.exit(app.exec())
