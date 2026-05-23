@echo off
echo [1/4] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller pillow

echo [2/4] Preparing Playwright Browsers...
set PLAYWRIGHT_BROWSERS_PATH=%CD%\pw-browsers
python -m playwright install chromium chromium-headless-shell ffmpeg

echo [3/4] Building AutoYuPro EXE...
python -m PyInstaller --clean --noconfirm AutoYuPro.spec

echo [4/4] Building AutoYuLite EXE...
python -m PyInstaller --clean --noconfirm AutoYuLite.spec

echo [5/5] Finalizing Packages...
if exist "pw-browsers" (
    echo Bundling internal browser for Pro...
    if exist "dist\AutoYuPro\_internal" (
        xcopy /E /I /Y "pw-browsers" "dist\AutoYuPro\_internal\browsers"
    )
    echo Bundling internal browser for Lite...
    if exist "dist\AutoYuLite\_internal" (
        xcopy /E /I /Y "pw-browsers" "dist\AutoYuLite\_internal\browsers"
    )
)

echo.
echo Build Complete! 
echo Hasil build ada di folder dist\
pause
