# ARTUR License System - API Integration Guide for Developers

Dokumentasi ini ditujukan bagi pengembang (developer) untuk mengintegrasikan sistem lisensi **ARTUR** ke dalam aplikasi klien (Desktop, Web, atau Mobile).

## 1. Informasi Endpoint
Sistem menggunakan protokol HTTP POST untuk verifikasi.

- **URL**: `https://api.pramana.web.id/verify.php`
- **Method**: `POST`
- **Content-Type**: `application/x-www-form-urlencoded`

## 2. Parameter Request (POST)
Kirimkan parameter berikut dari aplikasi Anda:

| Parameter | Tipe | Wajib | Deskripsi |
| :--- | :--- | :--- | :--- |
| `license_key` | String | Ya | Kunci lisensi yang dimasukkan user. |
| `machine_id` | String | Ya | ID unik perangkat (HWID). Disarankan menggunakan Serial Number Motherboard atau UUID sistem. |
| `variant_prefix` | String | Ya (Baru) | Prefix varian aplikasi (e.g. `LITE`, `PRO`, `ULTRA`). Digunakan untuk mencegah lisensi murah dipakai di versi mahal. |
| `app_id` | Integer | Disarankan | ID aplikasi yang terdaftar di panel admin. |
| `device_name` | String | Tidak | Nama komputer user (e.g. `DESKTOP-XYZ`). |
| `brand` | String | Tidak | Merek perangkat (e.g. `ASUS`, `ACER`). |
| `model` | String | Tidak | Model perangkat. |
| `serial` | String | Tidak | Serial number perangkat jika tersedia. |

## 3. Format Respon (JSON)

### **A. Sukses**
```json
{
    "status": "success",
    "message": "License Verified",
    "customer": "Nama Pelanggan",
    "expiry": "2024-12-31",
    "app": "Nama Aplikasi",
    "variant": "PRO",
    "signature": "BASE64_ENCODED_RSA_SIGNATURE"
}
```

### **B. Gagal**
```json
{
    "status": "error",
    "message": "Alasan kegagalan (e.g. Lisensi LITE tidak dapat digunakan untuk versi PRO)"
}
```

## 4. Keamanan Tingkat Tinggi (RSA Signature)
Untuk mencegah bypass menggunakan alat seperti *Fiddler* atau *Local Proxy*, server mengirimkan `signature`.
- **Data yang di-sign**: `license_key|machine_id|variant_prefix`
- **Algoritma**: `SHA256 with RSA`

**Cara Verifikasi di Sisi Klien:**
1. Gunakan **Public Key** (berasal dari `private_key.pem` di server).
2. Gabungkan `license_key` dan `machine_id` dengan pemisah `|`. (Catatan: Server saat ini menggunakan format `license_key|machine_id` untuk signing).
3. Verifikasi string tersebut terhadap `signature` yang diterima dari JSON menggunakan Public Key.

## 5. Contoh Kode Implementasi (Python dengan RSA)

```python
import requests
import hashlib
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
... (Isi dengan Public Key Anda) ...
-----END PUBLIC KEY-----"""

def verify_signature(data, signature_b64):
    try:
        public_key = serialization.load_pem_public_key(PUBLIC_KEY.encode())
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            data.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except:
        return False

def check_license(key, app_type="PRO"):
    hwid = "ID_UNIK_PERANGKAT" 
    url = "https://api.pramana.web.id/verify.php"
    
    data = {
        "license_key": key,
        "machine_id": hwid,
        "variant_prefix": app_type.upper()
    }
    
    try:
        r = requests.post(url, data=data)
        res = r.json()
        if res['status'] == 'success':
            # Verifikasi Signature untuk keamanan extra
            sig = res.get('signature')
            if sig and verify_signature(f"{key}|{hwid}", sig):
                return True, res
            return False, "Signature Verification Failed"
        return False, res['message']
    except Exception as e:
        return False, str(e)
```

### **C# (System.Net.Http)**
```csharp
using System.Net.Http;
using System.Collections.Generic;
using Newtonsoft.Json;

public async Task<bool> Verify(string key, string hwid) {
    var client = new HttpClient();
    var values = new Dictionary<string, string> {
        { "license_key", key },
        { "machine_id", hwid }
    };
    var content = new FormUrlEncodedContent(values);
    var response = await client.PostAsync("https://api.pramana.web.id/verify.php", content);
    var responseString = await response.Content.ReadAsStringAsync();
    dynamic result = JsonConvert.DeserializeObject(responseString);
    return result.status == "success";
}
```

## 6. Best Practices (Anti-Crack)
1. **Verifikasi Berkala**: Jangan hanya verifikasi saat startup. Lakukan verifikasi acak saat aplikasi sedang berjalan.
2. **Obfuscation**: Selalu gunakan tool obfuscator (seperti PyArmor untuk Python, atau Dotfuscator untuk C#) agar kode verifikasi tidak mudah dibaca.
3. **Jangan Simpan Status di File**: Jangan simpan status `is_premium = true` di file lokal atau registry yang mudah diedit. Selalu andalkan respon server atau enkripsi lokal yang kuat.

---
*Dokumentasi ini dibuat otomatis oleh ARTUR AI System.*
