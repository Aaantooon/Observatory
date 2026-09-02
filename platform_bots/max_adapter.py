"""Черновой адаптер мессенджера MAX — реализует MessagingAdapter.

⚠️ ВАЖНО, честно: в отличие от telegram_adapter.py (стабильный,
давно документированный Bot API, в котором я уверен), у MAX Bot API
на момент написания этого черновика я НЕ могу подтвердить точные
названия эндпоинтов/параметров без сверки с актуальной официальной
документацией (у MAX есть официальный Bot API для разработчиков —
искать на сайте max.ru / в разделе для разработчиков ботов). Ниже —
рабочий СКЕЛЕТ с реалистичной структурой (токен бота, метод отправки
сообщения, приём через polling или webhook), но каждое место с
пометкой "TODO: сверить с докой MAX" нужно проверить и поправить под
актуальный API, прежде чем этим адаптером реально пользоваться.

Не тратьте время на "может заработает как есть" — сначала откройте
официальную документацию бота MAX и сверьте:
  1. Базовый URL API и схему авторизации (Bearer-токен в заголовке?
     токен в query-параметре? свой заголовок?).
  2. Название и тело метода отправки текстового сообщения.
  3. Формат клавиатуры/кнопок (свой JSON или inline-разметка?).
  4. Способ получения новых сообщений: webhook (нужен свой HTTPS-адрес)
     или polling (свой метод вроде getUpdates)?
"""
import logging
import time

import requests

from .base_adapter import MessagingAdapter

logger = logging.getLogger(__name__)

# TODO: сверить с докой MAX — базовый URL наверняка другой.
API_BASE = "https://botapi.max.ru/{method}"


class MaxAdapter(MessagingAdapter):
    def __init__(self, token: str):
        self.token = token
        self._marker = None  # аналог offset в Telegram — id последнего обработанного апдейта

    def _call(self, method: str, **params):
        # TODO: сверить с докой MAX — вероятно токен передаётся иначе
        # (заголовок Authorization, а не query-параметр access_token).
        url = API_BASE.format(method=method)
        params.setdefault("access_token", self.token)
        response = requests.post(url, json=params, timeout=35)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_native_keyboard(keyboard):
        """Нейтральный [[label, ...], ...] -> формат кнопок MAX.
        TODO: сверить с докой MAX — структура ниже ПРЕДПОЛОЖИТЕЛЬНАЯ
        (по аналогии с Telegram/VK: ряды кнопок с текстом), не проверена
        по реальному API."""
        if not keyboard:
            return None
        return {"buttons": [[{"text": label} for label in row] for row in keyboard]}

    def send_message(self, user_id, text: str, keyboard=None) -> None:
        try:
            # TODO: сверить с докой MAX — имя метода и названия полей
            # (user_id/chat_id/recipient? text/message?) предположительные.
            self._call(
                "messages/send",
                chat_id=user_id,
                text=text,
                keyboard=self._to_native_keyboard(keyboard),
            )
        except Exception as e:
            logger.error(f"[max] Send message error to {user_id}: {e}")

    def run(self, on_message) -> None:
        """Черновой long polling по аналогии с Telegram/VK — если MAX
        реально работает через webhook, эту функцию нужно будет заменить
        на лёгкий HTTP-сервер (например Flask/FastAPI-эндпоинт), а не
        бесконечный цикл. TODO: сверить с докой MAX, какая модель приёма
        сообщений у него на самом деле."""
        logger.info("[max] Starting long polling (черновик — сверить с докой MAX)")
        while True:
            try:
                # TODO: сверить с докой MAX — имя метода получения апдейтов.
                data = self._call("updates/get", marker=self._marker, timeout=30)
                updates = data.get("updates", [])
            except Exception as e:
                logger.error(f"[max] updates poll error: {e}")
                time.sleep(5)
                continue

            for update in updates:
                # TODO: сверить с докой MAX — реальные ключи структуры апдейта.
                self._marker = update.get("marker", self._marker)
                message = update.get("message")
                if not message:
                    continue
                chat_id = message.get("chat_id")
                text = message.get("text", "")
                try:
                    on_message(chat_id, text)
                except Exception:
                    logger.exception(f"[max] on_message crashed for chat_id={chat_id}")
