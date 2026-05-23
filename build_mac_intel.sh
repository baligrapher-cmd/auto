#!/bin/bash

# AutoYu V3 Build Script for macOS Intel (x86_64)
echo "🚀 Starting Build Process for macOS Intel..."

# 1. Setup Virtual Environment
if [ ! -d "venv_x86" ]; then
    echo "📦 Creating venv_x86..."
    python3 -m venv venv_x86
fi
source venv_x86/bin/activate

# 2. Install Dependencies
echo "pip Install dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller pillow

# 3. Install Playwright Chromium
echo "🌐 Installing Playwright Chromium..."
PLAYWRIGHT_BROWSERS_PATH=./pw-browsers arch -x86_64 python -m playwright install chromium

# 4. Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist/Intel

# 5. Build Application
echo "🛠️ Compiling Application (Intel x86_64)..."
# Force x86_64 architecture for the build
arch -x86_64 pyinstaller --clean --noconfirm --distpath dist/Intel AutoYuPro.spec
if [ -d "pw-browsers" ]; then
    mkdir -p dist/Intel/AutoYuPro.app/Contents/Resources/browsers
    cp -R pw-browsers/* dist/Intel/AutoYuPro.app/Contents/Resources/browsers/
fi

echo "✅ Intel Build Complete!"
echo "📂 Application located at: dist/Intel/AutoYuPro.app"
