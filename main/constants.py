"""
constants.py — здесь мы храним все постоянные значения.
Это как словарь терминов: чтобы не разбрасывать числа по всему коду,
мы собираем их в одном месте и даём понятные имена.
"""

from enum import Enum

# Enum (перечисление) — это способ задать набор фиксированных значений.
# Вместо того чтобы писать строки "beginner", "experienced" везде,
# мы используем UserLevel.BEGINNER.value, UserLevel.EXPERIENCED.value.
# Так код становится понятнее, и мы не опечатаемся.

class UserLevel(Enum):
    """Уровни пользователей"""
    BEGINNER = "beginner"        # Новичок
    EXPERIENCED = "experienced"  # Опытный
    OBSERVER = "observer"        # Наблюдатель

class TriggerStatus(Enum):
    """Статусы кандидатов на триггер (паттерн замены слов)"""
    PENDING = "pending"          # На рассмотрении
    SUPPRESSED = "suppressed"    # В тихом режиме (временно скрыт)
    ACTIVE = "active"            # Активен

class MapNodeType(Enum):
    """Типы узлов в ментальной карте"""
    FACT = "fact"                # Факт
    INTERPRETATION = "interpretation"  # Интерпретация
    BIAS = "bias"                # Искажение
    CHECK = "check"              # Проверка
    FORUM_THREAD = "forum_thread"  # Ссылка на тему форума
    CHAT_MESSAGE = "chat_message"   # Ссылка на сообщение в чате
    SUMMARY = "summary"          # Итоговый вывод

class EdgeType(Enum):
    """Типы связей между узлами в ментальной карте"""
    EXPLAINS = "explains"        # Объясняет
    CONTRADICTS = "contradicts"  # Противоречит
    ILLUSTRATES = "illustrates"  # Иллюстрирует
    FOLLOWS_FROM = "follows_from"  # Вытекает из
    POSSIBLE_SUBSTITUTION = "possible_substitution"  # Возможная подмена

class ReviewStatus(Enum):
    """Статусы проверки разборов"""
    DRAFT = "draft"              # Черновик
    PENDING_REVIEW = "pending_review"  # На проверке
    PUBLISHED = "published"      # Опубликован
    RESOLVED = "resolved"        # Закрыт

# --- Числовые константы для работы с паттернами ---

# Сколько совпадений нужно для создания кандидата
BASE_REQUIRED_MATCHES = 5

# На сколько увеличивается порог за каждое отклонение
# Если кандидат отклонён 1 раз, нужно 5 + 1*2 = 7 совпадений
# Если 2 раза — 5 + 2*2 = 9 совпадений
REJECTION_MULTIPLIER = 2

# Сколько дней кандидат живёт в "тихом режиме"
SUPPRESSION_DAYS = 7

# Минимум узлов для обнаружения системной доработки
SYSTEMIC_MIN_NODES = 3

# Отклонение для системной доработки (0.5 = 50%)
SYSTEMIC_DEVIATION_RATIO = 0.5

# Пороги уверенности алгоритма (от 0 до 1)
CONF_LOW_THRESHOLD = 0.5   # Ниже этого — низкая уверенность
CONF_HIGH_THRESHOLD = 0.85  # Выше этого — высокая уверенность

# Пороги глубины правок (в символах)
LIGHT_THRESHOLD = 30    # Меньше 30 символов — лёгкая правка
DEEP_THRESHOLD = 100    # Больше 100 символов — глубокая правка

# Человекочитаемые названия уровней
USER_LEVEL_NAMES = {
    UserLevel.BEGINNER.value: "Новичок",
    UserLevel.EXPERIENCED.value: "Опытный",
    UserLevel.OBSERVER.value: "Наблюдатель",
}

# Описания уровней для главной страницы
USER_LEVEL_DESCRIPTIONS = {
    UserLevel.BEGINNER.value: "Только начинаешь замечать мир вокруг. Учишься отличать факты от интерпретаций.",
    UserLevel.EXPERIENCED.value: "Уже видишь паттерны. Шлифуешь инструменты наблюдения.",
    UserLevel.OBSERVER.value: "Строишь свой путь. Светишь фонариком туда, куда сам решишь.",
}


# Функция-фильтр для шаблонов, чтобы получать значение по ключу
def get_item(dictionary, key):
    """Возвращает значение из словаря по ключу. Для использования в шаблонах."""
    return dictionary.get(key, '')