"""
Тесты фоновой рассылки vk_bot/notifications.py — вызываем _check_notifications()
напрямую (без реального фонового потока/сна), с подменёнными VK и API.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import FakeVK, FakeAPIClient

from notifications import NotificationSystem
from vk_api.exceptions import ApiError


def make_api_error(code, msg="error"):
    return ApiError(None, "messages.send", {}, {}, {"error_code": code, "error_msg": msg})


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


# ---------------------------------------------------------------------------
# send_message() никогда не бросает исключение наружу (баг #4б)
# ---------------------------------------------------------------------------

def test_send_message_does_not_raise_on_generic_exception():
    ns, vk, api = make()

    def broken_method(name, params):
        raise RuntimeError("сеть упала")

    vk.method = broken_method
    result = ns.send_message(123, "привет")  # не должно бросить исключение
    assert result is False


def test_send_message_returns_true_on_success():
    ns, vk, api = make()
    assert ns.send_message(123, "привет") is True
    assert len(vk.sent) == 1


# ---------------------------------------------------------------------------
# Флуд-контроль VK (код 6/9) — баг #5: должен прекратить рассылку в текущем
# цикле вместо того, чтобы долбить остальные пункты в ту же стену.
# ---------------------------------------------------------------------------

def test_flood_control_stops_rest_of_notification_batch():
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 1, "user_vk_id": "111", "exercise_type": "diary"},
        {"id": 2, "user_vk_id": "222", "exercise_type": "diary"},
        {"id": 3, "user_vk_id": "333", "exercise_type": "diary"},
    ]

    original_method = vk.method

    def flood_after_first(name, params):
        if params["user_id"] == 111:
            return original_method(name, params)
        raise make_api_error(9, "Flood control")

    vk.method = flood_after_first

    ns._check_notifications()

    assert len(vk.sent) == 1, "Первое сообщение должно было уйти, дальше — остановка на флуд-контроле"
    assert vk.sent[0]["user_id"] == 111
    assert api.marked_notifications_sent == [1]
    # Уведомления 2 и 3 НЕ должны быть помечены отправленными — их
    # подхватит следующий цикл (~60с) заново.
    assert 2 not in api.marked_notifications_sent
    assert 3 not in api.marked_notifications_sent


def test_flood_control_stops_rest_of_admin_comment_batch():
    ns, vk, api = make()
    api.get_pending_admin_comments = lambda: [
        {"review_id": 1, "comment_index": 0, "user_vk_id": "111", "exercise_type": "diary", "text": "первый"},
        {"review_id": 2, "comment_index": 0, "user_vk_id": "222", "exercise_type": "diary", "text": "второй"},
    ]

    def always_flood(name, params):
        raise make_api_error(6, "Too many requests per second")

    vk.method = always_flood

    ns._check_notifications()  # не должно упасть

    assert vk.sent == []
    assert api.marked_comments_sent == []


def test_non_flood_api_error_does_not_stop_batch():
    """Обычная ошибка VK API (не код 6/9) не должна тормозить остальную
    рассылку — только флуд-контроль это делает."""
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 1, "user_vk_id": "111", "exercise_type": "diary"},
        {"id": 2, "user_vk_id": "222", "exercise_type": "diary"},
    ]

    original_method = vk.method

    def not_flood_error(name, params):
        if params["user_id"] == 111:
            raise make_api_error(100, "Some other VK error")
        return original_method(name, params)

    vk.method = not_flood_error

    ns._check_notifications()

    assert len(vk.sent) == 1
    assert vk.sent[0]["user_id"] == 222
    assert api.marked_notifications_sent == [2]


# ---------------------------------------------------------------------------
# Баг #6: send_message() успешен, но mark_notification_sent()/mark_comment_sent()
# не подтвердился — не должно быть двойной отправки ОДНОГО И ТОГО ЖЕ пункта
# в рамках одного цикла, и сбой должен громко залогироваться.
# ---------------------------------------------------------------------------

def test_mark_notification_sent_failure_is_logged_loudly(caplog):
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 1, "user_vk_id": "111", "exercise_type": "diary"},
    ]
    api.fail_mark_notification_sent = True

    with caplog.at_level("ERROR"):
        ns._check_notifications()

    assert len(vk.sent) == 1, "Сообщение всё равно должно было уйти"
    assert any("возможен повторный показ" in r.message for r in caplog.records), (
        "Сбой mark_notification_sent должен громко залогироваться"
    )


def test_duplicate_due_notification_id_sent_only_once_per_cycle():
    """Если backend по какой-то причине вернул один и тот же due-пункт
    дважды в одном цикле — отправить его нужно только один раз."""
    ns, vk, api = make()
    api.get_due_notifications = lambda: [
        {"id": 1, "user_vk_id": "111", "exercise_type": "diary"},
        {"id": 1, "user_vk_id": "111", "exercise_type": "diary"},
    ]

    ns._check_notifications()

    assert len(vk.sent) == 1, "Один и тот же id не должен слаться дважды за один цикл"


def test_mark_comment_sent_failure_is_logged_loudly(caplog):
    ns, vk, api = make()
    api.get_pending_admin_comments = lambda: [
        {"review_id": 10, "comment_index": 0, "user_vk_id": "555", "exercise_type": "my_roles", "text": "Хорошо"}
    ]
    api.fail_mark_comment_sent = True

    with caplog.at_level("ERROR"):
        ns._check_notifications()

    assert len(vk.sent) == 1
    assert any("возможен повторный показ" in r.message for r in caplog.records)
