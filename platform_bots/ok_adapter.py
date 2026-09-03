"""Адаптер Одноклассников (OK) — реализует MessagingAdapter поверх
официального Bot API OK, построенного на базе Graph API
(https://apiok.ru/en/dev/graph_api/bot_api).

Сверено с официальной докой 03.09.2026 (см. СВОДКА_ПРОЕКТА.md, журнал
изменений — конкретные цитаты и ссылки на источники):
  - у OK ДЕЙСТВИТЕЛЬНО есть официальный Bot API для личных/чат-сообщений
    (не только классические group-приложения) — построен поверх Graph
    API, это НЕ классический REST API OK со старой MD5-подписью
    (apiok.ru/dev/graph_api/, apiok.ru/en/dev/graph_api/bot_api).
  - авторизация: БЕЗ подписи (sig) — просто access_token параметром
    («no session token, no sig required, use Graph API token instead»).
    Токен для бота выдаётся в настройках группы («Management → Generate
    access key»), живёт 30 дней и продлевается при каждом вызове.
  - базовый URL: https://api.ok.ru/graph, запросы строятся по схеме
    /graph/{alias}/{edge}[/{subresource}] (Facebook-Graph-подобная схема,
    НЕ /graph/{имя.метода} и НЕ classic fb.do?method=...). Подтверждено
    примером из доки:
      POST https://api.ok.ru/graph/me/messages/chat:{chat_id}?access_token=...
      POST https://api.ok.ru/graph/me/subscribe?access_token=...
  - подписка на входящие (обязательна ПЕРЕД первым вызовом updates) —
    POST .../me/subscribe, тело {"types": [...], "longPolling": true}
    для long polling или {"url": "https://..."} для webhook.

⚠️ НЕ подтверждено докой, ОСТАЁТСЯ TODO — проверить перед продакшеном:
  1. Форма адресации 1:1-сообщения пользователю. Подтверждённый пример
     из доки — только для ЧАТА (.../messages/chat:{id}); отдельно (на
     странице метода graph.user.messages) упоминается вариант с телом
     {"recipient": {"user_ids": ["user:<id>"]}, "message": {"text": ...}}.
     Эти два варианта НЕ удалось свести воедино по документации — возможно
     это два разных способа адресации одного и того же метода, а не
     противоречие. Ниже — вариант по аналогии с подтверждённым chat:
     примером (.../messages/user:{id}), это ПРЕДПОЛОЖЕНИЕ.
  2. Точные поля одной кнопки клавиатуры (INLINE_KEYBOARD) — подтверждён
     только факт двумерного массива и типы кнопок (CALLBACK, LINK), сама
     структура полей кнопки — нет.
  3. Точный URL-путь GET .../updates — на странице метода нет текстового
     примера запроса (только таблица параметров marker/types/count/
     timeout/commit), путь ниже достроен по аналогии с двумя другими
     подтверждёнными методами.
"""
import logging
import time

import requests

from .base_adapter import MessagingAdapter

logger = logging.getLogger(__name__)

API_BASE = "https://api.ok.ru/graph"


class OkAdapter(MessagingAdapter):
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._marker = None

    def _call(self, path: str, http_method="POST", params=None, json_body=None):
        url = f"{API_BASE}/{path}"
        query = {"access_token": self.access_token}
        if params:
            query.update(params)
        response = requests.request(http_method, url, params=query, json=json_body, timeout=35)
        response.raise_for_status()
        return response.json() if response.content else {}

    @staticmethod
    def _to_native_keyboard(keyboard):
        """Нейтральный формат ({"rows": [[(текст, цвет), ...], ...],
        "one_time": bool} — см. vk_bot/keyboards.py::_kb) -> attachment
        INLINE_KEYBOARD. ⚠️ TODO: точные поля кнопки не подтверждены (см.
        шапку файла, п.2) — CALLBACK взят по аналогии с остальными
        адаптерами."""
        if not keyboard or not keyboard.get("rows"):
            return None
        return [{
            "type": "INLINE_KEYBOARD",
            "buttons": [
                [{"type": "CALLBACK", "text": text} for text, _color in row]
                for row in keyboard["rows"]
            ],
        }]

    def send_message(self, user_id, text: str, keyboard=None) -> None:
        try:
            # TODO: сверить с докой OK — путь ".../messages/user:{id}"
            # это предположение по аналогии, см. п.1 в шапке файла.
            body = {"text": text}
            attachments = self._to_native_keyboard(keyboard)
            if attachments:
                body["attachments"] = attachments
            self._call(f"me/messages/user:{user_id}", json_body=body)
        except Exception as e:
            logger.error(f"[ok] Send message error to {user_id}: {e}")

    def run(self, on_message) -> None:
        """Long polling. Подписка обязательна ПЕРЕД первым вызовом
        updates (см. шапку файла) — доке дословно: "For this method to
        work you need to create a long polling subscription with
        POST graph.user.subscribe method"."""
        try:
            self._call("me/subscribe", json_body={
                "types": ["MESSAGE_CREATED", "MESSAGE_CALLBACK"],
                "longPolling": True,
            })
        except Exception as e:
            logger.error(f"[ok] Не удалось оформить long-polling подписку: {e}")
            return

        logger.info("[ok] Starting long polling")
        while True:
            try:
                # TODO: сверить с докой OK — точный путь не подтверждён
                # (см. п.3 в шапке файла), взят по аналогии.
                data = self._call(
                    "me/updates", http_method="GET",
                    params={
                        "marker": self._marker, "timeout": 30, "count": 100,
                        "types": "MESSAGE_CREATED,MESSAGE_CALLBACK",
                    },
                )
            except Exception as e:
                logger.error(f"[ok] updates poll error: {e}")
                time.sleep(5)
                continue

            updates = data.get("updates", []) if isinstance(data, dict) else []
            for update in updates:
                if update.get("type") != "MESSAGE_CREATED":
                    continue
                message = update.get("message") or {}
                sender = message.get("sender") or {}
                user_id = sender.get("user_id")
                text = message.get("text", "")
                try:
                    on_message(user_id, text)
                except Exception:
                    logger.exception(f"[ok] on_message crashed for user_id={user_id}")

            if isinstance(data, dict):
                self._marker = data.get("marker", self._marker)


if __name__ == "__main__":
    # Ручной запуск для проверки адаптера отдельно от остального бота:
    #   OK_BOT_ACCESS_TOKEN=... python -m platform_bots.ok_adapter
    import os

    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("OK_BOT_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Задайте OK_BOT_ACCESS_TOKEN в окружении для проверки адаптера")

    adapter = OkAdapter(token)

    def echo(user_id, text):
        adapter.send_message(user_id, f"Эхо: {text}")

    adapter.run(echo)
