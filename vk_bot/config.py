import os
from pathlib import Path
from dotenv import load_dotenv

# Указываем путь к .env файлу в корне проекта
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Настройки VK
VK_TOKEN = os.getenv("VK_GROUP_TOKEN")
GROUP_ID = int(os.getenv("VK_GROUP_ID", "232481197"))

# Настройки API Django
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
API_TOKEN = os.getenv("API_TOKEN")

# Админы (список VK ID через запятую)
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(',') if x.strip()]

# Настройки бота
BOT_NAME = "Путь наблюдателя"
MAX_EXERCISE_ITEMS = 20

# Проверка
print("=" * 50)
print("📁 .env файл:", env_path)
print("🔑 VK_TOKEN:", "✅" if VK_TOKEN else "❌ НЕ ЗАГРУЖЕН!")
print("🆔 GROUP_ID:", GROUP_ID)
print("🔑 API_TOKEN:", "✅" if API_TOKEN else "❌ НЕ ЗАГРУЖЕН!")
print("👑 ADMIN_IDS:", ADMIN_IDS if ADMIN_IDS else "❌ НЕ ЗАДАНЫ!")
print("=" * 50)