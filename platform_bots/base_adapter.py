"""Заготовка архитектуры мультиплатформенных ботов — в
СВОДКА_ПРОЕКТА.md числилась в разделе «Не начато / в планах»
(«Мультиплатформенные боты (Telegram и др.) — архитектура пока не
заложена, только VK»).

ВАЖНО: ничего в этом пакете не подключено к живому боту (vk_bot/) и не
запускается ни одним systemd-сервисом. Это черновик интерфейса и
несколько черновых реализаций под конкретные платформы — чтобы было с
чего начать, когда до этого дойдут руки, без риска для уже работающего
VK-бота. См. platform_bots/README.md — там план, как реально подключить
это к существующим упражнениям (vk_bot/exercises/*), когда решите, что
пора.

Идея в двух словах: сейчас vk_bot/exercises/base.py::BaseExercise.send_message
зовёт self.platform.send_message(...) (шаг 3 плана миграции, см. README.md)
— упражнения больше не завязаны на VK напрямую. MessagingAdapter ниже —
описание того же send_message как интерфейса, который может по-разному
реализовать каждая платформа (VK/Telegram/MAX/OK). Клавиатура — не JSON
конкретной платформы, а НЕЙТРАЛЬНЫЙ формат (актуальный, см.
vk_bot/keyboards.py::_kb — этим форматом реально пользуются VkAdapter и
TelegramAdapter):

    {"rows": [[("➡️ Продолжить", "primary")],
              [("🔄 Начать заново и сохранить", "secondary")],
              [("💾 Выйти и сохранить", "negative")]],
     "one_time": True}

"rows" — ряды кнопок, каждая кнопка — пара (текст, цвет); цвет из набора
{"positive", "negative", "primary", "secondary"} — платформы без понятия
цвета кнопки (Telegram, и, судя по всему, MAX/OK) его просто
игнорируют. "one_time" — прятать ли клавиатуру после нажатия (VK
one_time behaviour) — не все платформы такое умеют, тоже можно
игнорировать. Такой формат один в один соответствует тому, что строит
keyboards.py — просто без привязки к VK JSON. Каждый адаптер сам
превращает нейтральный формат в свой нативный (см. VkAdapter.send_message
в vk_bot/vk_adapter.py, TelegramAdapter._to_reply_markup в
telegram_adapter.py — оба уже это делают на практике).
"""
from abc import ABC, abstractmethod


# Тип для читаемости — нейтральный формат клавиатуры, см. докстринг файла.
Keyboard = dict  # {"rows": list[list[tuple[str, str]]], "one_time": bool}


class MessagingAdapter(ABC):
    """Общий интерфейс для «отправить сообщение» и «получать сообщения»
    для одной платформы. vk_bot/exercises/base.py::BaseExercise, если
    его когда-нибудь переведут на этот интерфейс, будет держать
    self.platform = <конкретный адаптер> и звать
    self.platform.send_message(...) вместо прямого self.vk.method(...).
    """

    @abstractmethod
    def send_message(self, user_id, text: str, keyboard: "Keyboard | None" = None) -> None:
        """Отправить текстовое сообщение пользователю user_id (ID — свой
        для каждой платформы: VK user_id, Telegram chat_id, и т.д. —
        поэтому ID пользователей РАЗНЫХ платформ не взаимозаменяемы, их
        нельзя путать/смешивать в одной таблице User без явного признака
        платформы — см. README.md, раздел «Модель пользователя»).
        Ошибки отправки — как и в BaseExercise.send_message — не должны
        всплывать наружу и ронять вызывающий код упражнения, только
        логироваться."""
        raise NotImplementedError

    @abstractmethod
    def run(self, on_message) -> None:
        """Запустить приём входящих сообщений (не возвращается, пока не
        остановят) — long polling (VK, Telegram) или webhook-сервер
        (когда/если понадобится). on_message(user_id, text) — коллбэк,
        который вызывается на каждое входящее текстовое сообщение; его
        предоставляет вызывающий код (по образцу vk_bot/main.py,
        который сейчас раскладывает входящие VK-события по нужному
        экземпляру упражнения)."""
        raise NotImplementedError


def rows_to_plain_text_hint(keyboard: "Keyboard | None") -> str:
    """Вспомогательное — не часть интерфейса. Пригождается платформам
    без нативных кнопок (или на время, пока адаптер ещё черновой): текст
    вида "[Да] [Нет]" в конце сообщения, чтобы кнопки хотя бы были видны
    как подсказка, а не терялись совсем."""
    if not keyboard or not keyboard.get("rows"):
        return ""
    lines = []
    for row in keyboard["rows"]:
        lines.append(" ".join(f"[{text}]" for text, _color in row))
    return "\n" + "\n".join(lines)
