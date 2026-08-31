"""
Автоматические тесты VK-бота "Путь наблюдателя".

Эмулируют реальную переписку пользователя с ботом (без сети — VK и Django API
подменены in-memory заглушками из conftest.py) и проверяют:
  - клавиатура упражнений (3 кнопки: Продолжить / Сохранить и выйти / Сохранить и начать заново)
  - флаг _resume_prompt (одна и та же кнопка "Продолжить" на разных экранах)
  - защиту от бага с подстрокой ("заново"/"продолжить" внутри реального ответа)
  - "Сохранить и начать заново"
  - специфику каждого упражнения (my_roles без ограничения на минимум, diary
    без "None" в выводе, stress_search resume-баги, счётчик stop_technique)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import FakeVK, FakeAPIClient

from exercises.happiness_list import HappinessListExercise
from exercises.my_roles import MyRolesExercise
from exercises.conscious_choice import ConsciousChoiceExercise
from exercises.diary import DiaryExercise
from exercises.stop_technique import StopTechniqueExercise
from exercises.stress_search import StressSearchExercise

UID = 111


def make(cls):
    vk = FakeVK()
    api = FakeAPIClient()
    ex = cls(vk, api)
    return ex, vk, api


# ---------------------------------------------------------------------------
# Общие проверки редизайна — прогоняются по всем 6 упражнениям
# ---------------------------------------------------------------------------

ALL_EXERCISES = [
    ("happiness_list", HappinessListExercise),
    ("my_roles", MyRolesExercise),
    ("conscious_choice", ConsciousChoiceExercise),
    ("diary", DiaryExercise),
    ("stop_technique", StopTechniqueExercise),
    ("stress_search", StressSearchExercise),
]


EXERCISE_KEYBOARD_BUTTONS = ["➡️ Продолжить", "💾 Сохранить и начать заново", "💾 Сохранить и выйти"]
# diary / stop_technique — фиксированные линейные упражнения, у них есть
# навигация по шагам (Назад / В начало / В конец), см. step_nav_keyboard().
STEP_NAV_KEYBOARD_BUTTONS = [
    "➡️ Продолжить", "⬅️ Назад", "🏠 В начало", "🏁 В конец",
    "💾 Сохранить и начать заново", "💾 Сохранить и выйти",
]
# conscious_choice — тоже линейное упражнение с той же навигацией, но
# подписи "начать заново"/"выйти" в обратном порядке слов, см.
# conscious_choice_keyboard().
CONSCIOUS_CHOICE_KEYBOARD_BUTTONS = [
    "➡️ Продолжить", "⬅️ Назад", "🏠 В начало", "🏁 В конец",
    "🔄 Начать заново и сохранить", "💾 Выйти и сохранить",
]


def _expected_buttons(name):
    if name == "conscious_choice":
        return CONSCIOUS_CHOICE_KEYBOARD_BUTTONS
    if name in ("diary", "stop_technique"):
        return STEP_NAV_KEYBOARD_BUTTONS
    return EXERCISE_KEYBOARD_BUTTONS


def test_fresh_start_shows_three_button_keyboard():
    for name, cls in ALL_EXERCISES:
        ex, vk, api = make(cls)
        ex.start(UID)
        buttons = vk.last_buttons
        assert buttons == _expected_buttons(name), (
            f"{name}: ожидались ровно 3 кнопки на стартовом экране, получено {buttons}"
        )


def test_advance_button_is_not_swallowed_as_data():
    """Кнопка 'Продолжить'/'Стоп'/'Завершить' должна распознаваться, а не
    записываться как обычный ответ пользователя."""
    # my_roles: пустая фаза 'social' переспрашивает перед переходом дальше
    # (см. test_my_roles_empty_phase_asks_for_confirmation), но сама кнопка
    # "Продолжить" в любом случае не должна попасть в список ролей.
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "✅ Да, дальше")
    session = ex.user_sessions[UID]
    assert session["phase"] == "interpersonal", "Кнопка «Продолжить» не перевела на след. фазу"
    assert session["social_roles"] == [], "Текст кнопки не должен попасть в список ролей"


def test_substring_bug_regression_my_roles():
    """Ответ, СОДЕРЖАЩИЙ слово 'заново'/'продолжить' как часть текста, должен
    сохраняться как обычный ответ, а не восприниматься как команда навигации."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Хочу начать заново жить")
    session = ex.user_sessions[UID]
    assert session["social_roles"] == ["Хочу начать заново жить"], (
        f"Подстрока 'заново' проглотила реальный ответ пользователя: {session['social_roles']}"
    )
    assert session["phase"] == "social", "Фаза не должна была смениться"

    ex.handle_message(UID, "Хочу продолжить карьеру юриста")
    assert session["social_roles"][-1] == "Хочу продолжить карьеру юриста", (
        "Подстрока 'продолжить' проглотила реальный ответ пользователя"
    )


def test_substring_bug_regression_happiness_list():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Заново начать жизнь — 8")
    session = ex.user_sessions[UID]
    assert len(session["items"]) == 1, "Ответ со словом 'заново' должен был сохраниться как пункт"
    assert session["items"][0]["text"] == "Заново начать жизнь"
    assert session["items"][0]["score"] == 8


def test_save_and_restart_all_exercises():
    for name, cls in ALL_EXERCISES:
        ex, vk, api = make(cls)
        ex.start(UID)
        # кладём хоть какой-то ввод перед "сохранить и начать заново",
        # кроме stress_search / happiness_list, у которых формат "текст число"
        if name in ("happiness_list",):
            ex.handle_message(UID, "Кофе утром — 8")
        elif name == "stress_search":
            ex.handle_message(UID, "Работа 8")
        else:
            ex.handle_message(UID, "Тестовый ответ")

        before_results = len(api.results)
        ex.handle_message(UID, "💾 Сохранить и начать заново")

        assert len(api.results) == before_results + 1, (
            f"{name}: 'Сохранить и начать заново' должен был сохранить результат"
        )
        assert UID in ex.user_sessions, f"{name}: после сохранения должна начаться новая сессия"
        buttons = vk.last_buttons
        assert buttons == _expected_buttons(name), (
            f"{name}: после рестарта должен показываться стартовый экран упражнения"
        )


def test_resume_prompt_continue_and_restart():
    for name, cls in ALL_EXERCISES:
        # --- ветка "Продолжить ✅" из resume-промпта ---
        ex, vk, api = make(cls)
        ex.start(UID)
        if name == "happiness_list":
            ex.handle_message(UID, "Кофе утром — 8")
        elif name == "stress_search":
            ex.handle_message(UID, "Работа 8")
        else:
            ex.handle_message(UID, "Тестовый ответ")

        # новый объект — как будто бот перезапустился и сессия в памяти пропала
        ex2, vk2, _ = make(cls)
        ex2.vk, ex2.api = ex.vk, api  # переиспользуем тот же vk/api (тот же прогресс)
        ex2.start(UID)
        assert vk.last_buttons == ["Продолжить ✅", "Начать заново 🔄"], (
            f"{name}: при наличии сохранённого прогресса должен быть resume-промпт"
        )
        assert ex2.user_sessions[UID].get("_resume_prompt") is True

        ex2.handle_message(UID, "Продолжить ✅")
        assert "_resume_prompt" not in ex2.user_sessions[UID] or not ex2.user_sessions[UID].get("_resume_prompt"), (
            f"{name}: флаг _resume_prompt должен сняться после ответа"
        )

        # --- ветка "Начать заново 🔄" ---
        ex3, vk3, api3 = make(cls)
        ex3.start(UID)
        if name == "happiness_list":
            ex3.handle_message(UID, "Кофе утром — 8")
        elif name == "stress_search":
            ex3.handle_message(UID, "Работа 8")
        else:
            ex3.handle_message(UID, "Тестовый ответ")

        ex4, vk4, _ = make(cls)
        ex4.vk, ex4.api = ex3.vk, api3  # тот же vk-объект, что и у ex3 (vk3)
        ex4.start(UID)
        ex4.handle_message(UID, "Начать заново 🔄")
        assert ex3.vk.last_buttons == _expected_buttons(name), (
            f"{name}: после 'Начать заново' должен показаться чистый старт"
        )


