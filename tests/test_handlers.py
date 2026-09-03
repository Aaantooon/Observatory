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
    """Пока у клиента есть Review со статусом in_review, произвольное
    сообщение "в пустоту" (не название пункта меню, нет активной сессии
    упражнения, нет состояния выбора упражнения) уходит как комментарий в
    диалог проверки. Раньше это было верно для АБСОЛЮТНО любого текста —
    смягчено (см. test_active_review_does_not_block_*): активная сессия
    упражнения и само меню выбора упражнения теперь пропускаются, но
    случайный текст без контекста по-прежнему уходит психологу."""
    bh, vk, api = make_handlers()
    api.set_active_review(UID, review_id=42, status="in_review")

    # Пользователь ещё даже не открывал меню — состояние 'main', сессии нет,
    # поэтому текст "1" не может относиться ни к какому упражнению и
    # закономерно уходит как комментарий наблюдателю.
    bh.handle_message(UID, "1", "Тест", "Тестов")

    assert len(api.comments) == 1, "Сообщение должно было перехватиться как комментарий к Review"
    assert api.comments[0] == {"review_id": 42, "comment": "1", "is_admin": False}
    assert "Ответ отправлен наблюдателю" in vk.last_message
    # Ни в одно упражнение сессия не должна была попасть
    assert UID not in bh.stress_search.user_sessions
    assert UID not in bh.my_roles.user_sessions


def test_active_review_comment_failure_reports_honestly():
    """Правка: это ответ клиента психологу в рамках живой проверки — раньше
    при сбое add_comment сообщение всё равно считалось "отправленным", и
    ответ клиента терялся навсегда, а он был уверен, что психолог его видел."""
    bh, vk, api = make_handlers()
    api.set_active_review(UID, review_id=42, status="in_review")
    api.fail_add_comment = True

    bh.handle_message(UID, "1", "Тест", "Тестов")

    assert len(api.comments) == 1
    assert "Ответ отправлен наблюдателю" not in vk.last_message
    assert "Не получилось" in vk.last_message


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


def test_active_review_does_not_block_already_active_exercise_session():
    """Смягчение блокировки: если клиент уже В СЕРЕДИНЕ упражнения (сессия
    уже создана), его ответ должен продолжить упражнение, а не улететь
    комментарием психологу, даже если открыт Review в статусе in_review."""
    bh, vk, api = make_handlers()
    bh.happiness_list.start(UID)  # сессия создана напрямую, без похода через меню
    api.set_active_review(UID, review_id=42, status="in_review")

    bh.handle_message(UID, "Кофе утром — 8", "Тест", "Тестов")

    assert len(api.comments) == 0, "Ответ внутри активного упражнения не должен уйти в Review"
    assert UID in bh.happiness_list.user_sessions
    assert bh.happiness_list.user_sessions[UID]["items"][0]["text"] == "Кофе утром"


def test_active_review_does_not_block_exercise_selection_menu():
    """Смягчение блокировки: пока клиент выбирает/запускает упражнение из
    меню (ещё нет сессии), открытый Review не должен мешать выбору."""
    bh, vk, api = make_handlers()
    bh.user_states[UID] = 'selecting_exercise'
    api.set_active_review(UID, review_id=42, status="in_review")

    bh.handle_message(UID, "2", "Тест", "Тестов")  # список счастья

    assert len(api.comments) == 0, "Выбор упражнения из меню не должен уйти в Review"
    assert UID in bh.happiness_list.user_sessions, "Упражнение должно было реально запуститься"


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


def _greet(bh, uid=UID):
    """Проводит нового пользователя через приветствие в состояние 'main'."""
    bh.handle_message(uid, "любой текст", "Аня", "Иванова")


# ---------------------------------------------------------------------------
# state == 'main' — маршрутизация по ключевым словам
# ---------------------------------------------------------------------------

def test_main_menu_keyword_routes_to_results():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Мои результаты", "Аня", "И")
    assert "ПУТЬ ПУСТ" in vk.last_message, "У нового пользователя результатов нет"


