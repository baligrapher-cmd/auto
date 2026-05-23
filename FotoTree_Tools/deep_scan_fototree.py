import requests
import json
import time

def deep_scan():
    try:
        with open("session_token.txt", "r") as f:
            token = f.read().strip()
    except:
        print("Error: session_token.txt not found.")
        return

    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fotoyu.com",
        "Referer": "https://www.fotoyu.com/"
    }

    all_trees = {}
    
    # 1. GRID SCAN (BBOX)
    # Indonesia: Longitude 94 to 142, Latitude -12 to 8
    # Divide into smaller boxes to overcome API limits
    print("Starting Grid Scan...")
    lon_steps = 6 # ~8 degrees per step
    lat_steps = 4 # ~5 degrees per step
    
    for i in range(lon_steps):
        for j in range(lat_steps):
            min_lon = 94 + (i * 8)
            max_lon = min_lon + 8
            min_lat = -12 + (j * 5)
            max_lat = min_lat + 5
            
            bbox = f"[[{min_lon}, {min_lat}], [{max_lon}, {max_lat}]]"
            url = "https://api.fotoyu.com/tree/v2/trees"
            params = {"bbox": bbox, "zoom_level": 10}
            
            try:
                resp = requests.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    results = resp.json().get("result", [])
                    for t in results:
                        all_trees[t["id"]] = t
                    print(f"  BBOX {bbox}: Found {len(results)} trees. Total unique: {len(all_trees)}")
                else:
                    print(f"  BBOX {bbox}: Error {resp.status_code}")
                time.sleep(0.2)
            except Exception as e:
                print(f"  BBOX {bbox}: Exception {e}")

    # 2. KEYWORD SEARCH SCAN
    print("\nStarting Keyword Search Scan...")
    keywords = [
        "", "Run", "Marathon", "Fun", "Race", "Jakarta", "Bali", "Bandung", "Surabaya", 
        "Medan", "Jogja", "Semarang", "Makassar", "Palembang", "Batam", "Pekanbaru",
        "Malang", "Solo", "Bogor", "Tangerang", "Bekasi", "Depok", "Lari", "Event",
        "Park", "Alun", "Stadion", "GOR", "Pantai", "Gunung", "Trail", "Road"
    ]
    
    search_url = "https://api.fotoyu.com/tree/v2/trees/search"
    for kw in keywords:
        params = {"q": kw, "limit": 100}
        try:
            resp = requests.get(search_url, headers=headers, params=params)
            if resp.status_code == 200:
                results = resp.json().get("result", [])
                new_count = 0
                for t in results:
                    if t["id"] not in all_trees:
                        all_trees[t["id"]] = t
                        new_count += 1
                print(f"  Keyword '{kw}': Found {len(results)} results, {new_count} new. Total unique: {len(all_trees)}")
            else:
                print(f"  Keyword '{kw}': Error {resp.status_code}")
            time.sleep(0.2)
        except Exception as e:
            print(f"  Keyword '{kw}': Exception {e}")

    # 3. SAVE RESULTS
    print(f"\nFinal count of unique FotoTrees: {len(all_trees)}")
    
    all_results = list(all_trees.values())
    all_results.sort(key=lambda x: x.get("name", ""))
    
    with open("full_fototree_list.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4)
        
    with open("full_fototree_list.txt", "w", encoding="utf-8") as f:
        for t in all_results:
            loc = t.get("location", {})
            f.write(f"{t.get('name')} (ID: {t.get('id')}) - {loc.get('name', 'No Location')} [{loc.get('latitude')}, {loc.get('longitude')}]\n")

    # Update DB
    db_entries = []
    for t in all_results:
        loc = t.get("location", {})
        db_entries.append({
            "name": t.get("name"),
            "id": t.get("id"),
            "location_name": loc.get("name", ""),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude")
        })
    db_entries.sort(key=lambda x: x["name"])
    with open("autoyu_tree_location_db.json", "w", encoding="utf-8") as f:
        json.dump(db_entries, f, indent=4)
        
    print("Database updated with deep scan results.")

if __name__ == "__main__":
    deep_scan()