# ---------------------------------------------------------------------------
# Прогресс-бар (▰▰▱▱ N%) — во всех упражнениях, где есть счётчик пунктов/шагов
# ---------------------------------------------------------------------------

def test_happiness_list_shows_progress_bar_when_adding_item():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кофе утром — 8")
    assert "▰" in vk.last_message and "%" in vk.last_message


def test_my_roles_shows_progress_bar_when_adding_role():
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    assert "▰" in vk.last_message and "%" in vk.last_message


def test_conscious_choice_shows_progress_bar_when_adding_item():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    assert "▰" in vk.last_message and "%" in vk.last_message


def test_diary_shows_step_progress_bar():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    assert "▰" in vk.last_message and "%" in vk.last_message
    ex.handle_message(UID, "Гулял по парку")
    assert "▰" in vk.last_message and "%" in vk.last_message


def test_stop_technique_shows_step_progress_bar():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    assert "▰" in vk.last_message and "%" in vk.last_message


def test_happiness_list_shows_score_emoji():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Плохой день — 2")
    assert "🔴" in vk.last_message
    ex.handle_message(UID, "Кофе — 8")
    assert "🟢" in vk.last_message


def test_happiness_list_milestone_at_quarter_marks():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    for i in range(5):  # target=20 -> четверть = 5 пунктов
        ex.handle_message(UID, f"Пункт{i} — 5")
    assert "Четверть пути" in vk.last_message


def test_workload_progress_map_marks_done_exercises():
    from workload import format_progress_map
    results = [{"exercise_type": "happiness_list"}, {"exercise_type": "diary"}]
    message = format_progress_map(results)
    assert "✅ Список счастья ✨" in message
    assert "✅ Дневник 📖" in message
    assert "⬜ Поиск стресса 🎯" in message


def test_workload_week_strip_marks_today_active():
    from datetime import date
    from workload import format_daily_plan_message
    today = date(2026, 1, 15)
    results = [{"exercise_type": "diary", "completed_at": "2026-01-15T10:00:00Z"}]
    message = format_daily_plan_message(results, today=today)
    assert "📆 Неделя:" in message
    assert "✅" in message
    assert "🗺️ Твой путь:" in message


# ---------------------------------------------------------------------------
# my_roles — снятое ограничение "минимум 1 роль"
# ---------------------------------------------------------------------------

def test_my_roles_no_minimum_items_restriction():
    """Нет ЖЁСТКОГО минимума ролей на раздел — но, в отличие от раньше,
    переход с 0 ролей требует подтверждения (см.
    test_my_roles_empty_phase_asks_for_confirmation), после «Да» переход
    происходит нормально."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    session = ex.user_sessions[UID]
    assert session["phase"] == "social"

    ex.handle_message(UID, "➡️ Продолжить")  # 0 ролей введено -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")
    assert ex.user_sessions[UID]["phase"] == "interpersonal", (
        "После подтверждения переход должен произойти даже с 0 ролей в разделе"
    )

    ex.handle_message(UID, "➡️ Продолжить")  # снова 0 ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")
    assert ex.user_sessions[UID]["phase"] == "intrapersonal"

    ex.handle_message(UID, "➡️ Продолжить")  # снова 0 ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> фаза 'analyze'
    # список ролей пуст -> анализировать нечего, упражнение сразу завершается
    assert UID not in ex.user_sessions, "С пустым списком ролей анализ должен сразу завершить упражнение"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["social_roles"] == []
    assert result["interpersonal_roles"] == []
    assert result["intrapersonal_roles"] == []


def test_my_roles_empty_phase_asks_for_confirmation():
    """Нажатие «Продолжить» с 0 ролей в разделе должно переспросить, а не
    сразу перейти дальше (запрошено пользователем: 'спросить его он
    действительно хочет оставить пустым')."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)

    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "social", "Фаза не должна была смениться до подтверждения"
    assert "оставить его пустым" in vk.last_message.lower()
    assert vk.last_buttons == ["✅ Да, дальше", "✏️ Нет, буду писать"]

    # непонятный ответ — просто напоминание про кнопки, ничего не ломается
    ex.handle_message(UID, "не знаю")
    assert ex.user_sessions[UID]["phase"] == "social"
    assert "Да, дальше" in vk.last_message and "буду писать" in vk.last_message

    ex.handle_message(UID, "✅ Да, дальше")
    assert ex.user_sessions[UID]["phase"] == "interpersonal"


def test_my_roles_empty_phase_no_keeps_writing():
    """Ответ «Нет, буду писать» должен вернуть к тому же разделу без
    сброса прогресса, и дать возможность реально дописать роль."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["_confirm_empty_phase"] is True

    ex.handle_message(UID, "✏️ Нет, буду писать")
    assert ex.user_sessions[UID]["phase"] == "social"
    assert "_confirm_empty_phase" not in ex.user_sessions[UID]

    ex.handle_message(UID, "Продавец")
    assert ex.user_sessions[UID]["social_roles"] == ["Продавец"]


def test_my_roles_non_empty_phase_advances_without_confirmation():
    """Если в разделе уже есть хотя бы одна роль, «Продолжить» переходит
    сразу, без переспроса."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "interpersonal", "С непустым разделом переспрос не нужен"
    assert "_confirm_empty_phase" not in ex.user_sessions[UID]


def test_my_roles_shows_progress_and_nudges_at_20():
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)

    ex.handle_message(UID, "Продавец")
    assert "(1/20)" in vk.last_message

    for i in range(19):  # доводим раздел 'social' до 20 ролей
        ex.handle_message(UID, f"Роль {i}")

    assert len(ex.user_sessions[UID]["social_roles"]) == 20
    assert "20 ролей" in vk.last_message
    assert vk.last_buttons[0] == "➡️ Продолжить"

    # можно писать и дальше сверх 20 — жёсткого лимита нет
    ex.handle_message(UID, "Ещё одна роль")
    assert len(ex.user_sessions[UID]["social_roles"]) == 21


def test_my_roles_legacy_bundled_role_self_heals_during_analysis():
    """Живой баг: роль, сохранённая ДО того, как появилась разбивка списков
    (одна строка-'простыня' из нескольких ролей через ';'), не должна
    анализироваться как ОДНА огромная роль — _all_roles должен на лету
    разложить её на отдельные атомарные роли."""
    ex, vk, api = make(MyRolesExercise)
    bundled = "посетитель выставки;\nпокупатель на ярмарке;\nпешеход, который придерживает дверь;"
    session = ex._fresh_session()
    session.update({
        'phase': 'analyze',
        'social_roles': [bundled],
        'analysis_index': 0,
        'analysis_results': [],
    })
    ex.user_sessions[UID] = session

    ex._analyze_roles(UID, session)

    assert "АНАЛИЗ РОЛИ 1/3" in vk.last_message, "Старая 'простыня' должна была разложиться на 3 отдельные роли"
    assert "Роль: посетитель выставки" in vk.last_message
    assert "покупатель на ярмарке" not in vk.last_message, "В карточке роли не должно быть остальных ролей из простыни"