def test_main_menu_typed_lowercase_moi_rezultaty_still_routes_to_results():
    """'мои' в одиночку (без слова 'результат') всё ещё должен матчить
    экран результатов — регрессия для бага #8 не должна ломать этот путь."""
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "мои", "Аня", "И")
    assert "ПУТЬ ПУСТ" in vk.last_message


def test_main_menu_typed_moi_roli_does_not_get_swallowed_by_results():
    """Баг #8: "мои роли", набранное текстом из главного меню, раньше
    маршрутизировалось на экран 'Мои результаты' из-за широкой проверки
    "мои" in text_clean, проверяемой раньше названия упражнения. Свободный
    ввод названия упражнения из состояния 'main' сегодня всё равно нигде не
    запускает упражнение напрямую (это работает только через кнопки —
    state == 'selecting_exercise'), так что здесь достаточно проверить, что
    его больше не молча уводит на экран результатов."""
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "мои роли", "Аня", "И")
    assert "ПУТЬ ПУСТ" not in vk.last_message, (
        "'мои роли' не должно было маршрутизироваться на экран результатов"
    )
    assert bh.user_states[UID] == "main"


def test_main_menu_keyword_routes_to_review_menu():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Проверка", "Аня", "И")
    # Без пройденных упражнений отправлять нечего — state остаётся 'main'
    # (см. show_review_menu: ранний return до смены user_states)
    assert bh.user_states[UID] == "main"
    assert "нет пройденных упражнений" in vk.last_message


def test_main_menu_keyword_routes_to_reminders():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    assert bh.user_states[UID] == "reminders"
    assert "НАПОМИНАНИЯ" in vk.last_message


def test_main_menu_keyword_routes_to_daily_plan():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "📅 Мой план на день", "Аня", "И")
    assert bh.user_states[UID] == "main"
    assert "МОЙ ПЛАН НА ДЕНЬ" in vk.last_message
    assert "Итого примерно" in vk.last_message


def test_main_menu_unrecognized_text_shows_hint_and_stays_in_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "непонятная фраза", "Аня", "И")
    assert bh.user_states[UID] == "main"
    assert "Используй кнопки меню" in vk.last_message


# ---------------------------------------------------------------------------
# state == 'selecting_exercise' — запуск каждого упражнения и 'назад'
# ---------------------------------------------------------------------------

def test_selecting_exercise_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "Назад", "Аня", "И")
    assert bh.user_states[UID] == "main"
    assert "перекрёсток" in vk.last_message


def test_selecting_exercise_invalid_text_reprompts_menu():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "абракадабра", "Аня", "И")
    assert bh.user_states[UID] == "selecting_exercise", "Состояние не должно было смениться"
    assert "Выбери упражнение из списка" in vk.last_message


def test_selecting_exercise_starts_each_exercise_by_number():
    # "1" (Поиск стресса) теперь ведёт не сразу в упражнение, а в подменю
    # выбора части — проверяется отдельно ниже.
    cases = [
        ("2", "happiness_list"), ("3", "my_roles"),
        ("4", "conscious_choice"), ("5", "diary"), ("6", "stop_technique"),
    ]
    for number, attr_name in cases:
        bh, vk, api = make_handlers()
        _greet(bh)
        bh.handle_message(UID, "Упражнения", "Аня", "И")
        bh.handle_message(UID, number, "Аня", "И")
        exercise = getattr(bh, attr_name)
        assert UID in exercise.user_sessions, f"Упражнение {attr_name} не запустилось по номеру {number}"
        assert bh.user_states[UID] == "main"


def test_selecting_exercise_stress_search_opens_parts_submenu():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    assert bh.user_states[UID] == "selecting_stress_part"
    assert UID not in bh.stress_search.user_sessions
    assert "Выбери часть" in vk.last_message


# ---------------------------------------------------------------------------
# state == 'selecting_stress_part' — раздельный запуск Части 1 / Части 2
# ---------------------------------------------------------------------------

