"""VK-реализация интерфейса отправки сообщений для упражнений
(vk_bot/exercises/base.py, vk_bot/exercises/stress_search.py) — шаг 3 из
плана миграции в platform_bots/README.md ("Завести self.platform в
BaseExercise").

По форме (send_message(user_id, text, keyboard=None) + run(on_message))
совпадает с platform_bots/base_adapter.py::MessagingAdapter, но НЕ
импортирует его и не наследует напрямую: vk_bot/main.py запускается как
отдельный скрипт (`python vk_bot/main.py`), и в этом случае в sys.path
попадает только сама папка vk_bot/, а не корень репозитория — прямой
импорт из соседней папки platform_bots/ мог бы неожиданно сломаться в
проде при любой перестановке путей запуска. Здесь просто тот же набор
методов, совместимый по форме, без риска для уже работающего бота.
"""
from vk_api.utils import get_random_id

from keyboards import to_vk_keyboard


class VkAdapter:
    def __init__(self, get_vk_session):
        """get_vk_session — не сам объект vk_session, а функция без
        аргументов, которая возвращает его АКТУАЛЬНОЕ значение на момент
        вызова (обычно `lambda: self.vk`). Это важно: код упражнений (и
        тесты — см. tests/test_exercises.py, `ex2.vk = ex.vk`) подменяет
        self.vk уже ПОСЛЕ создания экземпляра упражнения (например при
        восстановлении прогресса в новый экземпляр). Если бы VkAdapter
        захватывал vk_session один раз в конструкторе, такая подмена
        молча переставала бы работать, и сообщения продолжали бы уходить
        через старый (уже не используемый) vk_session."""
        self._get_vk_session = get_vk_session

    def send_message(self, user_id, text, keyboard=None):
        vk = self._get_vk_session()
        vk.method('messages.send', {
            'user_id': user_id,
            'message': text,
            'random_id': get_random_id(),
            'keyboard': to_vk_keyboard(keyboard),
        })

    def run(self, on_message):
        """Приём входящих сообщений для VK устроен отдельно — через
        longpoll-цикл в vk_bot/main.py, а не через этот адаптер. Метод
        существует только для формального сходства с MessagingAdapter."""
        raise NotImplementedError(
            "VkAdapter не запускает приём сообщений — для VK это делает "
            "отдельный longpoll-цикл в vk_bot/main.py"
        )
