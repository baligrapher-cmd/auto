
import os
import json
from core.license import get_app_data_dir


def get_presets_file_path():
    return os.path.join(get_app_data_dir(), "presets.json")


def load_presets():
    file_path = get_presets_file_path()
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("presets", [])
    except Exception:
        return []


def save_presets(presets):
    file_path = get_presets_file_path()
    data = {"presets": presets}
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def add_preset(name, price, description, location=None, fototree=None):
    presets = load_presets()
    new_preset = {
        "id": f"preset_{int(os.times()[4])}",  # Unique ID based on timestamp
        "name": name,
        "price": price,
        "description": description,
        "location": location,
        "fototree": fototree
    }
    presets.append(new_preset)
    save_presets(presets)
    return new_preset


def delete_preset(preset_id):
    presets = load_presets()
    presets = [p for p in presets if p.get("id") != preset_id]
    save_presets(presets)
