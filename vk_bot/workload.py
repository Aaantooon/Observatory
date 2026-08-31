"""
Рекомендованная дневная нагрузка по 6 упражнениям.

Это ориентир для пользователя, а не жёсткое ограничение — сами упражнения
работают независимо от этого модуля (кроме уже встроенных лимитов вроде
"1 роль в день" в my_roles). Нагрузка гибкая: подстраивается под то,
сколько дней за последнюю неделю человек реально завершал упражнения
(по данным /results/, которые уже собираются ботом).
"""
from datetime import date, datetime, timedelta

# Базовые (уровень "обычный темп") дневные ориентиры и оценка времени на
# единицу для каждого упражнения.
EXERCISE_PLAN = [
    {
        'type': 'stress_search',
        'title': 'Поиск стресса 🎯',
        'unit': 'ситуация',
        'unit_plural': 'ситуации',
        'base_count': 1,
        'minutes_per_unit': 6,
    },
    {
        'type': 'happiness_list',
        'title': 'Список счастья ✨',
        'unit': 'пункт',
        'unit_plural': 'пунктов',
        'base_count': 5,
        'minutes_per_unit': 1,
    },
    {
        'type': 'my_roles',
        'title': 'Мои роли 🎭',
        'unit': 'роль',
        'unit_plural': 'ролей',
        'base_count': 5,
        'minutes_per_unit': 1,
    },
    {
        'type': 'conscious_choice',
        'title': 'Осознанный выбор 🧘',
        'unit': 'выбор',
        'unit_plural': 'выборов',
        'base_count': 1,
        'minutes_per_unit': 4,
    },
    {
        'type': 'diary',
        'title': 'Дневник 📖',
        'unit': 'запись',
        'unit_plural': 'записей',
        'base_count': 1,
        'minutes_per_unit': 5,
    },
    {
        'type': 'stop_technique',
        'title': 'Стоп-техника 🛑',
        'unit': 'практика',
        'unit_plural': 'практик',
        'base_count': 1,
        'minutes_per_unit': 3,
    },
]

LOAD_LEVELS = {
    'light': {'multiplier': 0.6, 'label': '🌱 Спокойный темп'},
    'medium': {'multiplier': 1.0, 'label': '🌿 Обычный темп'},
    'intense': {'multiplier': 1.6, 'label': '🔥 Активный темп'},
}


def _active_days_last_week(results, today=None):
    """Сколько РАЗНЫХ календарных дней за последние 7 дней пользователь
    завершал хотя бы одно упражнение (по completed_at из /results/)."""
    today = today or date.today()
    week_ago = today - timedelta(days=7)
    days = set()
    for r in results or []:
        completed_at = r.get('completed_at')
        if not completed_at:
            continue
        try:
            d = datetime.fromisoformat(str(completed_at).replace('Z', '+00:00')).date()
        except (ValueError, TypeError):
            continue
        if week_ago <= d <= today:
            days.add(d)
    return len(days)


def compute_load_level(results, today=None):
    """Гибкая нагрузка: новый или редко занимающийся пользователь получает
    спокойный темп, регулярно занимающийся — более насыщенный."""
    active_days = _active_days_last_week(results, today=today)
    if active_days >= 4:
        return 'intense'
    if active_days >= 1:
        return 'medium'
    return 'light'


def build_daily_plan(results, today=None):
    """Возвращает (level, items, total_minutes).

    items — список {type, title, count, unit_label, minutes} по каждому
    из 6 упражнений."""
    level = compute_load_level(results, today=today)
    multiplier = LOAD_LEVELS[level]['multiplier']

    items = []
    total_minutes = 0
    for ex in EXERCISE_PLAN:
        count = max(1, round(ex['base_count'] * multiplier))
        minutes = max(1, round(count * ex['minutes_per_unit']))
        unit_label = ex['unit'] if count == 1 else ex['unit_plural']
        items.append({
            'type': ex['type'],
            'title': ex['title'],
            'count': count,
            'unit_label': unit_label,
            'minutes': minutes,
        })
        total_minutes += minutes

    return level, items, total_minutes


def format_daily_plan_message(results, today=None):
    level, items, total_minutes = build_daily_plan(results, today=today)
    label = LOAD_LEVELS[level]['label']

    lines = [
        "📅 МОЙ ПЛАН НА ДЕНЬ",
        "",
        label,
        "",
        "Это ориентир, а не обязаловка — можно сделать меньше или больше:",
        "",
    ]
    for item in items:
        lines.append(f"· {item['title']}: {item['count']} {item['unit_label']} (~{item['minutes']} мин)")

    lines.append("")
    lines.append(f"⏱️ Итого примерно: ~{total_minutes} мин")
    lines.append("")
    lines.append("💡 Темп подстраивается сам: чем регулярнее занимаешься — тем больше бот предлагает")

    return "\n".join(lines)