def test_my_roles_legacy_bundled_role_counts_correctly_in_progress_summary():
    """Сводка 'Всего записано' тоже должна честно считать атомарные роли,
    а не одну строку-простыню как одну роль."""
    ex, vk, api = make(MyRolesExercise)
    bundled = "роль раз;\nроль два;\nроль три;"
    session = ex._fresh_session()
    session.update({'phase': 'interpersonal', 'social_roles': [bundled]})

    summary = ex._progress_summary(session)
    assert "Всего записано: 3 ролей" in summary
    assert "Социальных: 3" in summary


def test_my_roles_pasted_multiline_list_splits_into_separate_roles():
    """Баг из живого использования: пользователь вставляет сразу список
    ролей одним сообщением (каждая роль на своей строке, с ';' на конце) —
    раньше это сохранялось как ОДНА роль ('1/20'). Должно разложиться на
    отдельные пункты."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)

    pasted = (
        "посетитель аптеки;\n"
        "зритель на автобусной остановке (тот, кто спокойно ждёт транспорт);\n"
        "участник очереди в МФЦ;\n"
        "прохожий, который подскажет дорогу;\n"
        "слушатель уличного музыканта;"
    )
    ex.handle_message(UID, pasted)

    roles = ex.user_sessions[UID]["social_roles"]
    assert len(roles) == 5, "Каждая строка списка должна была стать отдельной ролью"
    assert roles[0] == "посетитель аптеки"
    assert roles[1] == "зритель на автобусной остановке (тот, кто спокойно ждёт транспорт)"
    assert roles[4] == "слушатель уличного музыканта"
    assert "(1/20)" not in vk.last_message
    assert "Добавлено ролей: 5" in vk.last_message
    assert "Всего в этом разделе: 5/20" in vk.last_message


def test_my_roles_semicolon_list_on_one_line_also_splits():
    """Список из нескольких ролей через ';' в ОДНОЙ строке (без переноса)
    тоже должен разложиться на отдельные пункты, а не сохраниться как одна
    длинная роль."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "сосед; коллега; попутчик в метро")

    roles = ex.user_sessions[UID]["social_roles"]
    assert roles == ["сосед", "коллега", "попутчик в метро"]


def test_my_roles_single_role_message_unchanged():
    """Обычная одна роль без ';' и переносов — поведение и текст
    сообщения не должны были измениться после добавления разбивки списков."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    assert ex.user_sessions[UID]["social_roles"] == ["Продавец"]
    assert "✅ Добавлено: Продавец (1/20)" in vk.last_message


def test_my_roles_blank_message_does_not_add_empty_role():
    """Сообщение, в котором после разбивки не нашлось ни одной роли
    (например только пробелы/точки с запятой), не должно добавлять
    пустую роль и не должно падать."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "   ;  ; \n ")
    assert ex.user_sessions[UID]["social_roles"] == []
    assert "не нашёл" in vk.last_message.lower()


def test_my_roles_resume_screen_shows_detailed_breakdown():
    """Экран 'Продолжим с того места?' должен показывать не только общее
    число ролей, а разбивку по частям и текущий этап (запрошено
    пользователем: 'можно больше информации?')."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Друг для Саши")
    ex.handle_message(UID, "💾 Сохранить и выйти")

    ex2, vk2, _ = make(MyRolesExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)

    msg = vk.last_message
    assert "Всего записано: 2" in msg
    assert "Социальных: 1" in msg
    assert "Межличностных: 1" in msg
    assert "Внутриличностных: 0" in msg
    assert "Часть 2: Межличностные роли" in msg


def test_my_roles_resume_screen_shows_analysis_progress_and_today_status():
    """На этапе разбора экран возобновления должен показывать, сколько
    ролей уже разобрано и разобрана ли сегодняшняя роль."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-31"
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")   # social(1) -> interpersonal, без переспроса
    ex.handle_message(UID, "➡️ Продолжить")   # interpersonal(0) -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")    # -> intrapersonal
    ex.handle_message(UID, "➡️ Продолжить")   # intrapersonal(0) -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")    # -> analyze, роль 1, шаг 1

    ex2, vk2, _ = make(MyRolesExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    assert "Сейчас: Разбор ролей" in vk.last_message
    assert "Разобрано ролей: 0 из 1" in vk.last_message
    assert "Сегодня ещё не разбирал" in vk.last_message

    ex2.handle_message(UID, "Продолжить ✅")
    ex2.handle_message(UID, "идеально")
    ex2.handle_message(UID, "ужасно")  # роль разобрана сегодня

    ex3, vk3, _ = make(MyRolesExercise)
    ex3.vk, ex3.api = ex.vk, api
    # роль уже разобрана и была последней -> упражнение завершилось,
    # сохранённого прогресса больше нет — start() покажет инструкцию, а не
    # экран возобновления
    ex3.start(UID)
    assert "Продолжим с того места" not in vk.last_message


def test_my_roles_intrapersonal_target_is_10_not_20():
    """Часть 3 (внутриличностные роли) — цель 10, в отличие от частей 1 и 2 (по 20)."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")  # social -> interpersonal, 0 ролей
    ex.handle_message(UID, "✅ Да, дальше")
    ex.handle_message(UID, "➡️ Продолжить")  # interpersonal -> intrapersonal, 0 ролей
    ex.handle_message(UID, "✅ Да, дальше")
    assert ex.user_sessions[UID]["phase"] == "intrapersonal"

    ex.handle_message(UID, "Смелый")
    assert "(1/10)" in vk.last_message

    for i in range(9):  # доводим intrapersonal до 10 ролей
        ex.handle_message(UID, f"Роль {i}")

    assert len(ex.user_sessions[UID]["intrapersonal_roles"]) == 10
    assert "10 ролей" in vk.last_message
    assert vk.last_buttons[0] == "➡️ Продолжить"


# ---------------------------------------------------------------------------
# diary — баг с полем differences / литеральным None
# ---------------------------------------------------------------------------

def test_diary_no_none_leak_on_partial_save_and_restart():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")           # dream
    ex.handle_message(UID, "Спокойное")                # mood -> phase стал 'body'
    # сохраняем и начинаем заново ДО того, как дошли до 'differences'
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 1
    result_data = api.results[0]["result_data"]
    assert result_data["differences"] == "", "differences должен быть пустой строкой, не None"
    assert result_data["body"] == ""
    assert result_data["thoughts"] == ""
    assert result_data["wants"] == ""

    last_message = vk.last_message
    assert "None" not in last_message, f"В сообщении не должно быть литерального None: {last_message!r}"


# ---------------------------------------------------------------------------
# happiness_list — экран 20/20 использует exercise_keyboard
# ---------------------------------------------------------------------------

def test_happiness_list_20_items_uses_exercise_keyboard():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    for i in range(20):
        ex.handle_message(UID, f"Пункт{i} — {(i % 10) + 1}")

    assert vk.last_buttons == EXERCISE_KEYBOARD_BUTTONS, (
        f"Экран 20/20 должен использовать ту же клавиатуру, что и весь сбор: {vk.last_buttons}"
    )
    assert "Завершить" not in vk.last_message, "Текст не должен ссылаться на несуществующую кнопку «Завершить»"

    ex.handle_message(UID, "➡️ Продолжить")
    assert len(api.results) == 1
    assert api.results[0]["result_data"]["total"] == 20


# ---------------------------------------------------------------------------
# stop_technique — счётчик попыток
# ---------------------------------------------------------------------------

def test_stop_technique_attempt_counter():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    assert ex.user_sessions[UID]["count"] == 1

    # доходим до конца первой попытки
    ex.handle_message(UID, "Думаю о работе")
    ex.handle_message(UID, "Тревога")
    ex.handle_message(UID, "Отдохнуть")  # завершает -> _finish -> сессия закрыта
    assert UID not in ex.user_sessions
    assert api.results[-1]["result_data"]["count"] == 1

    # После полного завершения прогресс удалён -> новый вход через меню
    # («Упражнения» -> «Стоп-техника») законно начинается с count=1: это
    # НЕ сквозной пожизненный счётчик, а счётчик попыток внутри одного захода
    # (сквозной подсчёт — только внутри одной сессии через "Сохранить и начать заново",
    # см. test_stop_technique_counter_across_save_and_restart).
    ex.start(UID)
    assert ex.user_sessions[UID]["count"] == 1


def test_stop_technique_counter_across_save_and_restart():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    assert ex.user_sessions[UID]["count"] == 1
    ex.handle_message(UID, "Думаю о работе")
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 1
    assert api.results[0]["result_data"]["count"] == 1
    # новая попытка должна получить номер 2, не сброситься в 1
    assert ex.user_sessions[UID]["count"] == 2, (
        f"Счётчик должен увеличиться после 'Сохранить и начать заново', "
        f"получили {ex.user_sessions[UID]['count']}"
    )


# ---------------------------------------------------------------------------
# stress_search — специфичные resume-баги (были исправлены ранее в этой сессии)
# ---------------------------------------------------------------------------

def test_stress_search_resume_from_analysis_does_not_reset():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")  # -> phase analysis
    assert ex.user_sessions[UID]["phase"] == "analysis"

    # "перезапуск бота": та же api (тот же сохранённый прогресс), новый объект
    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    assert vk.last_buttons == ["Продолжить ✅", "Начать заново 🔄"]
    ex2.handle_message(UID, "Продолжить ✅")
    assert ex2.user_sessions[UID]["phase"] == "analysis", (
        "Возобновление с фазы 'analysis' не должно откатывать на 'question'"
    )
    assert ex2.user_sessions[UID]["answers"] == [], "answers не должны обнуляться при возобновлении"


def test_stress_search_resume_from_question_does_not_duplicate_answer():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")   # -> analysis
    ex.handle_message(UID, "➡️ Далее")        # -> показывает первый вопрос, добавляет answers[0]
    assert len(ex.user_sessions[UID]["answers"]) == 1
    ex.handle_message(UID, "Идеальная ситуация")  # step 1 -> 2

    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    ex2.handle_message(UID, "Продолжить ✅")
    assert len(ex2.user_sessions[UID]["answers"]) == 1, (
        f"Возобновление с фазы 'question' не должно дублировать запись в answers, "
        f"получено {len(ex2.user_sessions[UID]['answers'])}"
    )
    assert ex2.user_sessions[UID]["question_step"] == 2


def test_stress_search_handle_analysis_unrecognized_text_reprompts():
    """Текст на экране 'Разбор пути' (analysis), не являющийся ни 'далее',
    ни 'завершить', не должен пугать/ломать сессию — просто переспросить."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")  # -> analysis
    assert ex.user_sessions[UID]["phase"] == "analysis"

    ex.handle_message(UID, "непонятный текст")
    assert ex.user_sessions[UID]["phase"] == "analysis", "Фаза не должна была смениться"
    assert "Нажми" in vk.last_message


