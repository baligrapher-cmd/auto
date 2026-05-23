
import os
import sys
import json
import requests
import time

def upload_via_api(file_path, token, price="8000", description="Upload via API Trial"):
    """
    Prototype fungsi untuk upload langsung ke API Fotoyu tanpa browser.
    """
    url = "https://api.fotoyu.com/gs/v3/creations" # Endpoint v3 yang terdeteksi
    
    if not os.path.exists(file_path):
        print(f"❌ File tidak ditemukan: {file_path}")
        return False

    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fotoyu.com",
        "Referer": "https://www.fotoyu.com/upload"
    }

    # Metadata yang biasanya dikirim
    # Struktur ini mungkin perlu disesuaikan dengan hasil intercept nyata
    data = {
        "price": price,
        "description": description,
        "is_video": "false" if file_path.lower().endswith(('.jpg', '.jpeg', '.png')) else "true"
    }

    files = {
        "file": (os.path.basename(file_path), open(file_path, "rb"), "image/jpeg")
    }

    print(f"🚀 Mencoba upload {os.path.basename(file_path)}...")
    
    try:
        response = requests.post(url, headers=headers, data=data, files=files, timeout=60)
        
        if response.status_code in [200, 201]:
            print("✅ Berhasil! Respon Server:")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ Gagal (Status: {response.status_code})")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
        return False

def get_latest_token():
    # Cari token di lokasi standar tracker
    possible_paths = [
        "api_token.txt",
        os.path.join(os.getenv("APPDATA", ""), "AutoYuPro", "trackers", "api_token.txt")
    ]
    
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, "r") as f:
                return f.read().strip()
    return None

if __name__ == "__main__":
    print("=== AUTOYU DIRECT API TRIAL ===")
    token = get_latest_token()
    
    if not token:
        print("❌ Token tidak ditemukan! Silakan jalankan AutoYu V3 sekali untuk menangkap token.")
        sys.exit(1)
        
    print(f"🔑 Token ditemukan: {token[:20]}...")
    
    # Ganti dengan path file yang ingin dicoba
    test_file = input("Masukkan path file gambar (contoh: C:\\foto.jpg): ").strip('"')
    
    if test_file:
        upload_via_api(test_file, token)
    else:
        print("❌ Path file tidak boleh kosong.")
