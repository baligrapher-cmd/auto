
import json
import os
import subprocess
import sys

def process_locations():
    # Cek apakah kita perlu menjalankan sync terlebih dahulu
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    sync_script = os.path.join(tools_dir, "sync_locations.py")
    
    print("🔄 Menjalankan sinkronisasi data terbaru dari web...")
    try:
        # Gunakan python yang sama dengan yang menjalankan script ini
        subprocess.run([sys.executable, sync_script], check=True)
    except Exception as e:
        print(f"⚠️ Gagal sinkronisasi otomatis: {e}")
        print(" menggunakan data lokal yang ada...")

    json_input = os.path.join(tools_dir, "full_fototree_list.json")
    try:
        with open(json_input, "r", encoding="utf-8") as f:
            trees = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    mapping = []
    for t in trees:
        name = t.get("name", "Unknown")
        tree_id = t.get("id", "Unknown")
        loc_data = t.get("location", {})
        loc_name = loc_data.get("name", "")
        lat = loc_data.get("latitude")
        lng = loc_data.get("longitude")
        
        mapping.append({
            "name": name,
            "id": tree_id,
            "location_name": loc_name,
            "latitude": lat,
            "longitude": lng
        })

    # Sort by name
    mapping.sort(key=lambda x: x["name"])

    # Save as JSON for AutoYu logic
    db_json = os.path.join(tools_dir, "autoyu_tree_location_db.json")
    with open(db_json, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4)

    # Save as readable TXT for User
    db_txt = os.path.join(tools_dir, "autoyu_tree_location_db.txt")
    with open(db_txt, "w", encoding="utf-8") as f:
        f.write(f"{'FOTOTREE NAME':<50} | {'LATITUDE':<12} | {'LONGITUDE':<12} | {'LOCATION NAME'}\n")
        f.write("-" * 120 + "\n")
        for m in mapping:
            f.write(f"{m['name'][:50]:<50} | {str(m['latitude']):<12} | {str(m['longitude']):<12} | {m['location_name']}\n")

    print(f"✅ Berhasil memproses {len(mapping)} lokasi.")

if __name__ == "__main__":
    process_locations()
