
import requests

VERIFY_URL = "https://api.pramana.web.id/verify.php"
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://api.pramana.web.id",
    "Referer": "https://api.pramana.web.id/verify.php",
    "Connection": "keep-alive",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="148", "Microsoft Edge";v="148"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest"
}

def test_request():
    payload = {
        "license_key": "TEST-KEY",
        "machine_id": "TEST-HWID",
        "variant_prefix": "PRO",
        "device_name": "TEST-DEVICE",
        "brand": "TEST-BRAND",
        "model": "TEST-MODEL",
        "serial": "TEST-SERIAL"
    }

    print("Testing with Content-Type: application/x-www-form-urlencoded")
    try:
        response = requests.post(VERIFY_URL, data=payload, headers=COMMON_HEADERS, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Text: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n\nTesting without Content-Type header (let requests set it automatically)")
    try:
        headers_without_content_type = {k: v for k, v in COMMON_HEADERS.items() if k != "Content-Type"}
        response = requests.post(VERIFY_URL, data=payload, headers=headers_without_content_type, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Response Text: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_request()
