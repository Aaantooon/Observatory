"""
custom_filters.py — пользовательские фильтры для шаблонов Django.
Фильтры позволяют обрабатывать данные прямо в шаблонах.
"""

from django import template

# Регистрируем библиотеку фильтров
register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Фильтр для получения значения из словаря по ключу.
    Использование в шаблоне: {{ dictionary|get_item:key }}

    Пример:
        {{ level_descriptions|get_item:level_key }}

    Аргументы:
        dictionary: словарь, из которого нужно получить значение
        key: ключ, по которому ищем значение

    Возвращает:
        Значение из словаря или пустую строку, если ключ не найден
    """
    if dictionary is None:
        return ''
    return dictionary.get(key, '')


@register.filter
def get_level_name(level_code):
    """
    Фильтр для получения названия уровня по его коду.
    Использование в шаблоне: {{ user_level|get_level_name }}
    """
    from ..constants import USER_LEVEL_NAMES
    return USER_LEVEL_NAMES.get(level_code, level_code)


@register.filter
def truncate_text(text, length=100):
    """
    Обрезает текст до указанной длины и добавляет "..."
    Использование: {{ text|truncate_text:50 }}
    """
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length] + '...'