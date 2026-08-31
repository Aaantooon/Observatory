"""
Тесты модуля vk_bot/workload.py — рекомендованная дневная нагрузка по
6 упражнениям, гибкая (подстраивается под активность за последнюю неделю)
и с оценкой времени.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from workload import (
    EXERCISE_PLAN,
    LOAD_LEVELS,
    compute_load_level,
    build_daily_plan,
    format_daily_plan_message,
)

TODAY = date(2026, 8, 31)


def _result(exercise_type, days_ago):
    completed = TODAY - timedelta(days=days_ago)
    return {
        "exercise_type": exercise_type,
        "completed_at": f"{completed.isoformat()}T10:00:00Z",
    }


def test_no_activity_gives_light_level():
    assert compute_load_level([], today=TODAY) == "light"
    # completed_at отсутствует / битый формат — тоже игнорируется, не падает
    assert compute_load_level([{"exercise_type": "diary"}], today=TODAY) == "light"
    assert compute_load_level([{"completed_at": "не дата"}], today=TODAY) == "light"


def test_activity_older_than_a_week_does_not_count():
    results = [_result("diary", days_ago=10), _result("diary", days_ago=8)]
    assert compute_load_level(results, today=TODAY) == "light"


def test_one_to_three_active_days_gives_medium_level():
    results = [_result("diary", days_ago=1), _result("happiness_list", days_ago=1)]  # 1 активный день
    assert compute_load_level(results, today=TODAY) == "medium"

    results3 = [_result("diary", d) for d in (0, 1, 2)]  # 3 разных дня
    assert compute_load_level(results3, today=TODAY) == "medium"


def test_four_or_more_active_days_gives_intense_level():
    results = [_result("diary", d) for d in (0, 1, 2, 3)]  # 4 разных дня
    assert compute_load_level(results, today=TODAY) == "intense"


def test_build_daily_plan_covers_all_six_exercises_with_positive_counts_and_minutes():
    level, items, total_minutes = build_daily_plan([], today=TODAY)
    assert level == "light"
    assert len(items) == len(EXERCISE_PLAN) == 6
    types = {i["type"] for i in items}
    assert types == {
        "stress_search", "happiness_list", "my_roles",
        "conscious_choice", "diary", "stop_technique",
    }
    for item in items:
        assert item["count"] >= 1, "Рекомендация не может быть меньше 1 единицы"
        assert item["minutes"] >= 1
    assert total_minutes == sum(i["minutes"] for i in items)


def test_higher_activity_never_recommends_less_than_lower_activity():
    """Гибкость: чем активнее пользователь на неделе, тем нагрузка не меньше
    (light <= medium <= intense) по каждому упражнению."""
    _, light_items, light_total = build_daily_plan([], today=TODAY)
    _, medium_items, medium_total = build_daily_plan([_result("diary", 0)], today=TODAY)
    _, intense_items, intense_total = build_daily_plan(
        [_result("diary", d) for d in (0, 1, 2, 3)], today=TODAY
    )

    assert light_total <= medium_total <= intense_total

    by_type = lambda items: {i["type"]: i["count"] for i in items}
    light_counts, medium_counts, intense_counts = by_type(light_items), by_type(medium_items), by_type(intense_items)
    for ex_type in light_counts:
        assert light_counts[ex_type] <= medium_counts[ex_type] <= intense_counts[ex_type]


def test_format_daily_plan_message_contains_header_level_and_time_estimate():
    message = format_daily_plan_message([_result("diary", d) for d in (0, 1, 2, 3)], today=TODAY)
    assert "МОЙ ПЛАН НА ДЕНЬ" in message
    assert LOAD_LEVELS["intense"]["label"] in message
    assert "Итого примерно" in message
    assert "мин" in message
    for ex in EXERCISE_PLAN:
        assert ex["title"] in message
