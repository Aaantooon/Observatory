# vk_bot/main_telegram.py — Telegram-версия бота, шаги 4-5/5 плана миграции
# на несколько платформ (platform_bots/README.md). Отдельный процесс,
# отдельный systemd-сервис (см. СВОДКА_ПРОЕКТА.md) — НЕ трогает и не
# перезапускает VK-бота (main.py). Оба процесса работают параллельно и
# независимо, через общий Django-бэкенд (bot_api), но с разными
# пространствами ID пользователей (vk_id / telegram_id, см.
# bot_api/models.py::User и platform_bots/README.md, раздел «Модель
# пользователя»).
#
# С шага 5 (см. СВОДКА_ПРОЕКТА.md) фоновые напоминания и проактивная
# доставка комментариев психолога (notifications.py::NotificationSystem)
# тоже работают для Telegram — свой NotificationSystem(..., platform=
# 'telegram') ниже, со своим фоновым потоком, независимым от VK-бота.
import os
import sys
import time
import logging

# platform_bots/ — сосед vk_bot/ в корне репозитория, а не часть самого
# vk_bot/ (там же лежит base_adapter.py/telegram_adapter.py — общая
# заготовка адаптеров, см. platform_bots/README.md). vk_bot/main.py и все
# остальные модули vk_bot используют плоские импорты (from keyboards import
# ..., from api_client import ...) — это работает, только когда сама папка
# vk_bot/ лежит в sys.path (так её запускает systemd — WorkingDirectory
# видит только vk_bot/, а не корень репозитория). Поэтому для импорта
# соседнего platform_bots/ добавляем корень репозитория в sys.path явно —
# не полагаемся на то, откуда именно запущен этот скрипт.
#
# ВАЖНО: append(), а не insert(0, ...) — в репозитории ЕСТЬ ещё один
# модуль/пакет с именем "config": сам vk_bot/config.py (настройки бота,
# см. import ниже) и config/ в корне репозитория (пакет Django-настроек,
# config/settings.py и т.п. — см. предупреждение в самом начале
# tests/test_bot_api_integration.py про этот же конфликт имён). При
# insert(0, ...) корень репозитория оказывался ПЕРЕД папкой vk_bot/ в
# sys.path, и "from config import TELEGRAM_BOT_TOKEN" находил ПУСТОЙ
# Django-пакет config/ вместо vk_bot/config.py — ImportError на сервере
# (поймано и исправлено в этом же деплое). append() кладёт корень
# репозитория В КОНЕЦ — vk_bot/ (уже добавленная Python'ом первой, как
# папка самого запускаемого скрипта) остаётся в приоритете для "config",
# "keyboards", "handlers" и т.д., а platform_bots всё равно находится.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from platform_bots.telegram_adapter import TelegramAdapter  # noqa: E402

from config import TELEGRAM_BOT_TOKEN  # noqa: E402
from handlers import BotHandlers  # noqa: E402

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env, чтобы запустить Telegram-бота")

    print("🤖 Telegram-бот запущен!")
    print("📨 Ожидаю сообщения...")
    logger.info("Telegram-бот запущен")

    adapter = TelegramAdapter(TELEGRAM_BOT_TOKEN)
    # api_platform='telegram' — сервер ищет/создаёт пользователя по
    # telegram_id, а не по vk_id (см. bot_api/models.py::User).
    # start_notifications=True — фоновый поток NotificationSystem (шаг 5,
    # см. шапку файла) теперь поднимается и для Telegram, отдельно от
    # VK-бота (свой поток, свой процесс, свой systemd-сервис).
    handlers = BotHandlers(adapter, api_platform='telegram', start_notifications=True)

    def on_message(user_id, text, first_name, last_name):
        # TelegramAdapter.run() ниже уже оборачивает каждый вызов on_message
        # в свой try/except (см. platform_bots/telegram_adapter.py) — по
        # тому же принципу, что vk_bot/main.py оборачивает _handle_event на
        # каждое событие: одно упавшее сообщение не должно останавливать
        # бота для всех остальных пользователей.
        handlers.handle_message(user_id, text, first_name, last_name)

    # Внешний цикл — переживает даже обрыв самого long polling (по образцу
    # vk_bot/main.py — там то же самое вокруг VkBotLongPoll). run() сам по
    # себе уже бесконечный цикл с собственным ретраем getUpdates, так что
    # сюда мы попадаем только при непредвиденном исключении внутри него.
    while True:
        try:
            adapter.run(on_message)
        except Exception as e:
            logger.error(f"Telegram long polling оборвался: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