# ---------------------------------------------------------------------------
# Валидация неверного ввода (формат "текст число", число вне диапазона)
# ---------------------------------------------------------------------------

def test_happiness_list_rejects_invalid_input_without_losing_progress():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)

    ex.handle_message(UID, "Просто текст без оценки")
    assert ex.user_sessions[UID]["items"] == [], "Некорректный формат не должен добавлять пункт"
    assert "Формат" in vk.last_message

    ex.handle_message(UID, "Кофе утром — 15")  # оценка вне диапазона
    assert ex.user_sessions[UID]["items"] == [], "Оценка вне 1-10 не должна добавлять пункт"
    assert "от 1 до 10" in vk.last_message

    ex.handle_message(UID, "Кофе утром — abc")  # не число
    assert ex.user_sessions[UID]["items"] == []

    # корректный ввод после серии ошибок всё ещё работает
    ex.handle_message(UID, "Кофе утром — 8")
    assert len(ex.user_sessions[UID]["items"]) == 1


def test_happiness_list_no_duplicate_dash_in_stored_text_and_display():
    """Живой баг: пользователь пишет 'Текст — 8' (с тире перед оценкой),
    rsplit оставлял тире внутри item_text, а при показе добавлялось ещё
    одно ' — {score}/10' — получалось 'Текст — — 8/10'. Тире на конце
    введённого текста должно срезаться."""
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кофе утром — 8")

    assert ex.user_sessions[UID]["items"][0]["text"] == "Кофе утром"
    assert "— —" not in vk.last_message, "Не должно быть задвоенного тире в подтверждении"
    assert "Кофе утром — 8/10" in vk.last_message

    # без тире вообще (просто пробел перед оценкой) — тоже должно работать
    ex.handle_message(UID, "Прогулка в парке 9")
    assert ex.user_sessions[UID]["items"][1]["text"] == "Прогулка в парке"

    # дефис вместо длинного тире — тоже срезается
    ex.handle_message(UID, "Чтение книги - 7")
    assert ex.user_sessions[UID]["items"][2]["text"] == "Чтение книги"


def test_stress_search_rejects_invalid_input_without_losing_progress():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "безформатный текст")
    assert ex.user_sessions[UID]["items"] == [], "Без пробела+числа пункт не должен добавляться"

    ex.handle_message(UID, "Работа abc")
    assert ex.user_sessions[UID]["items"] == [], "Нечисловая оценка не должна добавляться"

    ex.handle_message(UID, "Работа 15")
    assert ex.user_sessions[UID]["items"] == [], "Оценка вне 1-10 не должна добавляться"

    ex.handle_message(UID, "Работа 8")
    assert len(ex.user_sessions[UID]["items"]) == 1


def test_stress_search_no_duplicate_dash_in_stored_text():
    """Тот же баг, что чинили в happiness_list: rsplit оставляет тире на
    конце текста ("Текст —"), а при показе добавляется ещё одно " — N/10" —
    получалось двойное тире."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "Кофе утром — 8")

    assert ex.user_sessions[UID]["items"][0]["text"] == "Кофе утром"
    assert "— —" not in vk.last_message


def test_stress_search_pasted_multiline_list_splits_into_separate_items():
    """Как и в my_roles.py — вставленный одним сообщением многострочный
    список должен разбираться на отдельные образы, а не сохраняться как
    один гигантский пункт."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    pasted = "Работа 8\nШум за окном — 7\n· Дедлайны 9"
    ex.handle_message(UID, pasted)

    items = ex.user_sessions[UID]["items"]
    assert len(items) == 3, "Многострочная вставка должна была разбиться на 3 образа"
    assert items[0] == {"text": "Работа", "rate": 8}
    assert items[1] == {"text": "Шум за окном", "rate": 7}
    assert items[2] == {"text": "Дедлайны", "rate": 9}
    assert "Добавлено образов: 3" in vk.last_message


