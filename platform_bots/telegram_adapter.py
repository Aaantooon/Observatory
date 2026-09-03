"""Черновой адаптер Telegram — реализует MessagingAdapter поверх
официального Telegram Bot HTTP API (https://core.telegram.org/bots/api).
НЕ подключён никуда — см. platform_bots/base_adapter.py и README.md.

Работает через обычные HTTP-запросы (requests), без сторонних библиотек
вроде python-telegram-bot — так же, как vk_bot сейчас работает поверх
vk_api. Если решите подключать по-настоящему, разумная альтернатива —
поставить python-telegram-bot и переписать run() на его Application
(меньше кода, готовый retry/backoff), но для черновика достаточно
голого HTTP.

Получить токен: @BotFather в Telegram -> /newbot -> токен вида
"123456:AAF...". Не коммитить токен в git — токен из .env (по образцу
VK_TOKEN в этом проекте), см. TELEGRAM_BOT_TOKEN в .env.example (нужно
будет добавить самим, когда/если решите подключать этот адаптер).
"""
import logging
import time

import requests

from .base_adapter import MessagingAdapter

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramAdapter(MessagingAdapter):
    def __init__(self, token: str):
        self.token = token
        self._offset = None  # id последнего обработанного апдейта +1, для getUpdates

    def _call(self, method: str, **params):
        url = API_BASE.format(token=self.token, method=method)
        response = requests.post(url, json=params, timeout=35)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error on {method}: {data}")
        return data["result"]

    @staticmethod
    def _to_reply_markup(keyboard):
        """Нейтральная клавиатура (см. vk_bot/keyboards.py::_kb —
        {"rows": [[(текст, цвет), ...], ...], "one_time": bool}, тот же
        формат, что вернул бы to_vk_keyboard() до конвертации в VK JSON) ->
        ReplyKeyboardMarkup Telegram. До шага 2 плана
        platform_bots/README.md здесь ожидался черновой плоский формат
        [[label, ...], ...] — переведено на реальный формат, который
        сейчас экспортируют функции keyboards.py. Telegram не поддерживает
        цвет кнопки — второй элемент кортежа просто игнорируется.
        one_time_keyboard берём из keyboard['one_time'] (по умолчанию True),
        а не жёстко — некоторые клавиатуры (например главное меню)
        постоянные (one_time=False в VK-версии), это же должно сохраняться
        и в Telegram."""
        if not keyboard or not keyboard.get("rows"):
            return {"remove_keyboard": True}
        return {
            "keyboard": [
                [{"text": text} for text, _color in row]
                for row in keyboard["rows"]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": keyboard.get("one_time", True),
        }

    def send_message(self, user_id, text: str, keyboard=None) -> None:
        try:
            self._call(
                "sendMessage",
                chat_id=user_id,
                text=text,
                reply_markup=self._to_reply_markup(keyboard),
            )
        except Exception as e:
            # Как и BaseExercise.send_message в vk_bot — сбой отправки не
            # должен ронять вызывающий код упражнения.
            logger.error(f"[telegram] Send message error to {user_id}: {e}")

    def send_text(self, chat_id, text: str) -> None:
        """Как send_message, но БЕЗ клавиатуры и БЕЗ проглатывания
        исключений — используется vk_bot/notifications.py::NotificationSystem
        для фоновой рассылки напоминаний/комментариев психолога, шаг 5
        плана platform_bots/README.md. send_message выше используется в
        потоке диалога упражнения, где сбой одной отправки не должен ронять
        обработку сообщения пользователя (см. exercises/base.py) — здесь
        наоборот: вызывающая сторона (NotificationSystem) сама решает, ушло
        ли сообщение, и должна ли она остановить рассылку в этом цикле
        (Telegram отвечает 429 Too Many Requests при флуд-контроле — тот же
        принцип, что коды 6/9 у VK API, см. notifications.py::TELEGRAM_FLOOD_STATUS).
        raise_for_status() внутри self._call() поднимет
        requests.exceptions.HTTPError при 429 (и любом другом не-2xx) —
        NotificationSystem его отдельно распознаёт по response.status_code."""
        self._call("sendMessage", chat_id=chat_id, text=text)

    def run(self, on_message) -> None:
        """Long polling через getUpdates — простейший вариант без
        webhook-сервера (не нужен домен/HTTPS-эндпоинт для старта).
        Цикл пишется по образцу vk_bot/main.py (там свой longpoll-цикл
        поверх VK LongPoll API — эта функция решает ту же задачу для
        Telegram).

        on_message вызывается как on_message(chat_id, text, first_name,
        last_name) — Telegram, в отличие от VK, отдаёт имя/фамилию прямо в
        самом апдейте (message['from']), отдельный запрос вроде VK-шного
        users.get (см. vk_bot/main.py::_handle_event) не нужен. Это важно
        для main_telegram.py — BotHandlers.handle_message ждёт ровно эти
        4 аргумента (используются при первом обращении, для
        get_or_create_user)."""
        logger.info("[telegram] Starting long polling")
        while True:
            try:
                updates = self._call(
                    "getUpdates",
                    offset=self._offset,
                    timeout=30,
                    allowed_updates=["message"],
                )
            except Exception as e:
                logger.error(f"[telegram] getUpdates error: {e}")
                time.sleep(5)
                continue

            for update in updates:
                self._offset = update["update_id"] + 1
                message = update.get("message")
                if not message:
                    continue
                chat_id = message["chat"]["id"]
                text = message.get("text", "")
                sender = message.get("from") or {}
                first_name = sender.get("first_name", "")
                last_name = sender.get("last_name", "")
                try:
                    on_message(chat_id, text, first_name, last_name)
                except Exception:
                    logger.exception(f"[telegram] on_message crashed for chat_id={chat_id}")


if __name__ == "__main__":
    # Ручной запуск для проверки адаптера отдельно от остального бота:
    #   TELEGRAM_BOT_TOKEN=... python -m platform_bots.telegram_adapter
    import os

    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в окружении для проверки адаптера")

    adapter = TelegramAdapter(token)

    def echo(user_id, text, first_name, last_name):
        adapter.send_message(
            user_id, f"Эхо: {text}",
            keyboard={"rows": [[("Привет", "primary")], [("Пока", "secondary")]], "one_time": True},
        )

    adapter.run(echo)
