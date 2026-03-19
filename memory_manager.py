import json
import os
import uuid

MEMORY_DIR = "memory"

class MemoryManager:
    def __init__(self, session_id=None):
        if not os.path.exists(MEMORY_DIR):
            os.makedirs(MEMORY_DIR)
        self.session_id = session_id or str(uuid.uuid4())
        self.file_path = os.path.join(MEMORY_DIR, f"{self.session_id}.json")
        self.history = []
        self.session_name = "New Chat"
        self._load_history()

    def _load_history(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.history = data
                    elif isinstance(data, dict):
                        self.history = data.get("history", [])
                        self.session_name = data.get("name", "New Chat")
            except Exception:
                pass

    def save_history(self):
        with open(self.file_path, "w") as f:
            json.dump({"name": self.session_name, "history": self.history}, f, indent=4)

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})
        self.save_history()

    def get_history(self):
        return self.history
        
    def clear_history(self):
        self.history = []
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def rename_session(self, new_name):
        self.session_name = new_name
        self.save_history()

    @staticmethod
    def get_all_sessions():
        if not os.path.exists(MEMORY_DIR):
            return []
        sessions = []
        for filename in os.listdir(MEMORY_DIR):
            if filename.endswith(".json"):
                session_id = filename[:-5]
                filepath = os.path.join(MEMORY_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        name = "New Chat"
                        if isinstance(data, dict):
                            name = data.get("name", name)
                        sessions.append({"id": session_id, "name": name})
                except Exception:
                    pass
        # Sort by last modified time descending
        sessions.sort(key=lambda s: os.path.getmtime(os.path.join(MEMORY_DIR, f"{s['id']}.json")), reverse=True)
        return sessions

    @staticmethod
    def delete_session(session_id):
        filepath = os.path.join(MEMORY_DIR, f"{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