def test_selecting_stress_part_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Назад", "Аня", "И")
    assert bh.user_states[UID] == "main"


def test_selecting_stress_part_invalid_text_reprompts_menu():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "абракадабра", "Аня", "И")
    assert bh.user_states[UID] == "selecting_stress_part"
    assert "Выбери часть из списка" in vk.last_message


def test_selecting_stress_part_1_starts_collecting():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Часть 1: Собрать стресс", "Аня", "И")
    assert UID in bh.stress_search.user_sessions
    assert bh.stress_search.user_sessions[UID]['phase'] == 'collecting'
    assert bh.user_states[UID] == "main"


def test_selecting_stress_part_2_without_items_sends_to_part1():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Часть 2: Разобрать стресс", "Аня", "И")
    assert "нет ни одного образа" in vk.last_message
    assert UID not in bh.stress_search.user_sessions


def test_selecting_stress_part_2_with_saved_items_jumps_to_analysis():
    bh, vk, api = make_handlers()
    _greet(bh)
    # Копим один образ в Части 1, затем сохраняемся и выходим.
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Часть 1: Собрать стресс", "Аня", "И")
    bh.stress_search.handle_message(UID, "Работа 8")
    bh.stress_search.handle_message(UID, "Сохранить и выйти")
    assert UID not in bh.stress_search.user_sessions

    # Заходим сразу в Часть 2, минуя повторный сбор.
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Часть 2: Разобрать стресс", "Аня", "И")
    assert UID in bh.stress_search.user_sessions
    assert bh.stress_search.user_sessions[UID]['phase'] == 'analysis'
    assert "РАЗБОР ПУТИ" in vk.last_message


def test_selecting_exercise_starts_by_keyword():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "Список счастья", "Аня", "И")
    assert UID in bh.happiness_list.user_sessions


# ---------------------------------------------------------------------------
# show_results — пустой список, стрик, сводка по каждому типу упражнения
# ---------------------------------------------------------------------------

def test_show_results_with_completed_exercises_and_streak_text():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "stress_search", "result_data": {"items": [1, 2, 3]}},
        {"user_vk_id": UID, "exercise_type": "happiness_list", "result_data": {"items": [1]}},
        {"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "Спокойное"}},
        {"user_vk_id": UID, "exercise_type": "stop_technique", "result_data": {"count": 2}},
    ]
    api.update_streak = lambda user_vk_id: {"streak": 7}

    bh.handle_message(UID, "Мои результаты", "Аня", "И")

    msg = vk.last_message
    assert "Отличная привычка" in msg, "Стрик 7 дней должен показать соответствующий текст"
    assert "Поиск стресса ✅ Пройдено" in msg
    assert "Мои роли 🔘 Не начат" in msg, "Непройденное упражнение должно быть помечено"
    assert "3 образов" in msg
    assert "1 пунктов" in msg
    assert "Спокойное" in msg
    assert "#2" in msg


def test_show_results_empty_shows_path_is_empty_message():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Мои результаты", "Аня", "И")
    assert "ПУТЬ ПУСТ" in vk.last_message


# ---------------------------------------------------------------------------
# show_full_history / кнопка «Вся история»
# ---------------------------------------------------------------------------

def test_show_results_offers_full_history_button_when_more_than_five():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}, "completed_at": "2026-01-01"}
        for _ in range(6)
    ]
    bh.handle_message(UID, "Мои результаты", "Аня", "И")
    assert "📜 Вся история" in vk.last_buttons


def test_show_results_hides_full_history_button_when_five_or_fewer():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}, "completed_at": "2026-01-01"}
        for _ in range(3)
    ]
    bh.handle_message(UID, "Мои результаты", "Аня", "И")
    assert not any("история" in b.lower() for b in vk.last_buttons)


