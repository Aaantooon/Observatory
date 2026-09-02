"""Черновой адаптер Одноклассников (OK) — реализует MessagingAdapter.

⚠️ ВАЖНО, честно, как и в max_adapter.py: подтверждённо я знаю только
общую схему авторизации классического OK API (application_key +
application_secret, подпись запроса — MD5 от отсортированных
параметров + секретный ключ, схема описана в официальной документации
OK API для разработчиков, apiok.ru). Названия конкретных методов для
бота-мессенджера OK (отправка сообщения, приём новых сообщений) НЕ
подтверждены — нужно свериться с актуальной документацией бот-платформы
OK (искать раздел «Боты» в документации для разработчиков OK), прежде
чем этим адаптером реально пользоваться. Все места с пометкой
"TODO: сверить с докой OK" — предположения по аналогии с остальными
адаптерами, не факт.
"""
import hashlib
import logging
import time

import requests

from .base_adapter import MessagingAdapter

logger = logging.getLogger(__name__)

# TODO: сверить с докой OK — актуальный базовый URL API ботов.
API_BASE = "https://api.ok.ru/fb.do"


class OkAdapter(MessagingAdapter):
    def __init__(self, application_key: str, application_secret: str, access_token: str):
        self.application_key = application_key
        self.application_secret = application_secret
        self.access_token = access_token
        self._offset = None

    def _sign(self, params: dict) -> str:
        """Классическая подпись OK API: MD5 от отсортированных
        "key=value" (без access_token) + секретный ключ приложения.
        Схема сама по себе стабильна и задокументирована годами — но
        то, какие именно параметры нужны для отправки сообщения ботом,
        не проверено (TODO: сверить с докой OK)."""
        base = "".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "access_token")
        return hashlib.md5((base + self.application_secret).encode("utf-8")).hexdigest()

    def _call(self, method: str, **params):
        params = {
            "method": method,
            "application_key": self.application_key,
            "access_token": self.access_token,
            "format": "json",
            **params,
        }
        params["sig"] = self._sign(params)
        response = requests.post(API_BASE, data=params, timeout=35)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("error_code"):
            raise RuntimeError(f"OK API error on {method}: {data}")
        return data

    @staticmethod
    def _to_native_keyboard(keyboard):
        """TODO: сверить с докой OK — формат кнопок бот-платформы OK не
        проверен, ниже нейтральная структура на всякий случай (текст
        рядов кнопок), а не подтверждённый формат API."""
        if not keyboard:
            return None
        return [[{"text": label} for label in row] for row in keyboard]

    def send_message(self, user_id, text: str, keyboard=None) -> None:
        try:
            # TODO: сверить с докой OK — реальное имя метода отправки
            # сообщения ботом (message.send? bot.sendMessage? другое).
            self._call(
                "bot.sendMessage",
                user_id=user_id,
                text=text,
                keyboard=self._to_native_keyboard(keyboard),
            )
        except Exception as e:
            logger.error(f"[ok] Send message error to {user_id}: {e}")

    def run(self, on_message) -> None:
        """Черновой polling-цикл по аналогии с остальными адаптерами.
        TODO: сверить с докой OK — реальный способ получения новых
        сообщений (polling своим методом или webhook)."""
        logger.info("[ok] Starting polling (черновик — сверить с докой OK)")
        while True:
            try:
                # TODO: сверить с докой OK — реальное имя метода/параметров.
                data = self._call("bot.getUpdates", offset=self._offset, timeout=30)
                updates = data.get("updates", []) if isinstance(data, dict) else []
            except Exception as e:
                logger.error(f"[ok] updates poll error: {e}")
                time.sleep(5)
                continue

            for update in updates:
                self._offset = update.get("id", self._offset)
                message = update.get("message")
                if not message:
                    continue
                user_id = message.get("user_id")
                text = message.get("text", "")
                try:
                    on_message(user_id, text)
                except Exception:
                    logger.exception(f"[ok] on_message crashed for user_id={user_id}")
