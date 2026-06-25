
from core.license import activate_license

LICENSE_KEY = "AUTOYOU-PRO-MOMOTO-33C5"
print(f"Testing license activation with key: {LICENSE_KEY}")

success, msg, res_data = activate_license(LICENSE_KEY, agreed=True, agreement_version="2.0", app_type="pro")

print(f"\nSuccess: {success}")
print(f"Message: {msg}")
print(f"Response Data: {res_data}")