def test_show_full_history_lists_all_results_up_to_limit():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {
            "user_vk_id": UID,
            "exercise_type": "stop_technique",
            "result_data": {"count": i},
            "completed_at": f"2026-01-{i:02d}",
        }
        for i in range(1, 8)
    ]
    bh.handle_message(UID, "Вся история", "Аня", "И")
    msg = vk.last_message
    assert "ВСЯ ИСТОРИЯ" in msg
    assert "последние 7 из 7" in msg
    assert "#7" in msg and "#1" in msg


def test_show_full_history_caps_at_thirty_entries():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "stop_technique", "result_data": {"count": i}, "completed_at": "2026-01-01"}
        for i in range(1, 41)
    ]
    bh.handle_message(UID, "Вся история", "Аня", "И")
    msg = vk.last_message
    assert "последние 30 из 40" in msg
    assert "показаны только последние 30" in msg


def test_show_full_history_empty_shows_path_is_empty_message():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Вся история", "Аня", "И")
    assert "ПУТЬ ПУСТ" in vk.last_message


def test_full_history_button_works_even_with_active_review():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}, "completed_at": "2026-01-01"}
    ]
    api.set_active_review(UID)
    bh.handle_message(UID, "📜 Вся история", "Аня", "И")
    assert "ВСЯ ИСТОРИЯ" in vk.last_message


# ---------------------------------------------------------------------------
# show_review_menu / handle_send_review — полный флоу отправки на проверку
# ---------------------------------------------------------------------------

def test_review_menu_lists_only_completed_exercises():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [
        {"user_vk_id": UID, "exercise_type": "diary", "result_data": {}},
    ]
    bh.handle_message(UID, "Проверка", "Аня", "И")
    assert bh.user_states[UID] == "sending_review"
    assert "5. Дневник" in vk.last_message
    assert "1. Поиск стресса" not in vk.last_message


def test_send_review_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}}]
    bh.handle_message(UID, "Проверка", "Аня", "И")
    bh.handle_message(UID, "назад", "Аня", "И")
    assert bh.user_states[UID] == "main"


def test_send_review_invalid_number_reprompts():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}}]
    bh.handle_message(UID, "Проверка", "Аня", "И")
    bh.handle_message(UID, "абв", "Аня", "И")
    assert "номер упражнения из списка" in vk.last_message
    assert bh.user_states[UID] == "sending_review"


def test_send_review_not_yet_completed_exercise_rejected():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}}]
    bh.handle_message(UID, "Проверка", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")  # stress_search — не пройден
    assert "ещё не пройдено" in vk.last_message
    assert len(api.sent_for_review) == 0


def test_send_review_valid_selection_sends_for_review():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}}]
    bh.handle_message(UID, "Проверка", "Аня", "И")
    bh.handle_message(UID, "5", "Аня", "И")  # diary — пройден
    assert len(api.sent_for_review) == 1
    assert api.sent_for_review[0]["exercise_type"] == "diary"
    assert "Отправлено на проверку" in vk.last_message
    assert bh.user_states[UID] == "main"


def test_send_review_failure_reports_honestly():
    """Правка: раньше "Отправлено на проверку!" показывалось безусловно —
    если send_for_review падал на сервере (None), клиент считал, что
    психолог уже видит упражнение, и ждал комментарий, который никогда не
    придёт."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {"mood": "ок"}}]
    api.fail_send_for_review = True
    bh.handle_message(UID, "Проверка", "Аня", "И")
    bh.handle_message(UID, "5", "Аня", "И")
    assert "Отправлено на проверку" not in vk.last_message
    assert "Не получилось" in vk.last_message
    assert bh.user_states[UID] == "main"


# ---------------------------------------------------------------------------
# state == 'reminders' — настройка напоминаний
# ---------------------------------------------------------------------------

def test_reminders_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "назад", "Аня", "И")
    assert bh.user_states[UID] == "main"


def test_reminders_setup_1_hour():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "1 час", "Аня", "И")
    assert "через 1 час" in vk.last_message
    assert bh.notifications.reminder_calls[-1] == ("continue", UID, "general", 1)


def test_reminders_setup_3_hours():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "3 часа", "Аня", "И")
    assert "через 3 часа" in vk.last_message
    assert bh.notifications.reminder_calls[-1] == ("continue", UID, "general", 3)


def test_reminders_setup_tomorrow_morning():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Завтра утром", "Аня", "И")
    assert "08:00" in vk.last_message
    assert bh.notifications.reminder_calls[-1] == ("diary", UID, "08:00")


def test_reminders_disable():
    """Правка 31.08.2026: раньше кнопка «Отключить» только показывала
    текст, но не отменяла ни одного реального напоминания — теперь
    вызывает delete_notification для каждого активного напоминания."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.created_notifications.append({
        "user_vk_id": UID, "exercise_type": "diary",
        "schedule_type": "daily", "schedule_data": {"time": "08:00"},
    })
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Отключить", "Аня", "И")
    assert "отключены" in vk.last_message
    assert api.deleted_notification_ids == {1}