def test_stress_search_run_on_single_line_splits_by_embedded_scores():
    """Пользователь может вставить список одной строкой без переносов —
    "Фраза N Фраза N Фраза N ..." — каждая оценка 1-10 закрывает фразу
    перед собой. Без этого вся строка сохранялась как один образ."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    pasted = (
        "Рецепт не выходит 8 вода не фильтруется 7 баг в коде не ищется 8 "
        "субстрат не сходится 7 время тает 8"
    )
    ex.handle_message(UID, pasted)

    items = ex.user_sessions[UID]["items"]
    assert len(items) == 5
    assert items[0] == {"text": "Рецепт не выходит", "rate": 8}
    assert items[1] == {"text": "вода не фильтруется", "rate": 7}
    assert items[4] == {"text": "время тает", "rate": 8}
    assert "Добавлено образов: 5" in vk.last_message


def test_stress_search_run_on_single_line_reports_leftover_tail():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "Работа 8 Учёба 7 незаконченный хвост без оценки")

    items = ex.user_sessions[UID]["items"]
    assert len(items) == 2
    assert "Не смог разобрать хвост" in vk.last_message
    assert "незаконченный хвост без оценки" in vk.last_message


def test_stress_search_single_item_still_uses_old_confirmation_format():
    """Обычная одна запись "Текст N" не должна попадать в новый
    "слитный список" разбор — сообщение должно остаться прежним."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "Работа 8")

    assert ex.user_sessions[UID]["items"] == [{"text": "Работа", "rate": 8}]
    assert "ОБРАЗ #1" in vk.last_message


def test_stress_search_pasted_multiline_list_reports_unrecognized_lines():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    pasted = "Работа 8\nэто без оценки\nШум 7"
    ex.handle_message(UID, pasted)

    items = ex.user_sessions[UID]["items"]
    assert len(items) == 2
    assert "Не распознал 1" in vk.last_message


def test_stress_search_multiline_all_unrecognized_does_not_add_items():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "первая строка без оценки\nвторая тоже без оценки")

    assert ex.user_sessions[UID]["items"] == []
    assert "Не смог распознать" in vk.last_message


# ---------------------------------------------------------------------------
# "Сохранить и выйти" (CANCEL_TEXTS) — прогресс сохраняется, сессия
# закрывается, при повторном входе появляется resume-промпт
# ---------------------------------------------------------------------------

def test_cancel_saves_progress_and_shows_resume_prompt_on_next_start():
    for name, cls in ALL_EXERCISES:
        ex, vk, api = make(cls)
        ex.start(UID)
        if name == "happiness_list":
            ex.handle_message(UID, "Кофе утром — 8")
        elif name == "stress_search":
            ex.handle_message(UID, "Работа 8")
        else:
            ex.handle_message(UID, "Тестовый ответ")

        results_before = len(api.results)
        ex.handle_message(UID, "💾 Сохранить и выйти")

        assert UID not in ex.user_sessions, f"{name}: после 'Сохранить и выйти' сессия должна закрыться"
        assert len(api.results) == results_before, f"{name}: 'Сохранить и выйти' не должен создавать результат"

        # повторный вход в то же упражнение (тот же api => тот же прогресс)
        ex2, vk2, _ = make(cls)
        ex2.vk, ex2.api = ex.vk, api
        ex2.start(UID)
        assert vk.last_buttons == ["Продолжить ✅", "Начать заново 🔄"], (
            f"{name}: после 'Сохранить и выйти' повторный вход должен предложить продолжить"
        )


# ---------------------------------------------------------------------------
# Полные флоу до конца (не только частичные сценарии)
# ---------------------------------------------------------------------------

def test_diary_full_flow_to_finish():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")     # dream
    ex.handle_message(UID, "Спокойное")           # mood
    ex.handle_message(UID, "Лёгкость в теле")     # body
    ex.handle_message(UID, "Мысли о работе")      # thoughts
    ex.handle_message(UID, "Хочу кофе")           # wants
    ex.handle_message(UID, "Солнечный день")      # differences -> _finish()

    assert UID not in ex.user_sessions, "После 6 шага упражнение должно завершиться"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result == {
        "dream": "Гулял по парку",
        "mood": "Спокойное",
        "body": "Лёгкость в теле",
        "thoughts": "Мысли о работе",
        "wants": "Хочу кофе",
        "differences": "Солнечный день",
    }
    assert "None" not in vk.last_message


def test_conscious_choice_step1_shows_progress_and_target_nudge():
    """Шаг 1 ('Что я должен?') показывает счётчик X/20 при добавлении
    пункта и отдельное сообщение по достижении 20."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    assert "20 пунктов" in vk.last_message

    ex.handle_message(UID, "Кормить детей")
    assert "(1/20)" in vk.last_message

    for i in range(19):
        ex.handle_message(UID, f"Пункт {i}")

    assert len(ex.user_sessions[UID]["must_items"]) == 20
    assert "Отлично! Ты собрал 20 пунктов" in vk.last_message


def test_conscious_choice_full_flow_to_finish():
    """Шаги 4 и 5 ("Анализ выбора" и "Альтернативы") разбиты на отдельные
    экраны — сначала показывается сам выбор (подтверждение "Продолжить"),
    потом отдельно минусы, потом отдельно плюсы, каждый можно ответить
    текстом или пропустить кнопкой "Продолжить"."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    assert ex.user_sessions[UID]["step"] == 1

    ex.handle_message(UID, "Кормить детей")        # добавлен must-пункт
    ex.handle_message(UID, "➡️ Продолжить")        # -> step 2 (current_must = "Кормить детей")
    assert ex.user_sessions[UID]["step"] == 2

    ex.handle_message(UID, "Никто не отнял")        # who_took -> step 3
    assert ex.user_sessions[UID]["step"] == 3

    ex.handle_message(UID, "Я сам")                 # who_greater -> step 4 (ack "Я выбираю")
    assert ex.user_sessions[UID]["step"] == 4
    assert "Я выбираю" in vk.last_message

    ex.handle_message(UID, "➡️ Продолжить")        # -> step 5 (минусы)
    assert ex.user_sessions[UID]["step"] == 5
    assert "Не хочу" in vk.last_message

    ex.handle_message(UID, "устану")                # choice_minus -> step 6 (плюсы)
    assert ex.user_sessions[UID]["step"] == 6
    assert "Хочу" in vk.last_message

    ex.handle_message(UID, "увижу улыбку")          # choice_plus -> step 7 (alt ack)
    assert ex.user_sessions[UID]["step"] == 7
    assert "устану" in ex.user_sessions[UID]["choice_analysis"]
    assert "увижу улыбку" in ex.user_sessions[UID]["choice_analysis"]

    ex.handle_message(UID, "➡️ Продолжить")        # -> step 8 (другие минусы)
    assert ex.user_sessions[UID]["step"] == 8

    ex.handle_message(UID, "➡️ Продолжить")        # пропускаем минусы -> step 9 (другие плюсы)
    assert ex.user_sessions[UID]["step"] == 9

    ex.handle_message(UID, "энергия")               # alt_plus -> step 10 -> _finish()
    assert UID not in ex.user_sessions, "Упражнение должно завершиться после шага 9"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["must_items"] == ["Кормить детей"]
    assert result["answers"]["who_took"] == "Никто не отнял"
    assert result["answers"]["who_greater"] == "Я сам"
    assert "устану" in result["choice_analysis"]
    assert "энергия" in result["alternatives"]
    assert "—" in result["alternatives"], "Пропущенные минусы должны отметиться прочерком"


