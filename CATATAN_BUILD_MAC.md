# Catatan Teknis Build macOS AutoYu

Dokumen ini berisi catatan penting mengenai konfigurasi build macOS untuk memastikan ukuran file optimal dan kompatibilitas perangkat.

## 1. Optimasi Ukuran ZIP (Penting!)
Masalah utama ukuran build macOS yang membengkak (misal dari 300MB menjadi 800MB+) adalah penanganan **Symlinks**.
- **Solusi**: Gunakan perintah `zip -r9y`.
- **Flag `-y`**: Menjaga symlink agar tidak disalin sebagai file asli. Ini adalah kunci utama agar ukuran ZIP tetap kecil.
- **Pembersihan Browser**: Sebelum di-zip, folder browser Playwright harus dibersihkan dari:
  - Folder `translations` (file bahasa menu browser).
  - File `*.zip`, `*.gz`, `*.dSYM`.
  - Folder `obj` dan `gen`.
- **Binary Stripping**: Gunakan perintah `strip -x` pada file binary di dalam folder `MacOS` untuk membuang informasi debug yang tidak diperlukan.

## 2. Konfigurasi Mac Intel vs Apple Silicon
GitHub Actions menggunakan jenis mesin (runner) yang berbeda untuk masing-masing arsitektur.

### Build Mac Intel (x86_64)
- **Runner**: `macos-13` (Runner Intel asli terakhir yang stabil).
- **Arsitektur**: Harus dikunci dengan `ARCH: x86_64` saat menjalankan PyInstaller.
- **Workflow**: Tersedia di `.github/workflows/build-intel.yml`.

### Build Apple Silicon (M1/M2/M3/M4)
- **Runner**: `macos-14` atau versi lebih baru.
- **Arsitektur**: Menggunakan `ARCH: arm64`.
- **Workflow**: Tersedia di `.github/workflows/compile-mac.yml`.

## 3. Aturan Bundling Rilis
Setiap file ZIP rilis yang diunduh pengguna wajib memiliki struktur berikut:
1.  **Aplikasi**: `AutoYuPro.app` atau `AutoYuLite.app`.
2.  **Panduan**: `PANDUAN_USER.txt` (Disesuaikan dengan versi Pro/Lite).
3.  **Icon**: `icon.ico` (Sesuai permintaan agar tidak blank di taskbar).

## 4. Penanganan Versi Lite
- **Panduan**: Menggunakan sumber file `PANDUAN_LITE_MAC.txt`.
- **Nama File**: Saat dibundel, namanya diubah menjadi `PANDUAN_USER.txt` agar seragam dengan versi Pro.
- **Fitur**: Fitur FotoTree dinonaktifkan di versi Lite sebagai insentif upgrade ke Pro.

---
*Terakhir diperbarui: 9 Mei 2026*