def test_reminders_disable_with_none_survives():
    """Если у пользователя нет ни одного напоминания, get_notifications
    возвращает [] (не None) — обработчик не должен падать и не должен
    врать, что что-то отключил, раз отключать было нечего."""
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Отключить", "Аня", "И")
    assert "не найдено" in vk.last_message


def test_reminders_setup_1_hour_reports_failure_honestly():
    """Правка: раньше setup_reminder_to_continue вызывался, а результат
    игнорировался — если create_notification падал на сервере, пользователь
    всё равно видел "Напомню через 1 час", хотя ничего не сохранилось."""
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.notifications.fail_reminder_setup = True
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "1 час", "Аня", "И")
    assert "через 1 час" not in vk.last_message
    assert "Не получилось" in vk.last_message


def test_reminders_setup_tomorrow_morning_reports_failure_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.notifications.fail_reminder_setup = True
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Завтра утром", "Аня", "И")
    assert "08:00" not in vk.last_message
    assert "Не получилось" in vk.last_message


def test_reminders_disable_reports_when_get_notifications_fails():
    """get_notifications вернул None (сбой сети) — раньше это маскировалось
    под [] и пользователь слышал "отключены", хотя бот даже не смог узнать,
    что вообще отключать."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.fail_get_notifications = True
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Отключить", "Аня", "И")
    assert "Не получилось" in vk.last_message
    assert "отключены" not in vk.last_message


def test_reminders_disable_reports_partial_failure():
    """Если часть delete_notification не удалась, ответ должен честно
    сказать, что не всё получилось, а не бодро отрапортовать "отключены"."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.created_notifications.append({
        "user_vk_id": UID, "exercise_type": "diary",
        "schedule_type": "daily", "schedule_data": {"time": "08:00"},
    })
    api.created_notifications.append({
        "user_vk_id": UID, "exercise_type": "stop_technique",
        "schedule_type": "daily", "schedule_data": {"time": "12:00"},
    })
    api.fail_delete_notification_ids = {2}
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "Отключить", "Аня", "И")
    assert "1 из 2" in vk.last_message
    assert api.deleted_notification_ids == {1}


def test_reminders_invalid_text_reprompts():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Напоминания", "Аня", "И")
    bh.handle_message(UID, "чепуха", "Аня", "И")
    assert "Выбери настройку из кнопок" in vk.last_message
    assert bh.user_states[UID] == "reminders"


# ---------------------------------------------------------------------------
# state == 'account_link' / 'account_link_enter_code' — привязка VK+Telegram
# (см. platform_bots/README.md, «Модель пользователя»; наша цель — сделать
# максимально удобно, просто и понятно, поэтому отдельно проверяем и честные
# сообщения об ошибках, и прощение мусорного ввода).
# ---------------------------------------------------------------------------

def test_account_link_menu_opens_from_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    assert bh.user_states[UID] == "account_link"
    assert "ПРИВЯЗКА АККАУНТА" in vk.last_message


def test_account_link_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "назад", "Аня", "И")
    assert bh.user_states[UID] == "main"


