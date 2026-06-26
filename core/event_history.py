import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from core.license import get_app_data_dir


class EventHistory:
    def __init__(self):
        self.app_data_dir = get_app_data_dir()
        self.history_file = os.path.join(self.app_data_dir, "event_history.json")
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir, exist_ok=True)

    def load_history(self) -> List[Dict]:
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[EventHistory] Error loading: {e}")
        return []

    def save_history(self, history: List[Dict]):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EventHistory] Error saving: {e}")

    def add_event(self, event_data: Dict):
        history = self.load_history()
        event_data['id'] = int(time.time() * 1000)
        event_data['timestamp'] = datetime.now().isoformat()
        history.insert(0, event_data)
        # Keep last 100 events only
        if len(history) > 100:
            history = history[:100]
        self.save_history(history)

    def delete_event(self, event_id: int):
        history = self.load_history()
        history = [e for e in history if e.get('id') != event_id]
        self.save_history(history)

    def clear_all_history(self):
        self.save_history([])
