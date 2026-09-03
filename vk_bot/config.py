import os
from pathlib import Path
from dotenv import load_dotenv

# Указываем путь к .env файлу в корне проекта
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Настройки VK
VK_TOKEN = os.getenv("VK_GROUP_TOKEN")
GROUP_ID = int(os.getenv("VK_GROUP_ID", "232481197"))

# Настройки Telegram (main_telegram.py, шаг 4 плана platform_bots/README.md)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Публичный @username Telegram-бота (без "@") — НЕ секрет, нужен ОБОИМ
# ботам, чтобы построить диплинк для автоматической привязки аккаунтов
# (03.09.2026, см. handlers.py::show_account_link_menu). Пусто — диплинк
# из VK в Telegram просто не показывается, остальная привязка не страдает.
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")

# Настройки API Django
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
API_TOKEN = os.getenv("API_TOKEN")

# Настройки бота
BOT_NAME = "Путь наблюдателя"
# Максимум пунктов на "собирательных" шагах (список счастья, роли,
# осознанный выбор) — используется в exercises/happiness_list.py,
# exercises/conscious_choice.py и exercises/my_roles.py.
MAX_EXERCISE_ITEMS = 20

# Проверка
print("=" * 50)
print("📁 .env файл:", env_path)
print("🔑 VK_TOKEN:", "✅" if VK_TOKEN else "❌ НЕ ЗАГРУЖЕН!")
print("🆔 GROUP_ID:", GROUP_ID)
print("🔑 API_TOKEN:", "✅" if API_TOKEN else "❌ НЕ ЗАГРУЖЕН!")
print("🔑 TELEGRAM_BOT_TOKEN:", "✅" if TELEGRAM_BOT_TOKEN else "❌ НЕ ЗАГРУЖЕН (нужен только main_telegram.py)")
print("=" * 50)