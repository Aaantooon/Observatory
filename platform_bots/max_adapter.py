"""Адаптер мессенджера MAX — реализует MessagingAdapter поверх официального
Bot API MAX (https://dev.max.ru/docs-api).

Сверено с официальной докой 03.09.2026 (см. СВОДКА_ПРОЕКТА.md, журнал
изменений — конкретные цитаты и ссылки на источники):
  - базовый URL: https://platform-api2.max.ru
    (https://dev.max.ru/docs/chatbots/bots-coding/prepare)
  - авторизация: заголовок `Authorization: <token>` (БЕЗ "Bearer " —
    в примере доки токен идёт как есть), НЕ query-параметр access_token.
    Токен выдаётся не через бота-помощника (аналог @BotFather), а через
    веб-панель партнёрской платформы MAX: «Чат-боты → Расширенные
    настройки → Настроить», после модерации бота
    (https://dev.max.ru/docs/chatbots/bots-create/manage).
  - отправка сообщения: POST /messages?user_id={id} (или chat_id={id}) —
    получатель ТОЛЬКО query-параметром, НЕ в теле; тело — {"text": ...}
    (до 4000 символов), опционально attachments/link/notify/format
    (https://dev.max.ru/docs-api/methods/POST/messages,
    https://dev.max.ru/docs-api/objects/NewMessageBody). Лимит — не
    более 2 сообщений в секунду в один диалог.
  - входящие сообщения: GET /updates — long polling (marker/limit/timeout,
    https://dev.max.ru/docs-api/methods/GET/updates) ИЛИ POST /subscriptions
    — webhook (https://dev.max.ru/docs-api/methods/POST/subscriptions).
    Здесь реализован long polling, по аналогии с остальными адаптерами
    (не нужен свой HTTPS-эндпоинт, чтобы просто начать).

⚠️ НЕ подтверждено докой, ОСТАЁТСЯ TODO — проверить перед продакшеном:
  1. Точные поля кнопки клавиатуры. Подтверждён только пример
     кнопки-ссылки (type="link", text, url) внутри attachments с
     type="inline_keyboard" — payload.buttons, двумерный массив. Другие
     типы кнопок (callback, link, request_contact, request_geo_location,
     open_app, message, clipboard) упомянуты в навигации доки, но их
     JSON-схему найти не удалось (страницы объектов Button/CallbackButton
     недоступны). Нам для «кнопка = как будто пользователь написал этот
     текст» нужен, вероятно, тип "message" — используется ниже как
     ПРЕДПОЛОЖЕНИЕ, не подтверждённое докой.
  2. Точная структура апдейта message_created (вложенное сообщение) —
     подтверждена только общая схема Update (update_type/chat_id/user/
     timestamp) и объекта Message (sender/recipient/timestamp/body) по
     отдельности, а не то, как именно Message лежит внутри конкретного
     Update — собрано ниже по аналогии, проверить на реальных апдейтах.
  3. Формат ответа GET /updates (лежит ли следующий marker в ответе
     целиком, или в каждом апдейте отдельно, как offset у Telegram) — не
     подтверждено, взято по аналогии с Telegram/VK (marker на уровне
     ответа).
"""
import logging
import time

import requests

from .base_adapter import MessagingAdapter

logger = logging.getLogger(__name__)

API_BASE = "https://platform-api2.max.ru"


class MaxAdapter(MessagingAdapter):
    def __init__(self, token: str):
        self.token = token
        self._marker = None  # аналог offset в Telegram — маркер для GET /updates

    def _call(self, path: str, http_method="POST", params=None, json_body=None):
        url = f"{API_BASE}/{path}"
        headers = {"Authorization": self.token}
        response = requests.request(
            http_method, url, headers=headers, params=params, json=json_body, timeout=35
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    @staticmethod
    def _to_native_keyboard(keyboard):
        """Нейтральный формат ({"rows": [[(текст, цвет), ...], ...],
        "one_time": bool} — см. vk_bot/keyboards.py::_kb) -> attachments
        MAX с inline_keyboard. ⚠️ TODO: тип кнопки "message" и его поля —
        предположение, НЕ подтверждено докой (см. шапку файла, п.1)."""
        if not keyboard or not keyboard.get("rows"):
            return None
        return [{
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "message", "text": text} for text, _color in row]
                    for row in keyboard["rows"]
                ]
            },
        }]

    def send_message(self, user_id, text: str, keyboard=None) -> None:
        try:
            attachments = self._to_native_keyboard(keyboard)
            body = {"text": text}
            if attachments:
                body["attachments"] = attachments
            self._call("messages", params={"user_id": user_id}, json_body=body)
        except Exception as e:
            # Как и в остальных адаптерах — сбой отправки не должен ронять
            # вызывающий код упражнения.
            logger.error(f"[max] Send message error to {user_id}: {e}")

    def run(self, on_message) -> None:
        """Long polling через GET /updates. MAX поддерживает и webhook
        (POST /subscriptions) — но здесь polling, по аналогии с остальными
        адаптерами. on_message вызывается как on_message(user_id, text) —
        см. TODO №2 в шапке файла про структуру message_created, и note в
        base_adapter.py про то, что TelegramAdapter расширил сигнатуру до
        4 аргументов (+first_name/last_name) — если понадобится то же для
        MAX, смотреть, есть ли имя в объекте `user` апдейта."""
        logger.info("[max] Starting long polling")
        while True:
            try:
                data = self._call(
                    "updates", http_method="GET",
                    params={"marker": self._marker, "timeout": 30, "limit": 100},
                )
            except Exception as e:
                logger.error(f"[max] updates poll error: {e}")
                time.sleep(5)
                continue

            updates = data.get("updates", []) if isinstance(data, dict) else []
            for update in updates:
                if update.get("update_type") != "message_created":
                    continue
                message = update.get("message") or {}
                sender = message.get("sender") or {}
                recipient = message.get("recipient") or {}
                user_id = sender.get("user_id") or update.get("chat_id") or recipient.get("chat_id")
                text = (message.get("body") or {}).get("text", "")
                try:
                    on_message(user_id, text)
                except Exception:
                    logger.exception(f"[max] on_message crashed for user_id={user_id}")

            if isinstance(data, dict):
                self._marker = data.get("marker", self._marker)


if __name__ == "__main__":
    # Ручной запуск для проверки адаптера отдельно от остального бота:
    #   MAX_BOT_TOKEN=... python -m platform_bots.max_adapter
    import os

    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("MAX_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте MAX_BOT_TOKEN в окружении для проверки адаптера")

    adapter = MaxAdapter(token)

    def echo(user_id, text):
        adapter.send_message(user_id, f"Эхо: {text}")

    adapter.run(echo)
