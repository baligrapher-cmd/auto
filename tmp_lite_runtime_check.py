import gui.main_window as mw
from PySide6.QtWidgets import QApplication, QMessageBox
from gui.lite_window import LiteWindow


def main():
    # Bypass lisensi agar tes deterministik dan tidak butuh koneksi.
    mw.check_license = lambda: (True, "OK", "Test", {})

    app = QApplication([])

    # Siapkan settings awal
    mw.save_settings(
        {
            "accounts": ["AkunAwal"],
            "current_account": "AkunAwal",
            "type": "video",
            "mode": "TURBO",
            "auto_calc": True,
            "folder": "",
            "price": "10000",
            "desc": "desc",
        }
    )

    window = LiteWindow()

    assert window.account_combo.count() == 1, "Lite harus hanya 1 akun"
    assert window.account_combo.currentText() == "AkunAwal", "Akun awal tidak sesuai"

    # Paksa konfirmasi hapus akun = Yes
    original_question = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)

    window.on_remove_account()
    assert window.account_combo.count() == 0, "Akun tidak terhapus dari UI"

    settings = mw.load_settings() or {}
    assert settings.get("accounts") == [], "Settings accounts harus kosong"
    assert settings.get("current_account") == "", "Settings current_account harus kosong"

    # Simulasi tambah akun baru (tanpa dialog/login browser)
    window.account_combo.addItem("AkunBaru")
    window.account_combo.setCurrentText("AkunBaru")
    window.refresh_account_buttons()
    window.update_account_status("AkunBaru")

    settings["accounts"] = ["AkunBaru"]
    settings["current_account"] = "AkunBaru"
    mw.save_settings(settings)

    cfg = window.get_current_config()
    assert cfg["current_account"] == "AkunBaru", "Config akun baru tidak sesuai"
    assert cfg["type"] == "foto", "Lite wajib mode foto"
    assert cfg["mode"] == "SAFE", "Lite wajib SAFE"
    assert cfg["auto_calc"] is False, "Lite wajib auto_calc nonaktif"

    QMessageBox.question = original_question
    print("PASS: lite ganti akun + config otomasi aman")
    app.quit()


if __name__ == "__main__":
    main()