def test_account_link_invalid_menu_text_reprompts():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "чепуха", "Аня", "И")
    assert "Выбери действие из кнопок" in vk.last_message
    assert bh.user_states[UID] == "account_link"


def test_account_link_generate_code_success_shows_code_and_expiry():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.generate_link_code_result = {"ok": True, "code": "654321", "expires_in_minutes": 10}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Получить код", "Аня", "И")
    assert "654321" in vk.last_message
    assert "10 минут" in vk.last_message
    assert api.generated_link_codes == [UID]
    assert bh.user_states[UID] == "main"


def test_account_link_generate_code_already_linked_reports_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.generate_link_code_result = {"ok": False, "error": "already_linked"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Получить код", "Аня", "И")
    assert "уже объединены" in vk.last_message
    assert bh.user_states[UID] == "main"


def test_account_link_generate_code_network_failure_reports_honestly():
    """generate_link_code всегда возвращает dict с ключом "ok" (см.
    api_client.py) — при сетевом сбое ok=False без конкретного известного
    error, и это не должно молча выглядеть как успех или как already_linked."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.generate_link_code_result = {"ok": False, "error": "network"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Получить код", "Аня", "И")
    assert "Не получилось" in vk.last_message
    assert "уже объединены" not in vk.last_message


def test_account_link_enter_code_prompts_for_code():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    assert bh.user_states[UID] == "account_link_enter_code"
    assert "Пришли код" in vk.last_message


def test_account_link_enter_code_back_returns_to_main():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "назад", "Аня", "И")
    assert bh.user_states[UID] == "main"


def test_account_link_enter_code_success_merges_accounts():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.confirm_link_code_result = {"ok": True, "status": "ok"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "123456", "Аня", "И")
    assert "Готово" in vk.last_message
    assert "объединены" in vk.last_message
    assert api.confirmed_link_codes == [(UID, "123456")]
    assert bh.user_states[UID] == "main"


def test_account_link_enter_code_strips_non_digits_before_confirming():
    """Наша цель — максимально удобно и просто: код можно вписать с
    пробелами/дефисами/эмодзи-подсказкой вокруг цифр, бот должен вычленить
    сами цифры, а не заставлять переписывать в "правильном" формате."""
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "код: 123-456 😊", "Аня", "И")
    assert api.confirmed_link_codes == [(UID, "123456")]


def test_account_link_enter_code_pure_garbage_reprompts_without_calling_api():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "не помню код", "Аня", "И")
    assert "не похож" in vk.last_message.lower()
    assert api.confirmed_link_codes == []
    assert bh.user_states[UID] == "account_link_enter_code"


def test_account_link_enter_code_invalid_or_expired_reports_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.confirm_link_code_result = {"ok": False, "error": "invalid_or_expired"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "111111", "Аня", "И")
    assert "устарел" in vk.last_message or "неверный" in vk.last_message


def test_account_link_enter_code_same_account_reports_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.confirm_link_code_result = {"ok": False, "error": "same_account"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "111111", "Аня", "И")
    assert "этого же аккаунта" in vk.last_message


def test_account_link_enter_code_conflict_reports_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.confirm_link_code_result = {"ok": False, "error": "conflict"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "111111", "Аня", "И")
    assert "другому аккаунту" in vk.last_message


def test_account_link_enter_code_network_failure_reports_honestly():
    bh, vk, api = make_handlers()
    _greet(bh)
    api.confirm_link_code_result = {"ok": False, "error": "network"}
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    bh.handle_message(UID, "111111", "Аня", "И")
    assert "Не получилось" in vk.last_message


def test_active_review_does_not_block_account_link_menu():
    """То же смягчение блокировки Review, что и для меню упражнений (см.
    test_active_review_does_not_block_exercise_selection_menu) — привязка
    аккаунта не должна быть недоступна только потому, что открыта проверка."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.set_active_review(UID, review_id=42, status="in_review")

    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    assert len(api.comments) == 0
    assert bh.user_states[UID] == "account_link"

    bh.handle_message(UID, "Получить код", "Аня", "И")
    assert len(api.comments) == 0
    assert api.generated_link_codes == [UID]


def test_active_review_does_not_block_account_link_enter_code_state():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Привязать аккаунт", "Аня", "И")
    bh.handle_message(UID, "Ввести код", "Аня", "И")
    api.set_active_review(UID, review_id=42, status="in_review")

    bh.handle_message(UID, "123456", "Аня", "И")
    assert len(api.comments) == 0
    assert api.confirmed_link_codes == [(UID, "123456")]


# ---------------------------------------------------------------------------
# _normalize_text — эмодзи не мешают распознаванию ключевых слов
# ---------------------------------------------------------------------------

def test_dispatch_routes_follow_up_message_into_each_active_exercise():
    """Пока сессия упражнения открыта, следующее сообщение должно уходить
    прямо в него, а не обрабатываться как команда главного меню — для
    ВСЕХ 6 упражнений (не только my_roles, см. предыдущий тест)."""
    cases = [
        ("2", "happiness_list", "Кофе — 8", lambda ex: len(ex.user_sessions[UID]["items"]) == 1),
        ("4", "conscious_choice", "Кормить детей", lambda ex: ex.user_sessions[UID]["must_items"] == ["Кормить детей"]),
        ("5", "diary", "Гулял по парку", lambda ex: ex.user_sessions[UID]["dream"] == "Гулял по парку"),
        ("6", "stop_technique", "Думаю о работе", lambda ex: ex.user_sessions[UID]["thoughts"] == "Думаю о работе"),
    ]
    for number, attr_name, follow_up, check in cases:
        bh, vk, api = make_handlers()
        _greet(bh)
        bh.handle_message(UID, "Упражнения", "Аня", "И")
        bh.handle_message(UID, number, "Аня", "И")
        bh.handle_message(UID, follow_up, "Аня", "И")
        exercise = getattr(bh, attr_name)
        assert check(exercise), f"{attr_name}: follow-up сообщение не попало в активную сессию"

    # stress_search теперь запускается через подменю "Часть 1"/"Часть 2" —
    # проверяется тем же принципом (follow-up уходит в активную сессию).
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "Упражнения", "Аня", "И")
    bh.handle_message(UID, "1", "Аня", "И")
    bh.handle_message(UID, "Часть 1: Собрать стресс", "Аня", "И")
    bh.handle_message(UID, "Работа 8", "Аня", "И")
    assert len(bh.stress_search.user_sessions[UID]["items"]) == 1


