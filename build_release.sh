#!/bin/bash

# AutoYu Pro Release Build Script
# Creates both Apple Silicon and Intel versions with PANDUAN_USER.txt included

set -e # Exit on error

echo "🚀 Starting Release Build Process for macOS..."

# --- APPLE SILICON BUILD ---
echo "📦 Setting up Apple Silicon environment..."
if [ ! -d "venv_arm" ]; then
    python3 -m venv venv_arm
fi
source venv_arm/bin/activate
pip install --upgrade pip
pip install --no-compile --no-cache-dir -r requirements.txt
pip install --no-compile --no-cache-dir pyinstaller pillow
PLAYWRIGHT_BROWSERS_PATH=./pw-browsers python -m playwright install chromium

echo "🛠️ Compiling Apple Silicon version..."
rm -rf build dist
pyinstaller --clean --noconfirm --distpath dist AutoYuPro.spec
if [ -d "pw-browsers" ]; then
    mkdir -p dist/AutoYuPro.app/Contents/Resources/browsers
    # Salin chromium dan ffmpeg
    cp -R pw-browsers/chromium* dist/AutoYuPro.app/Contents/Resources/browsers/
    cp -R pw-browsers/ffmpeg-* dist/AutoYuPro.app/Contents/Resources/browsers/
    
    # --- PEMBERSIHAN BROWSER (Sesuai Catatan Teknis) ---
    echo "🧹 Optimizing browser bundle size..."
    # Hapus folder translations agar ramping
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "translations" -type d -exec rm -rf {} +
    # Hapus file zip/gz/dSYM
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.zip" -delete
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.gz" -delete
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.dSYM" -type d -exec rm -rf {} +
    # Hapus folder obj dan gen
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "obj" -type d -exec rm -rf {} +
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "gen" -type d -exec rm -rf {} +
fi

# --- BINARY STRIPPING (Sesuai Catatan Teknis) ---
echo "✂️ Stripping debug symbols..."
strip -x dist/AutoYuPro.app/Contents/MacOS/AutoYuPro || true

cp PANDUAN_USER.txt dist/
cd dist
# Gunakan flag -y untuk menjaga symlink (Sesuai Catatan Teknis)
zip -r9y ../AutoYuPro-AppleSilicon.zip AutoYuPro.app PANDUAN_USER.txt
cd ..
deactivate

# --- INTEL BUILD ---
echo "📦 Setting up Intel environment (x86_64)..."
rm -rf venv_intel
arch -x86_64 python3 -m venv venv_intel
source venv_intel/bin/activate
arch -x86_64 python3 -m pip install --upgrade pip
arch -x86_64 python3 -m pip install --no-compile --no-cache-dir -r requirements.txt
arch -x86_64 python3 -m pip install --no-compile --no-cache-dir pyinstaller pillow
PLAYWRIGHT_BROWSERS_PATH=./pw-browsers arch -x86_64 python3 -m playwright install chromium

echo "🛠️ Compiling Intel version..."
rm -rf build dist
arch -x86_64 pyinstaller --clean --noconfirm --distpath dist AutoYuPro.spec
if [ -d "pw-browsers" ]; then
    mkdir -p dist/AutoYuPro.app/Contents/Resources/browsers
    # Salin chromium dan ffmpeg
    cp -R pw-browsers/chromium* dist/AutoYuPro.app/Contents/Resources/browsers/
    cp -R pw-browsers/ffmpeg-* dist/AutoYuPro.app/Contents/Resources/browsers/
    
    # --- PEMBERSIHAN BROWSER (Sesuai Catatan Teknis) ---
    echo "🧹 Optimizing browser bundle size..."
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "translations" -type d -exec rm -rf {} +
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.zip" -delete
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.gz" -delete
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.dSYM" -type d -exec rm -rf {} +
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "obj" -type d -exec rm -rf {} +
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "gen" -type d -exec rm -rf {} +
fi

# --- BINARY STRIPPING (Sesuai Catatan Teknis) ---
echo "✂️ Stripping debug symbols..."
strip -x dist/AutoYuPro.app/Contents/MacOS/AutoYuPro || true

cp PANDUAN_USER.txt dist/
cd dist
# Gunakan flag -y untuk menjaga symlink (Sesuai Catatan Teknis)
zip -r9y ../AutoYuPro-Intel.zip AutoYuPro.app PANDUAN_USER.txt
cd ..
deactivate

echo "✅ All builds complete!"
echo "📦 Files created:"
echo "   - AutoYuPro-AppleSilicon.zip (contains: AutoYuPro.app + PANDUAN_USER.txt)"
echo "   - AutoYuPro-Intel.zip (contains: AutoYuPro.app + PANDUAN_USER.txt)"
