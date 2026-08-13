import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
application = get_wsgi_application()

"""
wsgi.py — точка входа для синхронных веб‑серверов (Gunicorn, uWSGI).
Это «официант»: принимает запрос → передаёт Django → возвращает ответ.
На боевом хостинге обязателен. При разработке используется manage.py runserver.
"""
