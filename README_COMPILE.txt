# AutoYu V3 - Source Code Backup

## Struktur Folder

```
backup_source/
├── main.py              # Entry point aplikasi
├── gui/                 # Graphical User Interface
│   ├── __init__.py
│   └── main_window.py   # Jendela utama aplikasi
├── core/                # Core logic
│   ├── __init__.py
│   ├── automation.py    # Logika upload automation
│   ├── state_machine.py # State machine untuk kontrol alur
│   ├── worker.py        # Worker thread untuk proses background
│   └── license.py       # Manajemen lisensi
├── assets/              # Asset aplikasi
│   └── icon.ico         # Ikon aplikasi
├── website/             # Website verification (PHP)
├── requirements.txt     # Daftar dependency Python
├── AutoYu_V3.spec       # PyInstaller spec file untuk Windows
└── build_mac.sh         # Script build untuk macOS
```

## Cara Compile di Windows

### Prasyarat
- Python 3.10+ terinstall
- pip (Python package manager)
- Internet connection untuk download dependency

### Langkah-langkah

1. **Buka Command Prompt / PowerShell**

2. **Install dependency:**
```bash
cd c:\path\to\backup_source
pip install -r requirements.txt
```

3. **Install Playwright browser ke folder bundle lokal:**
```bash
$env:PLAYWRIGHT_BROWSERS_PATH = ".\pw-browsers"
python -m playwright install chromium
```

4. **Compile dengan PyInstaller:**
```bash
pyinstaller AutoYu_V3.spec
```

5. **File executable akan muncul di:**
```
dist\AutoYu_V3.exe
```

### Alternative: Compile dengan build_exe.bat
```bash
build_exe.bat
```

---

## Cara Compile di macOS

### Prasyarat
- Python 3.10+ terinstall
- Terminal access
- Internet connection

### Langkah-langkah

1. **Buka Terminal**

2. **Grant execute permission:**
```bash
chmod +x build_mac.sh
```

3. **Jalankan script:**
```bash
./build_mac.sh
```

Script ini akan:
- Membuat virtual environment
- Install semua dependency
- Install Playwright Chromium
- Compile dengan PyInstaller (windowed mode)

4. **File aplikasi akan muncul di:**
```
dist/AutoYu.app
```

---

## Dependencies

Aplikasi ini membutuhkan library berikut:
- **PySide6** - GUI Framework (Qt binding untuk Python)
- **playwright** - Browser automation
- **pillow** - Image processing
- **requests** - HTTP library

Lihat `requirements.txt` untuk versi lengkap.

---

## Catatan Penting

1. **Ikon**: Untuk macOS, Anda perlu mengkonversi `icon.ico` ke `icon.icns` menggunakan tool seperti `iconutil` atau online converter.

2. **Playwright**: Browser Chromium sebaiknya diinstall ke `pw-browsers` agar ikut terbundle saat build.

3. **Website Verification**: Folder `website/` berisi PHP scripts untuk verifikasi lisensi. Anda perlu web server dengan PHP untuk menggunakan fitur ini.

---

## Lisensi

Properti dari AutoYu. Source code ini dilindungi hak cipta.
