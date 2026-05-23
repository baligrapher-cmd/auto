
import sys
import os
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.lite_window import LiteWindow
from gui.main_window import load_settings, save_settings

def run_test():
    app = QApplication(sys.argv)
    window = LiteWindow()
    
    print("--- MEMULAI PENGUJIAN MANDIRI LITE ---")
    
    # 1. Simulasi Ganti Akun (Hapus Akun)
    print("Step 1: Simulasi Hapus Akun...")
    # Kita tidak panggil dialog, tapi langsung panggil logika hapus
    # Ambil akun saat ini
    current = window.account_combo.currentText()
    if current:
        print(f"Menghapus akun aktif: {current}")
        # Hapus secara manual dari settings dan combo untuk simulasi
        settings = load_settings() or {}
        settings["accounts"] = []
        settings["current_account"] = ""
        save_settings(settings)
        window.account_combo.clear()
        window.refresh_account_buttons()
        print("✔ Akun berhasil dihapus secara simulasi.")
    else:
        print("Info: Tidak ada akun awal, lanjut ke pendaftaran.")

    # 2. Simulasi Tambah Akun & Buka Browser
    print("\nStep 2: Simulasi Tambah Akun 'TestLite'...")
    test_name = "TestLite"
    
    def simulate_add():
        window.account_combo.addItem(test_name)
        window.account_combo.setCurrentText(test_name)
        window.refresh_account_buttons()
        window.update_account_status(test_name)
        
        settings = load_settings() or {}
        settings["accounts"] = [test_name]
        settings["current_account"] = test_name
        save_settings(settings)
        
        print(f"✔ Akun '{test_name}' ditambahkan ke UI dan Settings.")
        print("Mencoba memicu pembukaan browser (on_start)...")
        
        # Panggil on_start
        window.on_start(login_only=True)
        
        print("\n--- HASIL PENGUJIAN ---")
        print("Jika browser Chromium terbuka sekarang, berarti perbaikan sukses!")
        print("Tutup jendela aplikasi untuk mengakhiri tes.")

    # Jalankan simulasi setelah jendela muncul
    QTimer.singleShot(2000, simulate_add)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()
