# PANDUAN PENGGUNAAN AUTOYU V3 LITE

AutoYu V3 Lite adalah versi ringkas yang dioptimalkan khusus untuk pengunggahan FOTO dengan performa tinggi dan antarmuka yang lebih sederhana (Compact GUI).

## 1. Persiapan Folder Foto
- Pastikan semua foto dalam format `.jpg`, `.jpeg`, atau `.png`.
- Masukkan semua foto ke dalam satu folder (misalnya di Desktop atau SD Card).
- **Penting:** Mode Lite tidak memindahkan foto yang gagal ke folder 'failed'. Foto tetap berada di folder asal agar Anda mudah menjalankan ulang otomasi tanpa harus mencari file kembali.

## 2. Cara Menjalankan Aplikasi
1. Buka `AutoYu_V3_Lite.exe`.
2. Masukkan **Nama Akun** Anda.
3. Pilih folder tempat foto Anda disimpan.
4. Klik **Jalankan Otomasi**.

## 3. Proses Login
- Jika baru pertama kali menggunakan akun tersebut, browser akan terbuka dan meminta login manual.
- Silakan login ke akun FotoYu Anda di browser tersebut.
- Setelah login berhasil, sistem akan mendeteksi otomatis. Klik tombol **LANJUTKAN** di aplikasi jika deteksi otomatis belum berpindah.

## 4. Fitur Khusus Versi Lite
- **Mode LITE Aktif:** Hanya mendukung unggahan FOTO. Video dinonaktifkan untuk stabilitas.
- **Compact GUI:** Tampilan minimalis yang berfokus pada progres pengunggahan.
- **Sistem Pelacak Tersembunyi:** Sistem menggunakan file `.upload_tracker.json` yang tersembunyi untuk mencatat progres agar foto tidak terupload ganda.
- **Smart Delay:** Terdapat jeda 3 detik di akhir proses agar Anda bisa melihat konfirmasi visual keberhasilan upload sebelum tab ditutup.

## 5. Indikator Progress
- **Selesai (Hijau):** Jumlah foto yang berhasil terupload di sesi ini.
- **Gagal (Merah):** Jumlah foto yang mengalami kendala (misal: gangguan internet).
- **Duplikat (Abu-abu):** Foto yang terdeteksi sudah pernah diunggah sebelumnya.
- **Progress Bar:** Menunjukkan persentase penyelesaian sesi secara akurat.

## 6. Penanganan Masalah
- **Internet Terputus:** Jika internet mati, sistem akan menunggu dan mencoba memverifikasi ulang. Jika gagal, browser akan tetap terbuka agar Anda bisa melihat status terakhir.
- **Tombol Unggah Mati:** Jika tombol "Unggah" tidak aktif, sistem akan menunggu beberapa saat sebelum mencoba melakukan klik paksa.
- **Foto Tidak Muncul di Progres:** Pastikan format file sudah benar dan folder yang dipilih sudah sesuai.

---
*AutoYu V3 Lite - Optimized for Efficiency*
