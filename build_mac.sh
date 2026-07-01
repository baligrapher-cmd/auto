#!/bin/bash

# AutoYu V3 Build Script for macOS
# Build Universal binary (Apple Silicon & Intel)

echo "🚀 Starting Build Process for macOS..."

# 1. Setup Virtual Environment
echo "📦 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 2. Install Dependencies
echo "pip Install dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller pillow  # Tambahkan pillow untuk konversi icon otomatis

# 3. Install Playwright Chromium
echo "🌐 Installing Playwright Chromium..."
rm -rf pw-browsers
PLAYWRIGHT_BROWSERS_PATH=./pw-browsers python -m playwright install chromium

# 4. Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# 5. Build Application
echo "🛠️ Compiling Application..."
pyinstaller --clean --noconfirm --distpath dist AutoYuPro.spec
if [ -d "pw-browsers" ]; then
    mkdir -p dist/AutoYuPro.app/Contents/Resources/browsers
    # Salin registry.json, chromium (utama), dan ffmpeg
    cp -R pw-browsers/registry.json dist/AutoYuPro.app/Contents/Resources/browsers/
    cp -R pw-browsers/chromium* dist/AutoYuPro.app/Contents/Resources/browsers/
    cp -R pw-browsers/ffmpeg-* dist/AutoYuPro.app/Contents/Resources/browsers/
    # Bersihkan file sampah (zip/tar/obj) agar ukuran ramping
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.zip" -delete
    find dist/AutoYuPro.app/Contents/Resources/browsers -name "*.gz" -delete
    rm -rf dist/AutoYuPro.app/Contents/Resources/browsers/*/obj
fi

echo "✅ Build Complete!"
echo "📂 Application located at: dist/AutoYuPro.app"
