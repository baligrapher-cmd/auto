@echo off
:: Berpindah ke folder tempat script ini berada
cd /d "%~dp0"
set REPO_URL=https://github.com/balismma-lgtm/auto

echo ====================================================
echo  AutoYu GitHub Push Helper
echo ====================================================

:: Check if git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git tidak ditemukan! Silakan install Git terlebih dahulu.
    echo Download di: https://git-scm.com/
    pause
    exit /b
)

:: Initialize git if .git folder doesn't exist
if not exist ".git" (
    echo [1/5] Inisialisasi Git repository...
    git init
) else (
    echo [OK] Git repository sudah terinisialisasi.
)

:: Check if remote 'origin' exists
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/5] Menghubungkan ke GitHub: %REPO_URL%
    git remote add origin %REPO_URL%
) else (
    echo [2/5] Memperbarui URL GitHub: %REPO_URL%
    git remote set-url origin %REPO_URL%
)

:: Add files
echo [3/5] Menambahkan file ke staging...
git add .

:: Commit
echo [4/5] Melakukan commit...
git commit -m "Setup macOS build automation for Pro and Lite version"

:: Push
echo [5/5] Melakukan push ke branch main...
git branch -M main
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [FAILED] Gagal melakukan push. Pastikan:
    echo 1. Anda sudah membuat repo 'auto' di GitHub balismma-lgtm.
    echo 2. Koneksi internet aktif.
    echo 3. Anda memiliki izin akses ke repository tersebut.
) else (
    echo.
    echo [SUCCESS] File berhasil terunggah ke GitHub!
    echo Silakan cek tab 'Actions' di %REPO_URL% untuk melihat proses build Mac.
)

pause
