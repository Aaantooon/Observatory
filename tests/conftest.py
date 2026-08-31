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
        self.created_users = []
        self.active_reviews = {}
        self.comments = []
        self.sent_for_review = []

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

    # -- методы, нужные для тестов на уровне handlers.py (см. test_handlers.py) --

    def get_or_create_user(self, vk_id, first_name, last_name):
        self.created_users.append((vk_id, first_name, last_name))
        return {"id": vk_id, "vk_id": vk_id, "first_name": first_name, "last_name": last_name}

    def get_user_results(self, vk_id):
        return list(self.results)

    def get_active_review(self, vk_id):
        return self.active_reviews.get(vk_id)

    def set_active_review(self, vk_id, review_id=1, status="in_review"):
        """Тестовый хелпер: имитирует наличие активной проверки у пользователя."""
        self.active_reviews[vk_id] = {"id": review_id, "status": status}

    def add_comment(self, review_id, comment, is_admin=False):
        self.comments.append({"review_id": review_id, "comment": comment, "is_admin": is_admin})
        return {"status": "ok"}

    def send_for_review(self, user_vk_id, exercise_type, data):
        entry = {"user_vk_id": user_vk_id, "exercise_type": exercise_type, "data": data}
        self.sent_for_review.append(entry)
        return {"review_id": len(self.sent_for_review)}

    def get_due_notifications(self):
        return []

    def get_pending_admin_comments(self):
        return []

    def mark_notification_sent(self, notification_id):
        return True

    def mark_comment_sent(self, review_id, comment_index):
        return None


class FakeNotificationSystem:
    """Заменяет NotificationSystem в тестах handlers.py — тот же интерфейс,
    но start() не поднимает фоновый поток (не нужен и не должен мешать тестам)."""

    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def setup_reminder_to_continue(self, user_id, kind, hours=1):
        return None

    def setup_diary_reminder(self, user_id, time_str):
        return None
