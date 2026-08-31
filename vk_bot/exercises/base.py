from abc import ABC, abstractmethod
from vk_api.utils import get_random_id


class BaseExercise(ABC):
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.user_sessions = {}

    @abstractmethod
    def get_exercise_type(self):
        pass

    @abstractmethod
    def get_exercise_title(self):
        pass

    @abstractmethod
    def start(self, user_id):
        pass

    @abstractmethod
    def handle_message(self, user_id, text):
        pass

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    def save_progress(self, user_id, data):
        return self.api.save_progress(user_id, self.get_exercise_type(), data)

    def get_progress(self, user_id):
        return self.api.get_progress(user_id, self.get_exercise_type())

    def delete_progress(self, user_id):
        return self.api.delete_progress(user_id, self.get_exercise_type())

    def save_result(self, user_id, data):
        return self.api.save_result(user_id, self.get_exercise_type(), data)

    def end_session(self, user_id):
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

    def _get_separator(self):
        return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

    def _get_progress_bar(self, count, target):
        if not target:
            return ""
        percent = min(100, int((count / target) * 100))
        filled = "▰" * (percent // 5)
        empty = "▱" * (20 - len(filled))
        return f"▰{filled}{empty}▱ {percent}%"

    def _score_emoji(self, score):
        """Цветовой индикатор оценки 1-10: 🔴 низкая, 🟡 средняя, 🟢 высокая."""
        if not isinstance(score, (int, float)):
            return "⚪"
        if score <= 3:
            return "🔴"
        elif score <= 6:
            return "🟡"
        return "🟢"

    def _milestone_line(self, count, target):
        """Поздравление на четверти/половине/трёх четвертях пути к target —
        None, если count не попадает ни на одну из этих отметок."""
        if not target:
            return None
        checkpoints = sorted(set(x for x in (target // 4, target // 2, target * 3 // 4) if x))
        if count not in checkpoints:
            return None
        idx = checkpoints.index(count)
        phrases = [
            "🌟 Четверть пути позади!",
            "🔥 Уже половина пути!",
            "🚀 Три четверти позади — почти у цели!",
        ]
        return phrases[idx] if idx < len(phrases) else f"🌟 {count}/{target} позади!"