def test_conscious_choice_skip_all_minus_plus_via_continue():
    """Все 4 экрана минусов/плюсов (шаги 5, 6, 8, 9) можно пропустить одной
    кнопкой «Продолжить», не отвечая ни разу — упражнение всё равно
    доходит до конца."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")   # -> step 2
    ex.handle_message(UID, "Никто не отнял")   # -> step 3
    ex.handle_message(UID, "Я сам")            # -> step 4

    for _ in range(6):  # шаги 4,5,6,7,8,9 — каждый пропускается "Продолжить"
        ex.handle_message(UID, "➡️ Продолжить")

    assert UID not in ex.user_sessions, "Упражнение должно завершиться, даже если все минусы/плюсы пропущены"
    result = api.results[-1]["result_data"]
    assert result["choice_analysis"] == "Минусы: —, Плюсы: —"
    assert result["alternatives"] == "Минусы: —, Плюсы: —"


def test_conscious_choice_ack_steps_reprompt_on_unexpected_text():
    """Шаги 4 и 7 — экраны-подтверждения без поля ввода: если пользователь
    вместо «Продолжить» пришлёт текст, шаг не должен смениться."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Никто не отнял")
    ex.handle_message(UID, "Я сам")            # -> step 4

    ex.handle_message(UID, "случайный текст")
    assert ex.user_sessions[UID]["step"] == 4
    assert "Жми «Продолжить»" in vk.last_message

    ex.handle_message(UID, "➡️ Продолжить")   # -> 5
    ex.handle_message(UID, "устану")           # -> 6
    ex.handle_message(UID, "улыбка")           # -> 7

    ex.handle_message(UID, "случайный текст")
    assert ex.user_sessions[UID]["step"] == 7
    assert "Жми «Продолжить»" in vk.last_message


def test_my_roles_full_flow_two_step_analysis():
    """Разбор каждой роли — два отдельных шага: сначала 'Идеально', потом
    'Ужасно' (заменили хрупкий формат 'Идеально: ..., Ужасно: ...' одной
    строкой на последовательные вопросы, см. СВОДКА_ПРОЕКТА.md).

    Не больше одной роли (Идеально + Ужасно) в день — роли 2 и 3
    разбираются "в другие дни" через подмену _today_str."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-29"
    ex.start(UID)

    ex.handle_message(UID, "Продавец")             # social role
    ex.handle_message(UID, "➡️ Продолжить")        # -> interpersonal
    ex.handle_message(UID, "Друг для Саши")        # interpersonal role
    ex.handle_message(UID, "➡️ Продолжить")        # -> intrapersonal
    ex.handle_message(UID, "Смелый")               # intrapersonal role
    ex.handle_message(UID, "➡️ Продолжить")        # -> analyze, роль 1 ("Продавец"), шаг 1

    session = ex.user_sessions[UID]
    assert session["phase"] == "analyze"
    assert session["analysis_index"] == 0
    assert session["analysis_step"] == 1
    assert "идеально" in vk.last_message.lower()

    # шаг 1: "Идеально" — любой текст принимается, продвигает на шаг 2
    ex.handle_message(UID, "всё отлично")
    assert ex.user_sessions[UID]["analysis_step"] == 2
    assert ex.user_sessions[UID]["analysis_index"] == 0, "Индекс роли не должен смениться между шагами 1 и 2"
    assert ex.user_sessions[UID]["current_ideal"] == "всё отлично"
    assert "ужасно" in vk.last_message.lower()

    # шаг 2: "Ужасно" — завершает роль 1, переходит к роли 2, снова шаг 1
    # (но роль 2 в тот же день заблокирована дневным лимитом — сразу
    # показывается сообщение о лимите, см. ниже)
    ex.handle_message(UID, "провал")
    assert ex.user_sessions[UID]["analysis_index"] == 1
    assert ex.user_sessions[UID]["analysis_step"] == 1
    assert "current_ideal" not in ex.user_sessions[UID]
    assert "уже разобрана" in vk.last_message.lower()

    # та же дата, обычный текст (не кнопка) — просто напоминание про кнопки,
    # роль 2 без явного подтверждения "Всё равно продолжить" не начинается
    ex.handle_message(UID, "дружба")
    assert ex.user_sessions[UID]["analysis_index"] == 1, "В тот же день вторая роль не должна начинаться"
    assert "всё равно продолжить" in vk.last_message.lower()

    # новый день — роль 2 (Друг для Саши)
    ex._today_str = lambda: "2026-08-30"
    ex.handle_message(UID, "дружба")
    ex.handle_message(UID, "ссора")
    assert ex.user_sessions[UID]["analysis_index"] == 2

    # тот же день — роль 3 заблокирована
    ex.handle_message(UID, "смелость")
    assert ex.user_sessions[UID]["analysis_index"] == 2

    # ещё один новый день — роль 3 (Смелый), последняя, упражнение завершается
    ex._today_str = lambda: "2026-08-31"
    ex.handle_message(UID, "смелость")
    ex.handle_message(UID, "трусость")
    assert UID not in ex.user_sessions, "После анализа всех ролей упражнение должно завершиться"

    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["social_roles"] == ["Продавец"]
    assert result["interpersonal_roles"] == ["Друг для Саши"]
    assert result["intrapersonal_roles"] == ["Смелый"]
    assert len(result["analysis"]) == 3
    assert result["analysis"][0] == {"role": "Продавец", "ideal": "всё отлично", "terrible": "провал"}
    assert result["analysis"][1] == {"role": "Друг для Саши", "ideal": "дружба", "terrible": "ссора"}
    assert result["analysis"][2] == {"role": "Смелый", "ideal": "смелость", "terrible": "трусость"}


def test_my_roles_daily_limit_can_be_overridden_for_one_extra_role():
    """Пользователь может настоять и разобрать ещё одну роль в тот же день
    через кнопку «⚠️ Всё равно продолжить» — лимит становится мягким
    предупреждением, а не жёсткой блокировкой."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-31"
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль Б")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль В")
    ex.handle_message(UID, "➡️ Продолжить")   # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "идеально 1")
    ex.handle_message(UID, "ужасно 1")        # роль 1 разобрана сегодня

    assert ex.user_sessions[UID]["analysis_index"] == 1
    assert "снижает" in vk.last_message.lower(), "Должно быть предупреждение об эффективности"
    assert vk.last_buttons == ["⚠️ Всё равно продолжить", "💾 Сохранить и выйти"]

    ex.handle_message(UID, "⚠️ Всё равно продолжить")
    assert ex.user_sessions[UID]["analysis_step"] == 1
    assert "идеально" in vk.last_message.lower(), "После подтверждения роль 2 должна начать разбор"
    assert ex.user_sessions[UID]["_daily_override_active"] is True

    ex.handle_message(UID, "идеально 2")
    ex.handle_message(UID, "ужасно 2")        # роль 2 разобрана в переопределённом режиме

    assert ex.user_sessions[UID]["analysis_index"] == 2
    assert "_daily_override_active" not in ex.user_sessions[UID], "Override не должен переноситься на роль 3"

    # роль 3 в тот же день — лимит снова спрашивает подтверждение, override
    # не переносится молча на все последующие роли
    assert "снижает" in vk.last_message.lower()
    ex.handle_message(UID, "идеально 3")
    assert ex.user_sessions[UID]["analysis_index"] == 2, "Без нового подтверждения роль 3 не должна начаться"


def test_my_roles_daily_limit_prompt_becomes_stale_after_midnight():
    """Если сообщение о лимите ещё висит на экране, а календарный день уже
    сменился, следующий текст должен обработаться как обычный ответ, а не
    как устаревшее напоминание про кнопки."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-31"
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль Б")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Продолжить")  # intrapersonal: 0 ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "идеально 1")
    ex.handle_message(UID, "ужасно 1")
    assert ex.user_sessions[UID]["_daily_limit_prompt"] is True

    ex._today_str = lambda: "2026-09-01"  # наступил новый день
    ex.handle_message(UID, "новый идеальный ответ")
    assert ex.user_sessions[UID]["analysis_step"] == 2, "Должно было обработаться как ответ 'Идеально', а не как нажатие кнопки"
    assert ex.user_sessions[UID]["current_ideal"] == "новый идеальный ответ"
    assert "_daily_limit_prompt" not in ex.user_sessions[UID]


def test_my_roles_daily_limit_blocks_second_role_same_day():
    """После разбора одной роли (Идеально+Ужасно) в один день — попытка
    начать анализ следующей роли в тот же день должна показать сообщение
    о дневном лимите, а не новую роль."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-31"
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль Б")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Продолжить")  # intrapersonal: 0 ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "идеально 1")
    ex.handle_message(UID, "ужасно 1")        # роль 1 разобрана сегодня

    assert ex.user_sessions[UID]["analysis_index"] == 1
    assert "выйти" in vk.last_buttons[0].lower() or any("выйти" in b.lower() for b in vk.last_buttons)

    # заново вызов _show_instruction/_resume_analyze (например, при возврате
    # в упражнение в тот же день) тоже должен показать лимит, а не роль 2
    ex._show_instruction(UID, ex.user_sessions[UID])
    assert "уже разобрана" in vk.last_message.lower()

    # подстраховка в _handle_analysis: если пользователь всё же пишет текст,
    # пока заблокировано, роль 2 не должна начаться
    ex.handle_message(UID, "случайный текст")
    assert ex.user_sessions[UID]["analysis_index"] == 1
    assert "current_ideal" not in ex.user_sessions[UID]


