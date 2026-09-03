import logging
from abc import ABC, abstractmethod
from vk_adapter import VkAdapter

logger = logging.getLogger(__name__)


class BaseExercise(ABC):
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        # self.platform — общий интерфейс отправки сообщений (см.
        # platform_bots/README.md, шаг 3): send_message ниже вызывает его,
        # а не self.vk напрямую, чтобы упражнение не было завязано на VK
        # конкретно. Два случая: (1) vk_session — настоящий VkApi (как
        # всегда было для VK) — оборачиваем в VkAdapter; lambda, а не
        # просто VkAdapter(vk_session), потому что self.vk можно подменить
        # уже после создания экземпляра (см. vk_adapter.py, docstring
        # VkAdapter.__init__), и адаптер должен видеть актуальное значение.
        # (2) vk_session уже сам реализует интерфейс отправки (например
        # TelegramAdapter из main_telegram.py, шаг 4) — используем его
        # напрямую, ничего не оборачивая: hasattr-проверка отличает готовый
        # адаптер (есть свой send_message) от сырой VK-сессии (метод
        # называется method, не send_message).
        if hasattr(vk_session, 'send_message'):
            self.platform = vk_session
        else:
            self.platform = VkAdapter(lambda: self.vk)
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
        try:
            self.platform.send_message(user_id, message, keyboard)
        except Exception as e:
            # Отправка не должна ронять вызывающий код (например, _finish()
            # после того, как save_result()/delete_progress() уже отработали)
            # — иначе сбой самого сообщения оставит пользователя без
            # завершающего экрана и клавиатуры.
            logger.error(f"Send message error to {user_id}: {e}")

    def save_progress(self, user_id, data):
        return self.api.save_progress(user_id, self.get_exercise_type(), data)

    def get_progress(self, user_id):
        return self.api.get_progress(user_id, self.get_exercise_type())

    def _progress_unavailable_notice(self, user_id):
        """Вызывать, когда get_progress() вернул None — это значит сбой
        сети/сервера, а НЕ «прогресса действительно не было». Не путать
        одно с другим молча — иначе сохранённый прогресс может незаметно
        потеряться из вида пользователя."""
        self.send_message(
            user_id,
            "⚠️ Не получилось загрузить твой сохранённый прогресс — сервис "
            "временно недоступен. Продолжаю с чистого листа; если прогресс "
            "был, попробуй зайти чуть позже."
        )

    def delete_progress(self, user_id):
        return self.api.delete_progress(user_id, self.get_exercise_type())

    def save_result(self, user_id, data):
        return self.api.save_result(user_id, self.get_exercise_type(), data)

    def _report_save_failure(self, user_id, session, keyboard=None):
        """Сервер не подтвердил сохранение результата (сеть/сервер недоступны).
        Не терять ответы (сохраняем прогресс как резервную копию) и честно
        сказать пользователю, а не показывать «Путь завершён», как будто
        всё прошло успешно."""
        self.save_progress(user_id, session)
        self.send_message(
            user_id,
            "⚠️ Не получилось сохранить результат — сервис на секунду недоступен.\n"
            "Ничего не потеряно, твои ответы сохранены как черновик. "
            "Попробуй завершить ещё раз той же кнопкой через минуту.",
            keyboard
        )

    def end_session(self, user_id):
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

    def _get_separator(self):
        return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

    def _get_progress_bar(self, count, target):
        """Луч фонарика, пробивающий туман: ▮ — уже освещённый участок
        пути, · — ещё скрытый в тумане. Та же тема и та же формула, что и
        в stress_search.py (единственное упражнение, где раньше её не
        было) — единый прогресс-бар по всему боту вместо отдельного
        нейтрального ▰▱-варианта здесь."""
        if not target:
            return ""
        percent = min(100, int((count / target) * 100))
        segments = 20
        filled_n = percent * segments // 100
        filled = "▮" * filled_n
        empty = "·" * (segments - filled_n)
        return f"🔦{filled}{empty} {percent}%"

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