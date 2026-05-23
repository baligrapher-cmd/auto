import os
import sys
import socket
import getpass
import subprocess
import hashlib
import base64
import json
import requests
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# --- CONFIGURATION ---
# URL Server Produksi
VERIFY_URL = "https://api.pramana.web.id/verify.php"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AutoYu/3.0.0"
}

# RSA Public Key for Verification
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0+1zKPgnBgmmazb1VfTh
pENzP8y2Z3nZmEeEwSkwqNB4SD4Wyz7msnBIwkW+otxVKDXch+F1Sdph7YmkUmp2
/CVqcm2IEx4dDls4yWGusAG/1RgoLmsLqkzGqyrpU2fE3Nt30d/1zmOX4MJg/qsA
QhCISvo1al2QhLS+/7U22fkzqpxt14Gx82MqJvFBezz25dETF7janlBgJUtkQN1B
zk3v6lpkn4O/c5fHGm0R3pxQ05FlqYtEEPxXQAT1Ua4eeFCgEnM8lmoK7gk6byCQ
A3Yn5d/bsoJK0ey1pjboCMJFPazOjESwFBdbfhDnKFTFwtPf4POlt37JDF7M4xhO
zwIDAQAB
-----END PUBLIC KEY-----"""

def _get_public_key():
    return serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())

def verify_signature(data_str, signature_b64):
    """Verifies that the data was signed by the private key."""
    try:
        public_key = _get_public_key()
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            data_str.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False

def _get_master_key():
    # Tetap gunakan master key lama untuk enkripsi local storage status
    part1 = "QXV0b1l1" # AutoYu
    part2 = "LVNlY3VyZQ==" # -Secure
    part3 = "LUxpY2Vuc2U=" # -License
    part4 = "LUtleS0yMDI0" # -Key-2024
    part5 = "LVByYW1hbmE=" # -Pramana
    
    combined = base64.b64decode(part1) + base64.b64decode(part2) + \
               base64.b64decode(part3) + base64.b64decode(part4) + \
               base64.b64decode(part5)
    
    k = hashlib.sha256(combined).digest()
    return base64.urlsafe_b64encode(k)

def get_app_data_dir():
    path = get_app_data_dir_by_name("AutoYuPro")
    os.makedirs(path, exist_ok=True)
    return path

def get_app_data_dir_by_name(app_folder_name):
    if sys.platform == 'darwin':
        path = os.path.expanduser(f"~/Library/Application Support/{app_folder_name}")
    else:
        path = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), app_folder_name)
    os.makedirs(path, exist_ok=True)
    return path

def _get_cmd_output(cmd):
    try:
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Gunakan encoding 'cp437' atau 'utf-8' dan bersihkan karakter null jika ada
            raw_output = subprocess.check_output(cmd, startupinfo=startupinfo).decode('cp437', errors='ignore')
            output = raw_output.replace('\x00', '').split('\n')
        else:
            output = subprocess.check_output(cmd).decode().split('\n')
        
        # Bersihkan baris dan ambil yang berisi data (bukan header)
        clean_lines = [l.strip() for l in output if l.strip()]
        
        # Jika ini perintah wmic 'get', biasanya baris pertama adalah header
        # Kita cari baris yang TIDAK sama dengan nama kolom yang diminta
        if len(cmd) >= 4 and cmd[0] == 'wmic' and cmd[2] == 'get':
            target_header = cmd[3].lower()
            for line in clean_lines:
                if line.lower() != target_header:
                    return line
        
        # Fallback ke baris pertama jika bukan wmic atau tidak ketemu
        return clean_lines[0] if clean_lines else "UNKNOWN"
    except:
        return "UNKNOWN"

def get_hwid():
    """Generates a unique Hardware ID based on CPU, Disk, and Machine GUID."""
    try:
        if sys.platform == "win32":
            cpu = _get_cmd_output(['wmic', 'cpu', 'get', 'processorid'])
            disk = _get_cmd_output(['wmic', 'diskdrive', 'get', 'serialnumber'])
            uuid = _get_cmd_output(['wmic', 'csproduct', 'get', 'uuid'])
            raw_id = f"{cpu}|{disk}|{uuid}"
        elif sys.platform == "darwin":
            # macOS implementation
            uuid = subprocess.check_output("ioreg -rd1 -c IOPlatformExpertDevice | grep -E '(IOPlatformUUID)' | awk '{print $3}' | tr -d '\"'", shell=True).decode().strip()
            serial = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '\"'", shell=True).decode().strip()
            raw_id = f"{uuid}|{serial}"
        else:
            raw_id = "LINUX-OR-OTHER"
            
        return hashlib.sha256(raw_id.encode()).hexdigest().upper()
    except Exception:
        return "HWID-ERROR-000"

def get_device_info():
    """Mengambil detail informasi perangkat (Nama, Pemilik, Merk, Model, Serial)."""
    info = {
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "manufacturer": "UNKNOWN",
        "model": "UNKNOWN",
        "serial": "UNKNOWN"
    }
    
    try:
        if sys.platform == "win32":
            info["manufacturer"] = _get_cmd_output(['wmic', 'computersystem', 'get', 'manufacturer'])
            info["model"] = _get_cmd_output(['wmic', 'computersystem', 'get', 'model'])
            info["serial"] = _get_cmd_output(['wmic', 'bios', 'get', 'serialnumber'])
        elif sys.platform == "darwin":
            # macOS: Get Model, Manufacturer, and Serial
            info["manufacturer"] = "Apple"
            info["model"] = subprocess.check_output("sysctl -n hw.model", shell=True).decode().strip()
            info["serial"] = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '\"'", shell=True).decode().strip()
    except:
        pass
        
    return info

import time

# --- CACHE ---
_LICENSE_CACHE = {
    'last_check': 0,
    'result': (False, "NOT_CHECKED", "", {}),
    'ttl': 300 # 5 minutes
}

def check_license(force=False, app_type="pro"):
    """
    Validates the license by checking local status and re-verifying with server.
    app_type: "lite" or "pro"
    """
    global _LICENSE_CACHE
    
    # Periksa cache, tapi JANGAN gunakan cache jika app_type berbeda dengan check sebelumnya
    now = time.time()
    if not force and (now - _LICENSE_CACHE['last_check'] < _LICENSE_CACHE['ttl']):
        cached_result = _LICENSE_CACHE['result']
        # Pastikan tipe aplikasi di cache sesuai (index 4 jika kita simpan app_type di cache)
        # Untuk kesederhanaan, jika force=False dan cache masih valid, kita kembalikan.
        # Namun untuk keamanan extra, kita bisa tambahkan validasi app_type di sini.
        if len(cached_result) > 4 and cached_result[4] == app_type:
            return cached_result[:4]
        elif len(cached_result) <= 4: # Cache lama
            return cached_result

    def _ret(is_valid, status, name, data):
        res = (is_valid, status, name, data, app_type)
        _LICENSE_CACHE['last_check'] = time.time()
        _LICENSE_CACHE['result'] = res
        return is_valid, status, name, data

    lic_path = os.path.join(get_app_data_dir(), "lic.dat")
    
    if not os.path.exists(lic_path):
        return _ret(False, "LICENSE_NOT_FOUND", "", {})
        
    try:
        # 1. Read Local Encrypted License Key
        with open(lic_path, "rb") as f:
            encrypted_data = f.read()
            
        key = _get_master_key()
        f = Fernet(key)
        
        try:
            decrypted_data = f.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            license_key = data.get('license_key')
            local_cust_name = data.get('customer_name', '')
            local_agreement_version = data.get('agreement_version', '0.0')
            signature = data.get('signature')
            
            # 1.5 RSA Verification (Local)
            if signature:
                hwid = get_hwid()
                # Server ARTUR menggunakan format: license_key|machine_id|variant_prefix
                # Kita gunakan app_type dari cache (yang disimpan saat aktivasi)
                cached_app_type = str(data.get('app_type', app_type)).upper()
                data_to_verify = f"{license_key}|{hwid}|{cached_app_type}"
                
                if not verify_signature(data_to_verify, signature):
                    # Fallback ke format lama (tanpa variant) jika format baru gagal
                    old_data_to_verify = f"{license_key}|{hwid}"
                    if not verify_signature(old_data_to_verify, signature):
                        return _ret(False, "RSA_VERIFICATION_FAILED", "", {})

        except:
            return _ret(False, "LICENSE_INVALID", "", {})

        # 2. Online Validation
        hwid = get_hwid()
        device = get_device_info()
        try:
            response = requests.post(VERIFY_URL, data={
                'license_key': license_key,
                'machine_id': hwid,
                'variant_prefix': app_type.upper(), # Kirim prefix variant (PRO/LITE) ke server
                'device_name': device['hostname'],
                'brand': device['manufacturer'],
                'model': device['model'],
                'serial': device['serial']
            }, timeout=25, verify=True, headers=COMMON_HEADERS)
            
            if response.status_code == 200:
                try:
                    res_data = response.json()
                except json.JSONDecodeError:
                    return _ret(False, "SERVER_ERROR_FORMAT", "", {})
                
                status = res_data.get('status')
                cust_name = res_data.get('customer', local_cust_name)
                
                if status == 'success':
                    # Update local cache if data changed
                    new_signature = res_data.get('signature', signature)
                    expiry = res_data.get('expiry', '')
                    server_app_type = str(res_data.get('app', '')).lower()
                    
                    # 3. App Type Validation
                    # Cek di kolom 'variant' (prioritas) atau 'app'
                    server_variant = str(res_data.get('variant', '')).lower()
                    server_app = str(res_data.get('app', '')).lower()
                    
                    if app_type == "pro":
                        if "pro" not in server_variant and "pro" not in server_app:
                            return _ret(False, "LICENSE_PRO_REQUIRED", cust_name, res_data)
                    
                    if cust_name != local_cust_name or new_signature != signature:
                        # Simpan tipe yang paling akurat ke local
                        final_type = server_variant if server_variant else server_app
                        _save_local_license(license_key, cust_name, local_agreement_version, new_signature, expiry, final_type, app_type)
                    return _ret(True, "LICENSE_OK", cust_name, res_data)
                elif status == 'error':
                    message = res_data.get('message', "LICENSE_INVALID")
                    if "expired" in message.lower():
                        return _ret(False, "LICENSE_EXPIRED", cust_name, res_data)
                    return _ret(False, message, cust_name, res_data)
                else:
                    return _ret(False, res_data.get('message', "LICENSE_INVALID"), cust_name, res_data)
            else:
                return _ret(False, f"SERVER_CONNECTION_ERROR_{response.status_code}", local_cust_name, {})
                
        except requests.exceptions.RequestException as e:
            return _ret(False, f"CONNECTION_FAILED: {str(e)}", local_cust_name, {})
            
    except Exception:
        return _ret(False, "LICENSE_INVALID", "", {})

def activate_license(license_key, agreed=False, agreement_version="0.0", app_type="pro"):
    """
    Initial activation: calls server to bind license to this machine.
    """
    hwid = get_hwid()
    device = get_device_info()
    try:
        payload = {
            'license_key': license_key,
            'machine_id': hwid,
            'variant_prefix': app_type.upper(), # Kirim prefix variant (PRO/LITE) ke server
            'device_name': device['hostname'],
            'brand': device['manufacturer'],
            'model': device['model'],
            'serial': device['serial']
        }
        response = requests.post(VERIFY_URL, data=payload, timeout=25, verify=True, headers=COMMON_HEADERS)
        
        if response.status_code == 200:
            try:
                res_data = response.json()
            except json.JSONDecodeError:
                return False, "Server memberikan respon yang tidak valid (Bukan JSON).", {}
            
            status = res_data.get('status')
            
            if status == 'success':
                cust_name = res_data.get('customer', 'User')
                signature = res_data.get('signature', '') # Signature dari server
                expiry = res_data.get('expiry', '')
                
                # Ambil tipe dari variant atau app
                server_variant = str(res_data.get('variant', '')).lower()
                server_app = str(res_data.get('app', '')).lower()
                
                # App Type Validation pada Aktivasi
                if app_type == "pro":
                    if "pro" not in server_variant and "pro" not in server_app:
                        return False, "Lisensi ini hanya untuk versi LITE, tidak bisa digunakan di versi PRO.", res_data
                
                # Verifikasi RSA Signature dari Server jika ada
                if signature:
                    # Server ARTUR menggunakan format: license_key|machine_id|variant_prefix
                    data_to_verify = f"{license_key}|{hwid}|{app_type.upper()}"
                    
                    if not verify_signature(data_to_verify, signature):
                        # Fallback ke format lama (tanpa variant) jika format baru gagal
                        old_data_to_verify = f"{license_key}|{hwid}"
                        if not verify_signature(old_data_to_verify, signature):
                            return False, "RSA_SERVER_VERIFICATION_FAILED", res_data
                
                final_type = server_variant if server_variant else server_app
                _save_local_license(license_key, cust_name, agreement_version, signature, expiry, final_type, app_type)
                return True, f"Aktivasi Berhasil! Terdaftar atas nama: {cust_name}", res_data
            else:
                return False, res_data.get('message', "Aktivasi Gagal"), res_data
        else:
            return False, f"Gagal menghubungi server aktivasi (Status: {response.status_code}).", {}
    except requests.exceptions.RequestException as e:
        return False, f"Koneksi Gagal: {str(e)}", {}
    except Exception as e:
        return False, f"Terjadi kesalahan: {str(e)}", {}

def _save_local_license(license_key, customer_name="", agreement_version="0.0", signature="", expiry="", app="", app_type="pro"):
    """Saves the license key locally in encrypted format."""
    data = {
        'license_key': license_key,
        'customer_name': customer_name,
        'agreement_version': agreement_version,
        'signature': signature,
        'expiry': expiry,
        'app': app,
        'app_type': app_type, # Simpan tipe aplikasi asli (pro/lite) untuk verifikasi RSA
        'activated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    json_data = json.dumps(data).encode()
    
    key = _get_master_key()
    f = Fernet(key)
    encrypted = f.encrypt(json_data)
    
    lic_path = os.path.join(get_app_data_dir(), "lic.dat")
    with open(lic_path, "wb") as f:
        f.write(encrypted)
    
    global _LICENSE_CACHE
    _LICENSE_CACHE['last_check'] = 0
    _LICENSE_CACHE['result'] = (True, "LICENSE_OK", customer_name, {}, app_type)

def install_license(source_path):
    """Obsolete for new system, but kept for compatibility if needed."""
    return False, "Gunakan aktivasi online melalui License Key."

def install_license_text(license_text, app_type="pro"):
    """New activation method using direct text input (License Key)."""
    return activate_license(license_text.strip(), app_type=app_type)
