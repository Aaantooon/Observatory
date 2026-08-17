from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import VK_TOKEN, GROUP_ID
from handlers import BotHandlers
import logging

# Включаем подробное логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("🤖 Бот запущен!")
    print("📨 Ожидаю сообщения...")
    logger.info("Бот запущен")

    vk_session = VkApi(token=VK_TOKEN)
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    handlers = BotHandlers(vk_session)

    for event in longpoll.listen():
        logger.debug(f"Событие: {event.type}")
        print(f"📩 Событие: {event.type}")

        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.message
            user_id = msg.from_id
            text = msg.text

            print(f"📩 Получено сообщение от {user_id}: {text}")
            logger.info(f"Сообщение от {user_id}: {text}")

            user_info = vk_session.method('users.get', {'user_ids': user_id})[0]
            first_name = user_info.get('first_name', '')
            last_name = user_info.get('last_name', '')

            handlers.handle_message(user_id, text, first_name, last_name)


if __name__ == "__main__":
    main()