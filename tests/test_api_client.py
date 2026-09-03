
"""
Тесты vk_bot/api_client.py — реального HTTP-клиента к серверу Django.

Этот файл ни разу не выполнялся другими тестами: все остальные (test_exercises,
test_handlers, test_notifications) используют FakeAPIClient из conftest.py и
не задевают настоящий модуль requests. Здесь requests.get/post/delete
подменяются заглушкой, которая записывает вызовы и отдаёт заранее заданный
ответ или бросает исключение — без единого настоящего сетевого запроса.

Проверяем для каждого метода оба поведения, которые важны для бота:
  - при успешном ответе сервера возвращается ожидаемое значение;
  - при ошибке (плохой статус-код ИЛИ сетевое исключение) метод не падает,
    а возвращает документированное значение по умолчанию (fallback) —
    именно на это полагается остальной код бота (exercises/*, handlers.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import api_client as api_client_module
from api_client import APIClient


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class FakeRequests:
    """Подмена модуля requests. queue — очередь ответов/исключений на
    последовательные вызовы (для методов, делающих 2 запроса подряд,
    например get_or_create_user). Если очередь пуста, отдаёт default."""

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []  # list of (verb, url, kwargs)

    def _next(self, verb, url, **kwargs):
        self.calls.append((verb, url, kwargs))
        if not self.queue:
            raise AssertionError(f"FakeRequests: нет заготовленного ответа на {verb} {url}")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._next("DELETE", url, **kwargs)


def make(*responses):
    fake = FakeRequests(*responses)
    api_client_module.requests = fake
    return APIClient(), fake


# ---------------------------------------------------------------------------
# Заголовки и базовый URL — общие для всех запросов
# ---------------------------------------------------------------------------

def test_headers_include_token_and_content_type():
    client, fake = make(FakeResponse(200, []))
    client.get_exercises()
    verb, url, kwargs = fake.calls[0]
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["Authorization"].startswith("Token ")
    assert kwargs["timeout"] == 5


# ---------------------------------------------------------------------------
# get_or_create_user — единственный метод с двумя последовательными запросами
# ---------------------------------------------------------------------------

def test_get_or_create_user_returns_existing_user_without_posting():
    client, fake = make(FakeResponse(200, [{"vk_id": "123"}]))
    result = client.get_or_create_user("123", "Аня", "И")
    # Раньше здесь возвращался сырой список (queryset) — расхождение с
    # веткой создания ниже, которая всегда отдаёт единственный dict.
    # Единый dict-результат защищает будущий код, читающий возврат, от
    # "работает только иногда" в зависимости от того, был пользователь
    # уже создан или нет.
    assert result == {"vk_id": "123"}
    assert len(fake.calls) == 1, "Если пользователь уже найден, POST не должен уйти"


def test_get_or_create_user_creates_when_not_found():
    client, fake = make(
        FakeResponse(200, []),  # GET: не найден
        FakeResponse(201, {"vk_id": "123", "first_name": "Аня"}),  # POST: создан
    )
    result = client.get_or_create_user("123", "Аня", "И")
    assert result == {"vk_id": "123", "first_name": "Аня"}
    assert fake.calls[1][0] == "POST"


def test_get_or_create_user_falls_back_to_local_dict_when_create_fails():
    client, fake = make(
        FakeResponse(200, []),
        FakeResponse(500, None),  # сервер отверг создание
    )
    result = client.get_or_create_user("123", "Аня", "И")
    assert result == {"id": "123", "vk_id": "123", "first_name": "Аня", "last_name": "И"}


def test_get_or_create_user_falls_back_to_local_dict_on_network_exception():
    client, fake = make(ConnectionError("сеть недоступна"))
    result = client.get_or_create_user("123", "Аня", "И")
    assert result == {"id": "123", "vk_id": "123", "first_name": "Аня", "last_name": "И"}, (
        "Сетевая ошибка не должна ронять бота — должен вернуться локальный fallback"
    )


# ---------------------------------------------------------------------------
# save_result — статус 201 vs что угодно другое vs исключение
# ---------------------------------------------------------------------------

def test_save_result_success_returns_server_json():
    client, fake = make(FakeResponse(201, {"id": 1}))
    assert client.save_result("123", "diary", {}) == {"id": 1}


def test_save_result_bad_status_returns_falsy_not_fake_success():
    """Баг #1: сервер отверг сохранение (не 201), но раньше save_result()
    всё равно возвращал truthy {"status": "saved_local"} — вызывающий код
    (exercises/*) проверяет `if not self.save_result(...)` и это условие
    никогда не срабатывало, скрывая реальный сбой от пользователя. Должен
    возвращаться falsy (None), чтобы честная проверка отработала."""
    client, fake = make(FakeResponse(400, {"error": "bad"}))
    result = client.save_result("123", "diary", {})
    assert not result
    assert result is None


def test_save_result_network_exception_returns_falsy_not_fake_success():
    client, fake = make(TimeoutError("таймаут"))
    result = client.save_result("123", "diary", {})
    assert not result
    assert result is None


# ---------------------------------------------------------------------------
# GET-методы со списком-по-умолчанию (get_exercises, get_due_notifications,
# get_pending_admin_comments)
# ---------------------------------------------------------------------------

def test_get_methods_return_empty_list_on_failure_or_exception():
    cases = [
        ("get_exercises", ()),
        ("get_due_notifications", ()),
        ("get_pending_admin_comments", ()),
    ]
    for method_name, args in cases:
        client, fake = make(FakeResponse(500, None))
        assert getattr(client, method_name)(*args) == [], f"{method_name}: плохой статус должен дать []"

        client, fake = make(RuntimeError("упало"))
        assert getattr(client, method_name)(*args) == [], f"{method_name}: исключение должно дать []"


def test_get_notifications_returns_none_on_failure_not_empty_list():
    """Отдельно от остальных GET-со-списком: get_notifications должен уметь
    отличить "напоминаний правда нет" ([]) от "не смогли узнать" (None) —
    handlers.py ("Отключить напоминания") иначе не может честно сообщить
    о сбое вместо того, чтобы соврать "отключены"."""
    client, fake = make(FakeResponse(500, None))
    assert client.get_notifications("123") is None

    client, fake = make(RuntimeError("упало"))
    assert client.get_notifications("123") is None

    client, fake = make(FakeResponse(200, []))
    assert client.get_notifications("123") == []


def test_get_user_results_returns_none_on_failure_not_empty_list():
    """Как и get_notifications: get_user_results должен отличать "историю
    правда пустую" ([]) от "не смогли узнать" (None) — иначе handlers.py
    (show_results/show_review_menu/show_daily_plan/handle_send_review)
    показывает "путь пуст" вместо честного сообщения о временном сбое."""
    client, fake = make(FakeResponse(500, None))
    assert client.get_user_results("123") is None

    client, fake = make(RuntimeError("упало"))
    assert client.get_user_results("123") is None

    client, fake = make(FakeResponse(200, []))
    assert client.get_user_results("123") == []


def test_get_user_results_success_returns_server_json():
    client, fake = make(FakeResponse(200, [{"exercise_type": "diary"}]))
    assert client.get_user_results("123") == [{"exercise_type": "diary"}]


# ---------------------------------------------------------------------------
# GET-методы с None-по-умолчанию (get_progress, update_streak,
# get_active_review)
# ---------------------------------------------------------------------------

def test_get_progress_success_and_failure():
    client, fake = make(FakeResponse(200, {"exists": True, "data": {}}))
    assert client.get_progress("123", "diary") == {"exists": True, "data": {}}

    client, fake = make(FakeResponse(404, None))
    assert client.get_progress("123", "diary") is None

    client, fake = make(OSError("сеть упала"))
    assert client.get_progress("123", "diary") is None


def test_update_streak_success_and_failure():
    client, fake = make(FakeResponse(200, {"streak": 5}))
    assert client.update_streak("123") == {"streak": 5}

    client, fake = make(FakeResponse(500, None))
    assert client.update_streak("123") is None


def test_get_active_review_exists_false_returns_none():
    """Сервер отвечает 200, но 'exists': False — это НЕ ошибка, это
    легитимный ответ 'у пользователя нет активной проверки'."""
    client, fake = make(FakeResponse(200, {"exists": False}))
    assert client.get_active_review("123") is None


def test_get_active_review_exists_true_returns_data():
    client, fake = make(FakeResponse(200, {"exists": True, "id": 7, "status": "in_review"}))
    result = client.get_active_review("123")
    assert result == {"exists": True, "id": 7, "status": "in_review"}


def test_get_active_review_bad_status_returns_none():
    client, fake = make(FakeResponse(500, None))
    assert client.get_active_review("123") is None


# ---------------------------------------------------------------------------
# True/False-методы (delete_progress, mark_notification_sent)
# ---------------------------------------------------------------------------

def test_delete_progress_true_on_200_false_otherwise():
    client, fake = make(FakeResponse(200, None))
    assert client.delete_progress("123", "diary") is True

    client, fake = make(FakeResponse(404, None))
    assert client.delete_progress("123", "diary") is False

    client, fake = make(KeyError("boom"))
    assert client.delete_progress("123", "diary") is False


def test_mark_notification_sent_true_on_200_false_otherwise():
    client, fake = make(FakeResponse(200, None))
    assert client.mark_notification_sent(1) is True

    client, fake = make(FakeResponse(500, None))
    assert client.mark_notification_sent(1) is False


# ---------------------------------------------------------------------------
# create_notification — требует именно 201 (не 200)
# ---------------------------------------------------------------------------

def test_create_notification_requires_201_not_200():
    client, fake = make(FakeResponse(201, {"id": 1}))
    assert client.create_notification("123", "diary", "daily", {}) == {"id": 1}

    client, fake = make(FakeResponse(200, {"id": 1}))
    assert client.create_notification("123", "diary", "daily", {}) is None, (
        "200 — не 201, метод должен вернуть None, а не считать уведомление созданным"
    )


# ---------------------------------------------------------------------------
# mark_comment_sent — не должен падать, даже если сеть отвалилась; должен
# возвращать True/False по статусу ответа (баг #6: notifications.py должен
# уметь отличить подтверждённую отметку "отправлено" от неподтверждённой,
# чтобы честно залогировать риск повторной отправки).
# ---------------------------------------------------------------------------

def test_mark_comment_sent_does_not_raise_on_network_exception():
    client, fake = make(RuntimeError("сеть упала"))
    result = client.mark_comment_sent(1, 0)  # не должно бросить исключение
    assert result is False


def test_mark_comment_sent_posts_comment_index_in_body():
    client, fake = make(FakeResponse(200, None))
    result = client.mark_comment_sent(7, 2)
    assert result is True
    verb, url, kwargs = fake.calls[0]
    assert verb == "POST"
    assert "7" in url
    assert kwargs["json"]["comment_index"] == 2


def test_mark_comment_sent_returns_false_on_bad_status():
    client, fake = make(FakeResponse(500, None))
    assert client.mark_comment_sent(7, 2) is False


# ---------------------------------------------------------------------------
# add_comment / send_for_review — POST-методы,
# успех и сетевая ошибка не должны ронять бота
# ---------------------------------------------------------------------------

def test_add_comment_success_and_exception():
    client, fake = make(FakeResponse(200, {"ok": True}))
    assert client.add_comment(1, "текст", is_admin=True) == {"ok": True}

    client, fake = make(ConnectionError("нет сети"))
    assert client.add_comment(1, "текст") is None


def test_send_for_review_success_and_exception():
    client, fake = make(FakeResponse(201, {"review_id": 1}))
    assert client.send_for_review("123", "diary", {}) == {"review_id": 1}

    client, fake = make(ConnectionError("нет сети"))
    assert client.send_for_review("123", "diary", {}) is None


# ---------------------------------------------------------------------------
# delete_notification — редко используемый метод, отдельная проверка кода 204
# ---------------------------------------------------------------------------

def test_save_progress_success_and_failure_and_exception():
    client, fake = make(FakeResponse(200, {"status": "ok"}))
    assert client.save_progress("123", "diary", {"dream": "x"}) == {"status": "ok"}
    verb, url, kwargs = fake.calls[0]
    assert kwargs["json"] == {"vk_id": "123", "exercise_type": "diary", "data": {"dream": "x"}}

    client, fake = make(FakeResponse(500, None))
    assert client.save_progress("123", "diary", {}) is None

    client, fake = make(ConnectionError("нет сети"))
    assert client.save_progress("123", "diary", {}) is None


def test_update_streak_network_exception_returns_none():
    client, fake = make(ConnectionError("нет сети"))
    assert client.update_streak("123") is None


def test_mark_notification_sent_network_exception_returns_false():
    client, fake = make(RuntimeError("сеть упала"))
    assert client.mark_notification_sent(1) is False


def test_get_active_review_network_exception_returns_none():
    client, fake = make(ConnectionError("нет сети"))
    assert client.get_active_review("123") is None


def test_delete_notification_true_on_204_false_otherwise():
    client, fake = make(FakeResponse(204, None))
    assert client.delete_notification(1) is True

    client, fake = make(FakeResponse(200, None))
    assert client.delete_notification(1) is False, "200 — не 204, ожидается False"

    client, fake = make(RuntimeError("сеть упала"))
    assert client.delete_notification(1) is False


# ---------------------------------------------------------------------------
# generate_link_code / confirm_link_code — привязка аккаунта к нескольким
# платформам (platform_bots/README.md, «Модель пользователя»). В отличие от
# большинства методов выше, эти два ВСЕГДА возвращают dict с ключом "ok"
# (никогда None/True/False) — handlers.py различает конкретную причину
# сбоя (см. bot_api/views.py::AccountLinkViewSet).
# ---------------------------------------------------------------------------

def test_generate_link_code_success_returns_ok_and_code():
    client, fake = make(FakeResponse(200, {"code": "123456", "expires_in_minutes": 10}))
    result = client.generate_link_code("123")
    assert result == {"ok": True, "code": "123456", "expires_in_minutes": 10}
    verb, url, kwargs = fake.calls[0]
    assert verb == "POST" and "link/generate" in url
    assert kwargs["json"] == {"vk_id": "123"}


def test_generate_link_code_uses_telegram_id_for_telegram_platform():
    client, fake = make(FakeResponse(200, {"code": "654321", "expires_in_minutes": 10}))
    client.platform = "telegram"
    client.generate_link_code("999")
    verb, url, kwargs = fake.calls[0]
    assert kwargs["json"] == {"telegram_id": "999"}


def test_generate_link_code_bad_status_returns_ok_false_with_server_error():
    client, fake = make(FakeResponse(400, {"error": "already_linked"}))
    result = client.generate_link_code("123")
    assert result == {"ok": False, "error": "already_linked"}


def test_generate_link_code_network_exception_returns_ok_false():
    client, fake = make(RuntimeError("сеть упала"))
    result = client.generate_link_code("123")
    assert result == {"ok": False, "error": "network"}


def test_confirm_link_code_success_returns_ok_true():
    client, fake = make(FakeResponse(200, {"status": "ok"}))
    result = client.confirm_link_code("123", "654321")
    assert result["ok"] is True
    verb, url, kwargs = fake.calls[0]
    assert verb == "POST" and "link/confirm" in url
    assert kwargs["json"] == {"vk_id": "123", "code": "654321"}


def test_confirm_link_code_bad_status_returns_ok_false_with_error():
    client, fake = make(FakeResponse(400, {"error": "invalid_or_expired"}))
    result = client.confirm_link_code("123", "000000")
    assert result == {"ok": False, "error": "invalid_or_expired"}


def test_confirm_link_code_network_exception_returns_ok_false():
    client, fake = make(ConnectionError("нет сети"))
    result = client.confirm_link_code("123", "654321")
    assert result == {"ok": False, "error": "network"}
