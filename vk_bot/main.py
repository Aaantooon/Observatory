import os
import time
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import VK_TOKEN, GROUP_ID
from handlers import BotHandlers
import logging

# Уровень логирования — INFO по умолчанию (в проде), DEBUG можно включить
# через переменную окружения LOG_LEVEL=DEBUG при локальной отладке.
# ВАЖНО: текст сообщений пользователей (дневник, стоп-техника и т.п.) в лог
# больше не пишется — это психологические записи, им не место в journalctl.
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _handle_event(handlers, vk_session, event):
    """Обработка одного события. Любая ошибка здесь (плохой профиль VK,
    баг в конкретном упражнении, сообщение длиннее лимита VK и т.п.) не
    должна убивать весь бот — только это одно событие."""
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.message
        user_id = msg.from_id
        text = msg.text or ""

        logger.info(f"Сообщение от {user_id} ({len(text)} симв.)")

        try:
            user_info = vk_session.method('users.get', {'user_ids': user_id})[0]
            first_name = user_info.get('first_name', '')
            last_name = user_info.get('last_name', '')
        except Exception as e:
            logger.error(f"Не удалось получить профиль VK {user_id}: {e}")
            first_name, last_name = '', ''

        handlers.handle_message(user_id, text, first_name, last_name)


def main():
    print("🤖 Бот запущен!")
    print("📨 Ожидаю сообщения...")
    logger.info("Бот запущен")

    vk_session = VkApi(token=VK_TOKEN)
    handlers = BotHandlers(vk_session)

    # Внешний цикл — переживает даже обрыв самого longpoll-соединения
    # (не только ошибки внутри обработки одного сообщения).
    while True:
        try:
            longpoll = VkBotLongPoll(vk_session, GROUP_ID)
            for event in longpoll.listen():
                try:
                    _handle_event(handlers, vk_session, event)
                except Exception as e:
                    logger.error(f"Ошибка обработки события {event.type}: {e}", exc_info=True)
                    # продолжаем цикл — одно упавшее событие не должно
                    # останавливать бота для всех остальных пользователей
        except Exception as e:
            logger.error(f"Longpoll-соединение оборвалось: {e}", exc_info=True)
            time.sleep(5)  # пауза перед переподключением, чтобы не долбить VK API в цикле


if __name__ == "__main__":
    main()