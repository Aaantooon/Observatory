#!/usr/bin/env python
import os
import sys
import pathlib

def main():
    # Определяем текущую папку, где лежит manage.py
    current_dir = pathlib.Path(__file__).resolve().parent
    
    # Пытаемся найти папку config
    config_paths = [
        current_dir / 'config',                 # Если config лежит рядом
        current_dir / 'public_html' / 'config'  # Если config лежит внутри public_html
    ]
    
    settings_found = False
    for path in config_paths:
        if path.exists() and (path / 'settings.py').exists():
            # Добавляем путь в sys.path, чтобы Django мог импортировать
            sys.path.insert(0, str(path.parent))
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'{path.name}.settings')
            settings_found = True
            break
            
    if not settings_found:
        raise ImportError(
            "Не могу найти папку 'config' с файлом settings.py. "
            "Проверьте, что она лежит внутри public_html или рядом с manage.py."
        )

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не могу импортировать Django. Проверьте, активировано ли виртуальное окружение."
        ) from exc

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()