def test_my_roles_used_analysis_today_helpers():
    """_used_analysis_today/_mark_analysis_today корректно отражают
    'сделал сегодня или нет' по сохранённой дате."""
    ex, vk, api = make(MyRolesExercise)
    session = {}
    assert ex._used_analysis_today(session) is False

    ex._today_str = lambda: "2026-08-31"
    ex._mark_analysis_today(session)
    assert session["last_analysis_date"] == "2026-08-31"
    assert ex._used_analysis_today(session) is True

    ex._today_str = lambda: "2026-09-01"
    assert ex._used_analysis_today(session) is False


def test_my_roles_message_without_session_restarts():
    """Сообщение без активной сессии (например, после рестарта бота) должно
    молча запускать start() заново, а не падать."""
    ex, vk, api = make(MyRolesExercise)
    assert UID not in ex.user_sessions
    ex.handle_message(UID, "что угодно")
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["phase"] == "social"


def test_my_roles_resume_prompt_rejects_unrecognized_text():
    """На экране 'продолжить с того места?' любой текст, кроме кнопок
    Продолжить/Начать заново, должен просто напомнить про кнопки, не теряя
    _resume_prompt и не трогая сохранённые роли."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "💾 Сохранить и выйти")

    ex2, vk2, _ = make(MyRolesExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    assert ex2.user_sessions[UID]["_resume_prompt"] is True

    ex2.handle_message(UID, "непонятный ответ")
    assert ex2.user_sessions[UID]["_resume_prompt"] is True, "Неизвестный текст не должен снимать resume_prompt"
    assert "Продолжить" in vk.last_message and "Начать заново" in vk.last_message
    assert ex2.user_sessions[UID]["social_roles"] == ["Роль А"], "Сохранённые роли не должны были пострадать"


def test_my_roles_plain_restart_text_without_resume_prompt():
    """'Начать заново' вне экрана resume_prompt (например, во время сбора
    ролей) тоже должно сбрасывать прогресс, как и '💾 Сохранить и начать заново'."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    assert ex.user_sessions[UID]["social_roles"] == ["Роль А"]

    ex.handle_message(UID, "начать заново")
    assert ex.user_sessions[UID]["social_roles"] == [], "Роли должны были сброситься"
    assert ex.user_sessions[UID]["phase"] == "social"


def test_my_roles_resume_analyze_finishes_when_all_roles_already_analyzed():
    """_resume_analyze — защитная ветка: если analysis_index уже указывает
    за пределы списка ролей (например, восстановленный прогресс), должен
    сразу завершить упражнение, а не упасть или показать пустую роль."""
    ex, vk, api = make(MyRolesExercise)
    session = ex._fresh_session()
    session.update({
        'phase': 'analyze',
        'social_roles': ['Роль А'],
        'analysis_index': 1,
        'analysis_results': [{'role': 'Роль А', 'ideal': 'и', 'terrible': 'у'}],
    })
    ex.user_sessions[UID] = session

    ex._resume_analyze(UID, session)
    assert UID not in ex.user_sessions
    assert len(api.results) == 1


def test_my_roles_resume_mid_analysis_does_not_lose_ideal_answer():
    """Возобновление сессии ПОСЛЕ ответа на 'Идеально', но ДО ответа на
    'Ужасно' (например бот перезапустился между сообщениями) не должно
    сбрасывать уже введённый ответ и не должно откатывать на шаг 1."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Продолжить")  # 0 interpersonal ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> intrapersonal
    ex.handle_message(UID, "➡️ Продолжить")  # 0 intrapersonal ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "всё отлично")     # -> шаг 2 ('current_ideal' сохранён)

    # "перезапуск бота": новый объект, тот же api (тот же сохранённый прогресс)
    ex2, vk2, _ = make(MyRolesExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    assert vk.last_buttons == ["Продолжить ✅", "Начать заново 🔄"]

    ex2.handle_message(UID, "Продолжить ✅")
    assert ex2.user_sessions[UID]["analysis_step"] == 2, "Должен остаться на шаге 2, не откатиться на 1"
    assert ex2.user_sessions[UID]["current_ideal"] == "всё отлично"
    assert "ужасно" in vk.last_message.lower()

    ex2.handle_message(UID, "провал")
    assert len(api.results) == 1
    assert api.results[0]["result_data"]["analysis"][0] == {
        "role": "Продавец", "ideal": "всё отлично", "terrible": "провал"
    }


def test_two_users_do_not_share_session_state():
    """Один и тот же объект упражнения (как в реальном боте — один
    HappinessListExercise на всех пользователей) не должен путать данные
    двух разных user_id, идущих параллельно."""
    ex, vk, api = make(HappinessListExercise)
    UID_A, UID_B = 111, 222

    ex.start(UID_A)
    ex.start(UID_B)
    ex.handle_message(UID_A, "Кофе утром — 8")
    ex.handle_message(UID_B, "Прогулка — 9")
    ex.handle_message(UID_A, "Музыка — 7")

    assert [i["text"] for i in ex.user_sessions[UID_A]["items"]] == ["Кофе утром", "Музыка"]
    assert [i["text"] for i in ex.user_sessions[UID_B]["items"]] == ["Прогулка"]

    ex.handle_message(UID_B, "💾 Сохранить и начать заново")
    assert UID_A in ex.user_sessions, "Действие пользователя B не должно закрывать сессию пользователя A"
    assert len(ex.user_sessions[UID_A]["items"]) == 2, "Данные пользователя A не должны были пострадать"

    result_for_b = [r for r in api.results if r["user_vk_id"] == UID_B]
    assert len(result_for_b) == 1
    assert result_for_b[0]["result_data"]["items"][0]["text"] == "Прогулка"


def test_stress_search_question_step2_validates_percent():
    """Шаг 2/4 (реалистичность в %) должен отвергать нечисловой ввод и
    число вне 0-100, не продвигая question_step и не теряя ответ шага 1."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")   # analysis
    ex.handle_message(UID, "➡️ Далее")        # question, step 1
    ex.handle_message(UID, "Идеальная ситуация")  # step 1 -> step 2

    ex.handle_message(UID, "не число")
    assert ex.user_sessions[UID]["question_step"] == 2, "Нечисловой % не должен продвигать шаг"
    assert "0 до 100" in vk.last_message

    ex.handle_message(UID, "150")
    assert ex.user_sessions[UID]["question_step"] == 2, "% вне 0-100 не должен продвигать шаг"

    ex.handle_message(UID, "70")  # корректно -> step 3
    assert ex.user_sessions[UID]["question_step"] == 3
    assert ex.user_sessions[UID]["answers"][-1]["ideal"] == "Идеальная ситуация", (
        "Ответ шага 1 не должен был потеряться из-за ошибок ввода на шаге 2"
    )
    assert ex.user_sessions[UID]["answers"][-1]["percent"] == 70


