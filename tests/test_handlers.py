"""
Тесты уровня vk_bot/handlers.py — маршрутизация сообщений между главным меню,
упражнениями и системой проверки (Review).

APIClient и NotificationSystem подменены на заглушки (FakeAPIClient,
FakeNotificationSystem из conftest.py), чтобы конструктор BotHandlers не лез
в сеть и не поднимал фоновый поток. AdminCheck использует реальный класс —
он тоже не делает сетевых вызовов при создании.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import FakeVK, FakeAPIClient, FakeNotificationSystem

import handlers as handlers_module

UID = 222


def make_handlers():
    # Подменяем реальный APIClient/NotificationSystem до создания BotHandlers,
    # чтобы конструктор не делал сетевых вызовов и не поднимал поток.
    handlers_module.APIClient = FakeAPIClient
    handlers_module.NotificationSystem = FakeNotificationSystem

    vk = FakeVK()
    bh = handlers_module.BotHandlers(vk)
    return bh, vk, bh.api


# ---------------------------------------------------------------------------
# Блокировка меню при активном Review (см. СВОДКА_ПРОЕКТА.md, известная
# особенность в разделе "Система проверки упражнений")
# ---------------------------------------------------------------------------

def test_active_review_intercepts_any_message_as_comment():
    """Пока у клиента есть Review со статусом in_review, ЛЮБОЕ сообщение
    (кроме названий пунктов меню) уходит как комментарий в диалог проверки —
    а не туда, куда пользователь на самом деле целился (например, в новое
    упражнение). Это задокументированная, не исправленная особенность —
    тест закрепляет её ТЕКУЩЕЕ поведение, чтобы будущая правка handlers.py
    не изменила его незаметно."""
    bh, vk, api = make_handlers()
    api.set_active_review(UID, review_id=42, status="in_review")

    # Пользователь пытается начать упражнение текстом "1" (как если бы был
    # в меню выбора упражнения) — вместо старта упражнения текст улетает
    # как комментарий наблюдателю.
    bh.handle_message(UID, "1", "Тест", "Тестов")

    assert len(api.comments) == 1, "Сообщение должно было перехватиться как комментарий к Review"
    assert api.comments[0] == {"review_id": 42, "comment": "1", "is_admin": False}
    assert "Ответ отправлен наблюдателю" in vk.last_message
    # Ни в одно упражнение сессия не должна была попасть
    assert UID not in bh.stress_search.user_sessions
    assert UID not in bh.my_roles.user_sessions


def test_active_review_allows_main_menu_words_through():
    """Слова главного меню ('упражнения', 'мои результаты' и т.п.) НЕ
    перехватываются в комментарий — по ним можно выйти из блокировки."""
    bh, vk, api = make_handlers()
    api.set_active_review(UID, review_id=42, status="in_review")

    bh.handle_message(UID, "Упражнения", "Тест", "Тестов")

    assert len(api.comments) == 0, "Слово 'упражнения' не должно уйти как комментарий"
    # Раз пользователь новый (не было main_states), первое сообщение всегда
    # уходит на приветствие — это ожидаемо и не относится к сути теста.


def test_active_review_with_closed_status_does_not_intercept():
    """Review со статусом, отличным от in_review (например closed), не
    должен ничего перехватывать — обычная маршрутизация работает."""
    bh, vk, api = make_handlers()
    api.set_active_review(UID, review_id=42, status="closed")

    bh.handle_message(UID, "1", "Тест", "Тестов")

    assert len(api.comments) == 0, "closed-review не должен перехватывать сообщения"


# ---------------------------------------------------------------------------
# Обычная маршрутизация: новый пользователь -> меню -> список упражнений -> старт
# ---------------------------------------------------------------------------

def test_new_user_greeted_then_can_open_exercises_and_start_one():
    bh, vk, api = make_handlers()

    bh.handle_message(UID, "любой текст", "Аня", "Иванова")
    assert "ПУТЬ НАБЛЮДАТЕЛЯ" in vk.last_message, "Первое сообщение нового пользователя — приветствие"
    assert bh.user_states[UID] == "main"

    bh.handle_message(UID, "Упражнения", "Аня", "Иванова")
    assert bh.user_states[UID] == "selecting_exercise"

    bh.handle_message(UID, "3", "Аня", "Иванова")  # "Мои роли"
    assert UID in bh.my_roles.user_sessions, "Упражнение 'Мои роли' должно было запуститься"
    assert bh.user_states[UID] == "main"

    # Дальнейшие сообщения должны маршрутизироваться прямо в my_roles,
    # а не обрабатываться как команды главного меню
    bh.handle_message(UID, "Продавец", "Аня", "Иванова")
    assert bh.my_roles.user_sessions[UID]["social_roles"] == ["Продавец"]
