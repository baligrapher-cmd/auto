
import sys
import os
from playwright.sync_api import sync_playwright

print("Python executable:", sys.executable)
print("Python version:", sys.version)

try:
    print("Testing sync_playwright()...")
    p = sync_playwright()
    print("p type:", type(p))
    print("p attrs:", dir(p))
    
    print("\nNow trying with context manager...")
    with sync_playwright() as p_obj:
        print("p_obj type:", type(p_obj))
        print("p_obj attrs:", dir(p_obj))
        print("Success!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    print("Traceback:", traceback.format_exc())