def test_stress_search_full_flow_through_all_questions_to_finish():
    """Естественное завершение через все 4 вопроса разбора для каждого
    образа (а не досрочное '✅ Завершить' из фазы analysis) — до сих пор
    не было ни разу пройдено целиком ни для одного, ни для нескольких
    образов подряд."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "Семья 5")
    ex.handle_message(UID, "➡️ Продолжить")   # -> analysis, 2 образа
    ex.handle_message(UID, "➡️ Далее")        # -> вопрос по образу 1, step 1

    # образ 1: все 4 шага
    ex.handle_message(UID, "Идеал 1")
    ex.handle_message(UID, "80")
    ex.handle_message(UID, "Почему 1")
    ex.handle_message(UID, "Рефлексия 1")  # step 4 -> следующий образ

    session = ex.user_sessions[UID]
    assert session["question_index"] == 1, "После образа 1 индекс должен указывать на образ 2"
    assert len(session["answers"]) == 2, "Для образа 2 должна была добавиться новая запись answers"
    assert session["answers"][0] == {
        "text": "Работа", "rate": 8,
        "ideal": "Идеал 1", "percent": 80, "why": "Почему 1", "reflection": "Рефлексия 1",
    }

    # образ 2: все 4 шага -> естественное завершение (index >= len(items))
    ex.handle_message(UID, "Идеал 2")
    ex.handle_message(UID, "40")
    ex.handle_message(UID, "Почему 2")
    ex.handle_message(UID, "Рефлексия 2")

    assert UID not in ex.user_sessions, "После разбора обоих образов упражнение должно завершиться само"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 2
    assert len(result["analysis"]) == 2
    assert result["analysis"][1] == {
        "text": "Семья", "rate": 5,
        "ideal": "Идеал 2", "percent": 40, "why": "Почему 2", "reflection": "Рефлексия 2",
    }


def test_diary_advance_without_answer_shows_error_and_does_not_advance():
    """Нажатие «➡️ Продолжить» до того, как что-то написано на шаге,
    должно показать «❌ Напиши...» и не сдвигать фазу вперёд."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "dream", "Фаза не должна была смениться без ответа"
    assert "Напиши свой сон" in vk.last_message

    ex.handle_message(UID, "Гулял по парку")  # ответ сразу переводит на фазу 'mood'
    assert ex.user_sessions[UID]["phase"] == "mood"

    # на новой фазе тот же guard снова срабатывает, пока нет ответа
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "mood", "Фаза не должна была смениться без ответа на 'mood'"
    assert "Напиши настроение" in vk.last_message


def test_stop_technique_advance_without_answer_shows_error_and_does_not_advance():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "thoughts"
    assert "Напиши, о чём думаешь" in vk.last_message


def test_conscious_choice_advance_without_answer_shows_error_at_each_gated_step():
    """Шаги 1-3 обязательны (нельзя продолжить без ответа). Шаги 4-9
    (подтверждение выбора + минусы/плюсы по отдельности для "Анализа
    выбора" и "Альтернатив") НЕ обязательны — "Продолжить" всегда
    пропускает их дальше, см. test_conscious_choice_full_flow_to_finish."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)

    # шаг 1: 0 пунктов -> "Продолжить" отклоняется
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["step"] == 1
    assert "хотя бы один пункт" in vk.last_message

    ex.handle_message(UID, "Кормить детей")     # 1 пункт -> теперь можно перейти
    ex.handle_message(UID, "➡️ Продолжить")     # -> step 2
    assert ex.user_sessions[UID]["step"] == 2

    # шаг 2: "Продолжить" без ответа на вопрос
    ex.handle_message(UID, "✅ Завершить")
    assert ex.user_sessions[UID]["step"] == 2
    assert "Напиши свой ответ" in vk.last_message

    ex.handle_message(UID, "Никто не отнял")
    # шаг 3: "Продолжить" без ответа
    ex.handle_message(UID, "✅ Завершить")
    assert ex.user_sessions[UID]["step"] == 3
    assert "Напиши свой ответ" in vk.last_message


def test_happiness_list_finish_with_empty_list_shows_error_and_does_not_finish():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")  # 0 пунктов
    assert "Список пуст" in vk.last_message
    assert len(api.results) == 0
    assert UID in ex.user_sessions, "Упражнение не должно было завершиться на пустом списке"


def test_stress_search_saves_result_with_correct_exercise_type():
    """Результат должен сохраняться под exercise_type='stress_search',
    как и остальные 5 упражнений — иначе он не попадёт в 'Мои результаты'
    и его нельзя будет отправить на проверку психологу."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")   # analysis
    ex.handle_message(UID, "✅ Завершить")     # завершить сразу из анализа

    assert len(api.results) == 1
    assert api.results[0]["exercise_type"] == "stress_search", (
        f"Результат сохранён с exercise_type={api.results[0]['exercise_type']!r}, "
        f"а не 'stress_search' — см. _finish_exercise(), там 'exercise_id = 1'"
    )


# ---------------------------------------------------------------------------
# Навигация по шагам (⬅️ Назад / 🏠 В начало / 🏁 В конец) — diary,
# stop_technique, conscious_choice
# ---------------------------------------------------------------------------

def test_diary_back_to_start_and_end_navigation():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")   # dream -> mood
    ex.handle_message(UID, "Спокойное")        # mood -> body

    session = ex.user_sessions[UID]
    assert session["phase"] == "body"
    assert session["_max_phase_index"] == 2

    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["phase"] == "mood"
    assert "Текущий ответ" in vk.last_message and "Спокойное" in vk.last_message

    ex.handle_message(UID, "🏠 В начало")
    assert ex.user_sessions[UID]["phase"] == "dream"
    assert "Гулял по парку" in vk.last_message

    ex.handle_message(UID, "🏁 В конец")
    assert ex.user_sessions[UID]["phase"] == "body", (
        "«В конец» должно вести на самый дальний из достигнутых шагов, а не на текущий"
    )


def test_diary_back_at_first_step_is_noop():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["phase"] == "dream"
    assert "первый шаг" in vk.last_message


def test_stop_technique_back_to_start_and_end_navigation():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "О работе")   # thoughts -> feelings
    ex.handle_message(UID, "Усталость")  # feelings -> wants

    assert ex.user_sessions[UID]["phase"] == "wants"

    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["phase"] == "feelings"
    assert "Текущий ответ" in vk.last_message and "Усталость" in vk.last_message

    ex.handle_message(UID, "🏠 В начало")
    assert ex.user_sessions[UID]["phase"] == "thoughts"

    ex.handle_message(UID, "🏁 В конец")
    assert ex.user_sessions[UID]["phase"] == "wants"


def test_conscious_choice_back_to_start_and_end_navigation():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")       # must_items[0]
    ex.handle_message(UID, "➡️ Продолжить")        # -> step 2
    ex.handle_message(UID, "Никто")                # step 2 -> 3
    ex.handle_message(UID, "Никто")                # step 3 -> 4

    session = ex.user_sessions[UID]
    assert session["step"] == 4
    assert session["_max_step"] == 4

    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["step"] == 3
    assert "Текущий ответ" in vk.last_message

    ex.handle_message(UID, "🏠 В начало")
    assert ex.user_sessions[UID]["step"] == 1

    ex.handle_message(UID, "🏁 В конец")
    assert ex.user_sessions[UID]["step"] == 4, (
        "«В конец» должно вести на самый дальний из достигнутых шагов"
    )


def test_conscious_choice_back_at_step1_is_noop():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["step"] == 1
    assert "первый шаг" in vk.last_message
