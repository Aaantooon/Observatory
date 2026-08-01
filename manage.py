#!/usr/bin/env python
"""
manage.py — это командный центр Django.
Через него мы управляем проектом: запускаем сервер, создаём базу данных и т.д.

Все команды пишутся так:
    python manage.py <название команды>

Примеры команд, которые мы уже использовали:
    python manage.py runserver       — запустить сервер разработки
    python manage.py startapp имя    — создать новое приложение
    python manage.py makemigrations  — создать миграции (изменения базы данных)
    python manage.py migrate         — применить миграции к базе данных
    python manage.py createsuperuser — создать администратора
"""

import os   # модуль для работы с операционной системой (пути, переменные окружения)
import sys  # модуль для доступа к аргументам командной строки


def main():
    """
    Главная функция, которая запускает Django.
    Она вызывается, когда мы пишем python manage.py ...
    """

    # Указываем Django, где лежит файл с настройками проекта
    # config.settings означает: в папке config файл settings.py
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    try:
        # Пытаемся импортировать функцию, которая выполняет команды
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Если Django не установлен — показываем понятную ошибку
        raise ImportError(
            "Не могу импортировать Django. Ты уверен, что он установлен? "
            "Возможно, виртуальное окружение не активировано."
        ) from exc

    # Запускаем команду, которую передали в терминале
    # sys.argv — это список: ['manage.py', 'runserver', ...]
    execute_from_command_line(sys.argv)


# Если файл запущен напрямую (python manage.py ...), выполняем main()
# Если файл импортирован из другого скрипта — не выполняем
if __name__ == '__main__':
    main()