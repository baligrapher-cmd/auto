import json
import re
import os

def convert_txt_to_json():
    txt_path = r"c:\Users\PRAMANA VISUAL\Desktop\AutoYu_V3_SourceCode_Backup\FotoTree_Tools\full_fototree_list.txt"
    json_path = r"c:\Users\PRAMANA VISUAL\Desktop\AutoYu_V3_SourceCode_Backup\FotoTree_Tools\full_fototree_list.json"
    db_path = r"c:\Users\PRAMANA VISUAL\Desktop\AutoYu_V3_SourceCode_Backup\FotoTree_Tools\autoyu_tree_location_db.json"
    
    if not os.path.exists(txt_path):
        print(f"Error: {txt_path} not found")
        return

    locations = []
    # Pattern: Name (ID: ID) - [lat, lon]
    pattern = re.compile(r"^(.*)\s\(ID:\s([a-zA-Z0-9]+)\)\s-\s+\[([-.\d]+),\s+([-.\d]+)\]")
    
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            match = pattern.match(line)
            if match:
                name = match.group(1).strip()
                id_str = match.group(2)
                lat = float(match.group(3))
                lon = float(match.group(4))
                
                # Generate alias: lowercase alphanumeric only
                alias = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
                
                item = {
                    "id": id_str,
                    "alias": alias,
                    "name": name,
                    "location": {
                        "name": "",
                        "latitude": lat,
                        "longitude": lon
                    },
                    "category": "place",
                    "pinpoint_icon": "https://cdn.fotoyu.com/tree/icons/pinpoint-place.png",
                    "leaf_count": 0,
                    "is_generated": False,
                    "created_at": "2024-05-11T00:00:00Z"
                }
                locations.append(item)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(locations, f, indent=4)
    
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(locations, f, indent=4)
    
    print(f"Successfully converted {len(locations)} locations to {json_path} and {db_path}")

if __name__ == "__main__":
    convert_txt_to_json()