def test_show_results_streak_text_branches():
    cases = [
        (400, "легенда"), (150, "монстр"), (50, "Круто"), (5, "Так держать"),
    ]
    for streak, expected_word in cases:
        bh, vk, api = make_handlers()
        _greet(bh)
        api.results = [{"user_vk_id": UID, "exercise_type": "diary", "result_data": {}}]
        api.update_streak = lambda user_vk_id, s=streak: {"streak": s}
        bh.handle_message(UID, "Мои результаты", "Аня", "И")
        assert expected_word in vk.last_message, f"streak={streak}: ожидалось '{expected_word}'"


def test_show_results_generic_exercise_type_shows_checkmark():
    """my_roles/conscious_choice в сводке последних записей не имеют
    отдельной ветки форматирования — должны попадать в общий 'else' с ✅."""
    bh, vk, api = make_handlers()
    _greet(bh)
    api.results = [{"user_vk_id": UID, "exercise_type": "my_roles", "result_data": {}}]
    bh.handle_message(UID, "Мои результаты", "Аня", "И")
    assert "Мои роли: ✅" in vk.last_message


def test_emoji_in_button_text_does_not_break_routing():
    bh, vk, api = make_handlers()
    _greet(bh)
    bh.handle_message(UID, "📋 Упражнения", "Аня", "И")
    assert bh.user_states[UID] == "selecting_exercise", "Эмодзи перед словом должно быть проигнорировано"
