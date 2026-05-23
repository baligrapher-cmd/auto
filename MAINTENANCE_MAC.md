# Panduan Maintenance & Kompilasi macOS AutoYu Pro

Dokumen ini berisi catatan teknis penting untuk memastikan aplikasi berjalan lancar di MacBook dan proses kompilasi tidak menghasilkan error.

## 1. Penanganan Masalah "Stuck di Compress"
Masalah utama pada MacBook adalah adanya file metadata tersembunyi yang dibuat oleh sistem macOS.

- **Penyebab**: File `._filename.jpg` (AppleDouble) dan `.DS_Store` dikira sebagai file gambar asli oleh aplikasi. Saat diunggah ke website Fotoyu, proses kompresi website akan hang karena file tersebut bukan gambar valid.
- **Solusi**: 
    - Selalu filter file yang diawali dengan `._` atau `.DS_Store`.
    - Batasi ekstensi hanya ke `.jpg`, `.jpeg`, dan `.png` untuk stabilitas maksimal di sisi server Fotoyu.
    - Lokasi filter: [worker.py](core/worker.py), [automation.py](core/automation.py), dan [main_window.py](gui/main_window.py).

## 2. Standar Kompilasi (Wajib Diikuti)
Untuk menghindari error "App is Damaged" atau "Killed: 9" di macOS modern (Apple Silicon & Intel):

- **Dilarang menggunakan `strip -x`**: Jangan menjalankan perintah `strip` pada binary yang dihasilkan PyInstaller. Ini akan merusak *Code Signature* dan membuat aplikasi tidak bisa dibuka.
- **Wajib menggunakan `zip -r9y`**: Saat membungkus aplikasi menjadi file `.zip`, flag `-y` **wajib** digunakan untuk menjaga *symlink* browser Playwright. Tanpa flag ini, ukuran file akan membengkak (duplikasi) dan struktur browser akan rusak.
- **Bundling Browser**: Pastikan seluruh isi folder `pw-browsers` (termasuk `registry.json`) disalin ke `AutoYuPro.app/Contents/Resources/browsers/`.

## 3. Wajib Smoke Test (Verifikasi Rilis)
Setiap kali melakukan build (terutama via GitHub Actions), **WAJIB** memeriksa log **Smoke Test & Verify Bundle**.

### Kriteria Kelulusan Smoke Test:
1. **Structure Check**: Memastikan binary utama ada di dalam bundle `.app`.
2. **Signature Check**: Menjalankan `codesign --verify` untuk memastikan bundle tidak korup.
3. **Internal Browser Check**: Aplikasi harus mencetak log `DEBUG: Found internal browser path`. Ini membuktikan aplikasi menggunakan browser bawaan, bukan browser sistem user.
4. **Execution Check**: Aplikasi harus berhasil memuat library (PySide6, Playwright) dalam 10-15 detik pertama tanpa crash.

> **Catatan**: Di lingkungan CI (GitHub Actions), aplikasi mungkin keluar dengan error GUI (Headless). Hal ini dianggap **LULUS** selama library berhasil dimuat dan tidak ada error `ModuleNotFoundError`.

## 4. Deteksi Sistem macOS
- **RAM**: Gunakan fallback ke `vm_stat` jika `psutil` tidak tersedia untuk mendapatkan penggunaan memori real-time yang akurat di macOS.
- **Internal Browser**: Selalu gunakan `flush=True` pada print debug agar log terdeteksi oleh sistem otomatis GitHub Actions.

---
*Dibuat untuk memastikan stabilitas AutoYu Pro lintas platform.*
