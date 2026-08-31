"""
Тесты фоновой рассылки vk_bot/notifications.py — вызываем _check_notifications()
напрямую (без реального фонового потока/сна), с подменёнными VK и API.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import FakeVK, FakeAPIClient

from notifications import NotificationSystem


def make():
    vk = FakeVK()
    api = FakeAPIClient()
    ns = NotificationSystem(vk, api)
    return ns, vk, api


def test_due_reminder_is_sent_and_marked():
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 1, "user_vk_id": "123", "exercise_type": "diary"}
    ]

    ns._check_notifications()

    assert len(vk.sent) == 1
    assert vk.sent[0]["user_id"] == 123
    assert "дневник" in vk.sent[0]["message"].lower()
    assert api.marked_notifications_sent == [1]


def test_unknown_exercise_type_falls_back_to_general_text():
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 2, "user_vk_id": "123", "exercise_type": "something_new_and_unmapped"}
    ]

    ns._check_notifications()

    assert vk.sent[0]["message"] == ns._get_reminder_text("general")


def test_notification_without_user_vk_id_is_skipped_not_crashed():
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 3, "exercise_type": "diary"},  # нет user_vk_id
        {"id": 4, "user_vk_id": "999", "exercise_type": "diary"},
    ]

    ns._check_notifications()  # не должно упасть

    assert len(vk.sent) == 1, "Уведомление без user_vk_id должно быть пропущено, не разослано"
    assert vk.sent[0]["user_id"] == 999
    assert api.marked_notifications_sent == [4], "Пропущенное уведомление не должно помечаться отправленным"


def test_send_error_for_one_user_does_not_block_others():
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 5, "user_vk_id": "111", "exercise_type": "diary"},
        {"id": 6, "user_vk_id": "222", "exercise_type": "diary"},
    ]

    original_method = vk.method

    def flaky_method(name, params):
        if params["user_id"] == 111:
            raise RuntimeError("VK API упал для этого пользователя")
        return original_method(name, params)

    vk.method = flaky_method

    ns._check_notifications()  # не должно упасть целиком из-за одной ошибки

    assert len(vk.sent) == 1
    assert vk.sent[0]["user_id"] == 222
    assert api.marked_notifications_sent == [6], (
        "Уведомление, для которого отправка упала, не должно помечаться отправленным"
    )


def test_pending_admin_comment_is_sent_and_marked():
    ns, vk, api = make()
    api.get_pending_admin_comments = lambda: [
        {"review_id": 10, "comment_index": 0, "user_vk_id": "555", "exercise_type": "my_roles", "text": "Хорошая работа"}
    ]

    ns._check_notifications()

    assert len(vk.sent) == 1
    assert vk.sent[0]["user_id"] == 555
    assert "Хорошая работа" in vk.sent[0]["message"]
    assert "my_roles" in vk.sent[0]["message"]
    assert api.marked_comments_sent == [(10, 0)]


def test_pending_admin_comment_send_error_does_not_mark_sent():
    """Правка 31.08.2026: если отправка комментария психолога упала,
    mark_comment_sent НЕ должен вызываться — иначе комментарий помечается
    доставленным и больше никогда не ретраится, теряясь навсегда."""
    ns, vk, api = make()
    api.get_pending_admin_comments = lambda: [
        {"review_id": 11, "comment_index": 0, "user_vk_id": "666", "exercise_type": "diary", "text": "текст"}
    ]

    def broken_method(name, params):
        raise RuntimeError("сеть упала")

    vk.method = broken_method

    ns._check_notifications()  # не должно упасть

    assert api.marked_comments_sent == [], (
        "Комментарий, для которого отправка упала, не должен помечаться отправленным"
    )


# ---------------------------------------------------------------------------
# setup_* методы — какие параметры реально уходят в create_notification
# ---------------------------------------------------------------------------

def test_setup_diary_reminder_creates_daily_notification():
    ns, vk, api = make()
    ns.setup_diary_reminder(123, "08:00")

    assert len(api.created_notifications) == 1
    n = api.created_notifications[0]
    assert n["exercise_type"] == "diary"
    assert n["schedule_type"] == "daily"
    assert n["schedule_data"]["time"] == "08:00"


def test_setup_reminder_to_continue_creates_once_notification_with_delay():
    ns, vk, api = make()
    ns.setup_reminder_to_continue(123, "general", hours=3)

    n = api.created_notifications[0]
    assert n["exercise_type"] == "general"
    assert n["schedule_type"] == "once"
    assert n["schedule_data"]["delay_hours"] == 3


def test_setup_stop_technique_reminder_creates_one_notification_per_time():
    ns, vk, api = make()
    ns.setup_stop_technique_reminder(123, ["10:00", "14:00", "19:00"])

    assert len(api.created_notifications) == 3
    times = [n["schedule_data"]["time"] for n in api.created_notifications]
    assert times == ["10:00", "14:00", "19:00"]
    assert all(n["exercise_type"] == "stop_technique" for n in api.created_notifications)
