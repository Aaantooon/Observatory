"""
asgi.py — точка входа для АСИНХРОННЫХ веб-серверов (например, Daphne, Uvicorn).

ПРОСТЫМИ СЛОВАМИ:
    Это "официант" для быстрой обработки множества запросов одновременно.
    Нужен для чатов, уведомлений в реальном времени, WebSockets.

Когда понадобится:
    Когда будем делать чат на сайте (нужны WebSockets).
    Обычные страницы работают и без него.

Сейчас не используется:
    Пока у нас нет чата, этот файл просто лежит "про запас".
"""

import os
from django.core.asgi import get_asgi_application

# Указываем, где лежат настройки проекта
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Создаём ASGI-приложение
application = get_asgi_application()