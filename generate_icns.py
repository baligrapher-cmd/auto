import os
import sys
from PIL import Image

def create_icns(icon_path, output_path):
    if not os.path.exists(icon_path):
        print(f"Error: Source icon not found at {icon_path}")
        return False
    
    try:
        img = Image.open(icon_path)
        # ICNS requires specific sizes: 16, 32, 64, 128, 256, 512, 1024
        # Pillow's ICNS support is better when we provide these sizes
        # But for a quick conversion, we ensure it's RGBA
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        img.save(output_path, format='ICNS')
        if os.path.exists(output_path):
            print(f"Successfully created: {output_path} (Size: {os.path.getsize(output_path)} bytes)")
            return True
        else:
            print(f"Error: {output_path} was not created even though save() returned.")
            return False
    except Exception as e:
        print(f"Failed to create ICNS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Check common locations
    candidates = ["icon.ico", "assets/icon.ico", "../icon.ico", "../assets/icon.ico"]
    src = None
    for c in candidates:
        if os.path.exists(c):
            src = c
            break
            
    if not src:
        print("Critical Error: No source icon.ico found in any candidate location.")
        sys.exit(0) # Exit gracefully so build continues without icon
    
    dest = "icon.icns"
    if create_icns(src, dest):
        print("ICNS generation process completed successfully.")
    else:
        print("ICNS generation process failed.")

