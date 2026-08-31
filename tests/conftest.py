import json
import sys
from pathlib import Path

# tests/ лежит рядом с vk_bot/ в корне репозитория
VK_BOT_DIR = Path(__file__).resolve().parent.parent / "vk_bot"
sys.path.insert(0, str(VK_BOT_DIR))


class FakeVK:
    """Заменяет vk_session — просто записывает все отправленные сообщения."""

    def __init__(self):
        self.sent = []  # list of dict(user_id, message, keyboard)

    def method(self, name, params):
        assert name == "messages.send"
        keyboard_raw = params.get("keyboard")
        buttons = []
        if keyboard_raw:
            kb = json.loads(keyboard_raw)
            for row in kb.get("buttons", []):
                for btn in row:
                    buttons.append(btn["action"]["label"])
        self.sent.append({
            "user_id": params["user_id"],
            "message": params["message"],
            "buttons": buttons,
        })

    @property
    def last(self):
        return self.sent[-1]

    @property
    def last_message(self):
        return self.sent[-1]["message"]

    @property
    def last_buttons(self):
        return self.sent[-1]["buttons"]


class FakeAPIClient:
    """Заменяет APIClient — хранит прогресс/результаты в памяти вместо Django API."""

    def __init__(self):
        self.progress_store = {}  # (uid, exercise_type) -> data
        self.results = []  # list of dict(user_vk_id, exercise_type, result_data)
        self.deleted_progress_calls = []

    def save_progress(self, user_vk_id, exercise_type, data):
        self.progress_store[(user_vk_id, exercise_type)] = dict(data)
        return {"status": "ok"}

    def get_progress(self, user_vk_id, exercise_type):
        data = self.progress_store.get((user_vk_id, exercise_type))
        if data is None:
            return {"exists": False}
        return {"exists": True, "data": data}

    def delete_progress(self, user_vk_id, exercise_type):
        self.deleted_progress_calls.append((user_vk_id, exercise_type))
        self.progress_store.pop((user_vk_id, exercise_type), None)
        return True

    def save_result(self, user_vk_id, exercise_type, result_data):
        entry = {
            "user_vk_id": user_vk_id,
            "exercise_type": exercise_type,
            "result_data": result_data,
        }
        self.results.append(entry)
        return {"status": "saved"}

    def update_streak(self, user_vk_id):
        return {"streak": 1}

    def results_for(self, exercise_type):
        return [r for r in self.results if r["exercise_type"] == exercise_type]
