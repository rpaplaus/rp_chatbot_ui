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
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_history(self):
        with open(self.file_path, "w") as f:
            json.dump(self.history, f, indent=4)

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})
        self.save_history()

    def get_history(self):
        return self.history
        
    def clear_history(self):
        self.history = []
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
