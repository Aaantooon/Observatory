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


def _diary_resume(ex, uid=UID):
    """Дневник теперь идёт тремя заходами в течение дня (Утро/День/Вечер,
    см. DiaryExercise.PHASE_BLOCK) — ответ, закрывающий блок (сон; хочу),
    завершает сессию (_show_block_boundary), а не сразу показывает
    следующий вопрос. Этот хелпер имитирует «заглянул попозже»: заново
    открывает «Дневник» и жмёт «Продолжить» на приглашении возобновить."""
    ex.start(uid)
    ex.handle_message(uid, "Продолжить")


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
# diary / stop_technique — фиксированные линейные упражнения. Раньше их
# клавиатура (step_nav_keyboard()) ещё показывала кнопки навигации по шагам
# (Назад / В начало / В конец) — по просьбе пользователя убраны как
# визуальный шум; команды по-прежнему работают, если их напечатать текстом
# (см. BACK_TEXTS/TO_START_TEXTS/TO_END_TEXTS в keyboards.py и тесты
# навигации ниже). Клавиатура сейчас совпадает с обычной EXERCISE_KEYBOARD_BUTTONS.
STEP_NAV_KEYBOARD_BUTTONS = EXERCISE_KEYBOARD_BUTTONS
# conscious_choice — линейное упражнение, у него те же три кнопки, но
# подписи "начать заново"/"выйти" — в обратном порядке слов, см.
# conscious_choice_keyboard().
CONSCIOUS_CHOICE_KEYBOARD_BUTTONS = [
    "➡️ Продолжить", "🔄 Начать заново и сохранить", "💾 Выйти и сохранить",
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
        elif name == "diary":
            # Первый же ответ ("Сон") сам закрывает сессию на границе блока
            # Утро -> День (см. _show_block_boundary) — заглядываем снова,
            # чтобы было что сохранять на активной сессии.
            ex.handle_message(UID, "Тестовый ответ")
            _diary_resume(ex)
        else:
            ex.handle_message(UID, "Тестовый ответ")

        before_results = len(api.results)
        ex.handle_message(UID, "💾 Сохранить и начать заново")

        # stress_search — особый случай: с 01.09.2026 "Сохранить и начать
        # заново" отправляет наблюдателю только если материала достаточно
        # (см. _can_finish_early) — с одним записанным и нулём разобранных
        # это не так, поэтому здесь результат НЕ должен сохраняться (см.
        # отдельный test_stress_search_save_and_restart_* ниже на оба случая).
        if name == "stress_search":
            assert len(api.results) == before_results, (
                f"{name}: с 1 записанным и 0 разобранных отправлять наблюдателю ещё рано"
            )
        else:
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
    assert "▮" in vk.last_message and "%" in vk.last_message


def test_my_roles_shows_progress_bar_when_adding_role():
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    assert "▮" in vk.last_message and "%" in vk.last_message


def test_conscious_choice_shows_progress_bar_when_adding_item():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    assert "▮" in vk.last_message and "%" in vk.last_message


def test_diary_shows_step_progress_bar():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    assert "▮" in vk.last_message and "%" in vk.last_message
    ex.handle_message(UID, "Гулял по парку")  # dream -> блок "День" ждёт
    _diary_resume(ex)  # заглянули через час, показался шаг 2
    assert "▮" in vk.last_message and "%" in vk.last_message


def test_stop_technique_shows_step_progress_bar():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    assert "▮" in vk.last_message and "%" in vk.last_message


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
    ex.handle_message(UID, "✅ Да, дальше")   # -> экран подтверждения перед разбором
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


def test_my_roles_confirm_empty_phase_does_not_survive_save_and_exit_resume():
    """Баг #2: '_confirm_empty_phase' — транзитный флаг "жду да/нет"; если
    он буквально сохранится через 'Сохранить и выйти' и потом молча
    восстановится при возобновлении (session.update(data) в start()), то
    следующий реальный ответ пользователя проглатывается мёртвой проверкой
    _confirm_empty_phase, и человек застревает без видимой причины и без
    выхода (кроме 'Начать заново', которое стирает все роли)."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")       # social: 1 роль -> has_saved=True при resume
    ex.handle_message(UID, "➡️ Продолжить")  # social непустой -> сразу interpersonal
    assert ex.user_sessions[UID]["phase"] == "interpersonal"

    ex.handle_message(UID, "➡️ Продолжить")  # interpersonal пуст -> ставит _confirm_empty_phase
    assert ex.user_sessions[UID]["_confirm_empty_phase"] is True

    # Пользователь вместо да/нет жмёт "Сохранить и выйти" — сессия
    # персистится (_handle_cancel -> save_progress) с флагом ещё активным.
    ex.handle_message(UID, "💾 Сохранить и выйти")
    assert UID not in ex.user_sessions

    # Флаг не должен был буквально попасть в персистентное хранилище.
    saved = api.progress_store.get((UID, "my_roles"))
    assert saved is not None
    assert "_confirm_empty_phase" not in saved, (
        "'_confirm_empty_phase' — транзитный флаг, не должен переживать save/exit"
    )

    # "Перезапуск бота": новый объект упражнения, тот же сохранённый прогресс.
    vk2 = FakeVK()
    ex2 = MyRolesExercise(vk2, api)  # тот же backend (то же хранилище прогресса)
    ex2.start(UID)
    assert ex2.user_sessions[UID].get("_resume_prompt") is True
    ex2.handle_message(UID, "✅ Продолжить")  # закрывает resume-prompt

    # Флаг отсутствует -> обычный ответ должен нормально обработаться как
    # роль, а НЕ быть проглочен мёртвой confirm-проверкой.
    assert "_confirm_empty_phase" not in ex2.user_sessions[UID]
    assert ex2.user_sessions[UID]["phase"] == "interpersonal"
    ex2.handle_message(UID, "Друг")
    assert "Друг" in ex2.user_sessions[UID]["interpersonal_roles"], (
        "Реальный ответ должен был добавиться как роль, а не быть проглочен "
        "застрявшим _confirm_empty_phase"
    )


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
    ex.handle_message(UID, "✅ Да, дальше")    # -> экран подтверждения перед разбором
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
    ex.handle_message(UID, "Гулял по парку")           # dream -> блок "День" ждёт
    _diary_resume(ex)                                   # заглянули через час
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
# diary — три блока в течение дня (Утро -> День -> Вечер), см. PHASE_BLOCK
# ---------------------------------------------------------------------------

def test_diary_morning_block_ends_session_and_schedules_hour_reminder():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")  # dream -> блок "День" ждёт
    assert UID not in ex.user_sessions, "Между блоками сессия завершается, как при отмене"
    assert "Утренняя часть готова" in vk.last_message
    assert len(api.created_notifications) == 1, "Должно быть поставлено одноразовое напоминание через час"
    notif = api.created_notifications[0]
    assert notif["exercise_type"] == "diary_day"
    assert notif["schedule_type"] == "once"
    assert notif["schedule_data"]["delay_hours"] == 1


def test_diary_day_block_ends_session_without_extra_reminder_for_evening():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")
    _diary_resume(ex)
    ex.handle_message(UID, "Спокойное")
    ex.handle_message(UID, "Тело в норме")
    ex.handle_message(UID, "Мысли о работе")
    ex.handle_message(UID, "Хочу кофе")  # wants -> блок "Вечер" ждёт
    assert UID not in ex.user_sessions
    assert "Дневная часть готова" in vk.last_message
    # На переход День -> Вечер отдельное авто-напоминание не ставим — только
    # то одно, что уже было поставлено на переходе Утро -> День.
    assert len(api.created_notifications) == 1


def test_diary_resume_prompt_names_the_next_block():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")
    ex.start(UID)
    assert "День" in vk.last_message


def test_diary_pressing_continue_right_away_does_not_wait_for_the_hour():
    """«Не блокировать» — можно продолжить сразу же, не дожидаясь реального
    часа; ожидание — просто рекомендация в тексте, а не проверка времени."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")
    _diary_resume(ex)
    assert ex.user_sessions[UID]["phase"] == "mood"
    assert "Напиши своё настроение" in vk.last_message or "Шаг 2: Настроение" in vk.last_message


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


def test_happiness_list_show_items_truncates_long_entries_to_avoid_vk_limit():
    """Баг #4: список пунктов на экране resume ('Продолжим?' -> 'Продолжить')
    конкатенирует текст ВСЕХ пунктов без ограничения — с длинными пунктами
    сообщение легко превышает лимит VK ~4096 символов."""
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    long_text = "Б" * 500
    for i in range(10):
        ex.handle_message(UID, f"{long_text}{i} — 5")

    # "перезапуск бота" — новый объект, тот же сохранённый прогресс,
    # чтобы дойти до _show_items() через resume-flow.
    ex2, vk2, _ = make(HappinessListExercise)
    ex2.api = api
    ex2.start(UID)
    ex2.handle_message(UID, "➡️ Продолжить")  # закрывает resume-prompt -> _show_items()

    assert len(vk2.last_message) < 4096, (
        f"Список из 10 длинных пунктов должен был обрезаться, длина={len(vk2.last_message)}"
    )


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
    ex.handle_message(UID, "Идеальная ситуация")  # step 1 -> ждём подтверждения
    ex.handle_message(UID, "➡️ Продолжить")        # подтверждение -> step 1 -> 2

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


def test_stress_search_rejects_duplicate_single_item():
    """Нельзя записать один и тот же образ дважды (по просьбе пользователя:
    не должно быть дубликатов пунктов) — сравнение без учёта регистра и
    пробелов по краям."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    ex.handle_message(UID, "Работа 8")
    assert len(ex.user_sessions[UID]["items"]) == 1

    ex.handle_message(UID, "работа  5")  # тот же текст, другой регистр/пробелы/оценка
    assert len(ex.user_sessions[UID]["items"]) == 1, "Повтор не должен добавиться"
    assert ex.user_sessions[UID]["items"][0]["rate"] == 8, "Исходная запись не должна измениться"
    assert "уже есть" in vk.last_message.lower()

    ex.handle_message(UID, "Учёба 6")  # другой текст — добавляется нормально
    assert len(ex.user_sessions[UID]["items"]) == 2


def test_stress_search_pasted_list_skips_duplicates():
    """Дедупликация работает и при вставке списком — и против уже
    записанных пунктов, и внутри самой вставки."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")

    pasted = "работа 5\nШум за окном 7\nшум за окном 6\nДедлайны 9"
    ex.handle_message(UID, pasted)

    items = ex.user_sessions[UID]["items"]
    texts = [i["text"] for i in items]
    assert texts == ["Работа", "Шум за окном", "Дедлайны"], (
        "Повтор «работа» (уже есть) и повтор «шум за окном» (внутри вставки) должны быть пропущены"
    )
    assert "Добавлено образов: 2" in vk.last_message
    assert "Пропущено повторов" in vk.last_message


def test_stress_search_pasted_list_all_duplicates_adds_nothing():
    """Если вся вставка состоит из уже записанных пунктов — ничего не
    добавляется и об этом честно сообщается, а не показывается «Добавлено
    образов: 0»."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8\nУчёба 6")

    ex.handle_message(UID, "работа 5\nучёба 7")

    assert len(ex.user_sessions[UID]["items"]) == 2, "Ничего нового не должно было добавиться"
    assert "уже есть" in vk.last_message.lower()
    assert "Добавлено образов" not in vk.last_message


def test_stress_search_pasted_long_multiline_list_does_not_exceed_vk_limit():
    """Баг #4: вставленный многострочный список эхается целиком без
    ограничения — с длинными строками (или их большим числом) сообщение
    легко превышает лимит VK ~4096 символов."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)

    long_word = "В" * 300
    pasted = "\n".join(f"{long_word}{i} {5 + (i % 5)}" for i in range(20))
    ex.handle_message(UID, pasted)

    assert len(ex.user_sessions[UID]["items"]) == 20
    assert len(vk.last_message) < 4096, (
        f"Подтверждение вставки должно было обрезаться, длина={len(vk.last_message)}"
    )


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


def test_stress_search_reaching_100_auto_advances_to_analysis_single_item():
    """Когда 100-й пункт добавлен по одному (не списком) — переход в Часть 2
    должен происходить сразу, без ожидания «Продолжить» от пользователя."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    session = ex.user_sessions[UID]
    session["items"] = [{"text": f"Пункт {i}", "rate": 5} for i in range(99)]

    ex.handle_message(UID, "Последний пункт 8")

    assert len(session["items"]) == 100
    assert session["phase"] == "analysis", (
        "После 100-го пункта сессия должна была сама перейти в разбор (Часть 2)"
    )
    assert "100 пунктов набрано" in vk.sent[-2]["message"]
    assert "РАЗБОР ПУТИ" in vk.last_message, (
        "Сообщение с разбором (Часть 2) должно было прийти сразу следом, без обрыва"
    )


def test_stress_search_reaching_100_auto_advances_to_analysis_batch():
    """То же самое, когда 100-й (и последующие) пункт добавлен вставкой
    сразу нескольких строк одним сообщением."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    session = ex.user_sessions[UID]
    session["items"] = [{"text": f"Пункт {i}", "rate": 5} for i in range(97)]

    ex.handle_message(UID, "Предпоследний 7\nПоследний 8\nЛишний сверху 6")

    assert len(session["items"]) == 100
    assert session["phase"] == "analysis"
    assert "100 пунктов набрано" in vk.sent[-2]["message"]
    assert "РАЗБОР ПУТИ" in vk.last_message


def test_stress_search_question1_asks_confirmation_before_advancing():
    """После ответа на Вопрос 1 (противоположность) бот должен сначала
    спросить подтверждение и только после «Да» переходить к Вопросу 2 —
    не сохранять ответ и не продвигать question_step сразу."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "Пунктуальность")
    session = ex.user_sessions[UID]
    assert session["question_step"] == 1, "До подтверждения шаг не должен продвигаться"
    assert "answers" not in session or "ideal" not in session["answers"][-1], (
        "До подтверждения ответ не должен попадать в answers"
    )
    assert "Уверен" in vk.last_message
    assert "Пунктуальность" in vk.last_message


def test_stress_search_question1_confirmation_yes_advances():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "Пунктуальность")

    ex.handle_message(UID, "➡️ Продолжить")
    session = ex.user_sessions[UID]
    assert session["question_step"] == 2
    assert session["answers"][-1]["ideal"] == "Пунктуальность"
    assert "_confirm_ideal" not in session
    assert "Вопрос 2/4" in vk.last_message


def test_stress_search_question1_can_retype_before_continuing():
    """На экране подтверждения не нужна отдельная кнопка «Нет» — если
    передумал, можно просто написать другой вариант ещё раз. Все написанные
    варианты видны на экране, пока не нажата «Продолжить» (по просьбе
    пользователя: должен видеть всё, что написал в моменте); «Продолжить»
    фиксирует именно последний вариант."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "Плохой вариант")

    ex.handle_message(UID, "Пунктуальность")  # передумал, без кнопки "Нет"
    session = ex.user_sessions[UID]
    assert session["question_step"] == 1, "Всё ещё на подтверждении, шаг не продвинулся"
    assert session.get("_pending_ideal") == "Пунктуальность"
    assert session.get("_pending_ideal_variants") == ["Плохой вариант", "Пунктуальность"]
    assert "Пунктуальность" in vk.last_message
    assert "Плохой вариант" in vk.last_message, "Все попытки должны быть видны, пока не нажата «Продолжить»"

    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["answers"][-1]["ideal"] == "Пунктуальность"
    assert "_pending_ideal_variants" not in ex.user_sessions[UID], "Черновик вариантов должен очищаться после подтверждения"


def test_stress_search_multiple_ideal_variants_stay_visible_before_percent_split():
    """Если пользователь на экране подтверждения написал НЕСКОЛЬКО разных
    вариантов «как должно быть» (переписывал подряд), все они должны
    остаться видны в 'ideal_variants' (последний уходит в 'ideal'), а
    дальше разбор идёт по каждому отдельно (см. следующий тест)."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Шутят надо мной 10")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "надо мной не шутят")
    ex.handle_message(UID, "шутят когда я сам захочу")
    ex.handle_message(UID, "понимают моё настроение")
    ex.handle_message(UID, "➡️ Продолжить")  # фиксирует все 3 варианта

    session = ex.user_sessions[UID]
    current_answer = session["answers"][-1]
    assert current_answer["ideal"] == "понимают моё настроение", "Последний вариант — тот, что уходит в 'ideal'"
    assert current_answer["ideal_variants"] == [
        "надо мной не шутят", "шутят когда я сам захочу", "понимают моё настроение",
    ]
    assert session["question_step"] == 2
    # Экран Вопроса 2/4 сразу спрашивает процент по ПЕРВОМУ варианту
    # отдельно (см. следующий тест) — но все варианты видны в блоке "Твои
    # ответы" на этом экране, без явного "вариант N/M" (по просьбе
    # пользователя убрано — единственный вариант без процента и есть
    # текущий).
    assert "надо мной не шутят" in vk.last_message
    assert "шутят когда я сам захочу" in vk.last_message
    assert "понимают моё настроение" in vk.last_message
    assert "убеждения о том, каким должен быть мир" in vk.last_message


def test_stress_search_multiple_ideal_variants_percent_and_why_asked_per_variant():
    """По просьбе пользователя: если вариантов «как должно быть» несколько,
    для КАЖДОГО варианта подряд спрашиваются процент реальности И «почему»
    (сразу друг за другом, пока процент не забылся) — а уже потом переход
    к следующему варианту, а не сначала все проценты, потом все «почему».
    Всё доходит до result_data (для наблюдателя и статистики на сайте)."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Шутят надо мной 10")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "надо мной не шутят")
    ex.handle_message(UID, "шутят когда я сам захочу")
    ex.handle_message(UID, "понимают моё настроение")
    ex.handle_message(UID, "➡️ Продолжить")

    # Вариант 1: процент, сразу за ним «почему» — про тот же вариант
    ex.handle_message(UID, "60")  # % для "надо мной не шутят"
    assert "вариант 1/3" in vk.last_message.lower()
    assert "60%" in vk.last_message
    assert ex.user_sessions[UID]["question_step"] == 2, "Ещё внутри цикла по вариантам"

    ex.handle_message(UID, "Почему1")  # почему для варианта 1 -> переходим к варианту 2

    # Вариант 2: процент, потом «почему»
    assert "шутят когда я сам захочу" in vk.last_message
    session = ex.user_sessions[UID]
    current_answer = session["answers"][-1]
    assert current_answer["ideal_details"][0] == {
        "text": "надо мной не шутят", "percent": 60, "why": "Почему1",
    }, "Вариант 1 должен быть полностью разобран (и процент, и почему) до перехода к варианту 2"

    ex.handle_message(UID, "70")  # % для "шутят когда я сам захочу"
    assert "вариант 2/3" in vk.last_message.lower()
    assert "70%" in vk.last_message
    ex.handle_message(UID, "Почему2")  # почему для варианта 2 -> переходим к варианту 3

    # Вариант 3: процент, потом «почему»
    assert "понимают моё настроение" in vk.last_message
    ex.handle_message(UID, "80")  # % для "понимают моё настроение"
    assert "вариант 3/3" in vk.last_message.lower()
    assert "80%" in vk.last_message
    ex.handle_message(UID, "Почему3")  # почему для варианта 3 -> все разобраны, Вопрос 4/4

    session = ex.user_sessions[UID]
    current_answer = session["answers"][-1]
    assert session["question_step"] == 4, "После разбора всех вариантов — переход к Вопросу 4/4"
    assert "_variant_idx" not in current_answer, "Служебный курсор не должен оставаться в записи"
    assert "_variant_phase" not in current_answer, "Служебный курсор не должен оставаться в записи"
    assert current_answer["ideal_details"] == [
        {"text": "надо мной не шутят", "percent": 60, "why": "Почему1"},
        {"text": "шутят когда я сам захочу", "percent": 70, "why": "Почему2"},
        {"text": "понимают моё настроение", "percent": 80, "why": "Почему3"},
    ]
    assert current_answer["percent"] == 70, "Общий процент — среднее по всем вариантам"
    assert "Вопрос 4/4" in vk.last_message

    ex.handle_message(UID, "Рефлексия")
    # Шаг 5 — связный разбор должен показать разбор по каждому варианту.
    assert "надо мной не шутят" in vk.last_message
    assert "Почему1" in vk.last_message
    assert "шутят когда я сам захочу" in vk.last_message
    assert "Почему2" in vk.last_message
    assert "понимают моё настроение" in vk.last_message
    assert "Почему3" in vk.last_message

    ex.handle_message(UID, "4")  # новая оценка -> упражнение завершается (1 образ)

    assert UID not in ex.user_sessions
    result = api.results[0]["result_data"]
    analysis = result["analysis"][0]
    assert analysis["ideal"] == "понимают моё настроение"
    assert analysis["percent"] == 70
    assert analysis["ideal_details"] == [
        {"text": "надо мной не шутят", "percent": 60, "why": "Почему1"},
        {"text": "шутят когда я сам захочу", "percent": 70, "why": "Почему2"},
        {"text": "понимают моё настроение", "percent": 80, "why": "Почему3"},
    ]
    assert "_variant_idx" not in analysis


def test_stress_search_multi_variant_loop_survives_restart_mid_why():
    """Обрыв процесса ровно посреди цикла по вариантам (процент варианта 2
    уже дан, «почему» варианта 2 — ещё нет) не должен сбить ни текущий
    вариант, ни фазу (процент/почему) — resume должен продолжить ровно
    с того места."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Шутят надо мной 10")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "надо мной не шутят")
    ex.handle_message(UID, "шутят когда я сам захочу")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "60")       # % вариант 1 -> почему вариант 1
    ex.handle_message(UID, "Почему1")  # почему вариант 1 -> % вариант 2
    ex.handle_message(UID, "70")       # % вариант 2 -> ждём почему варианта 2

    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    ex2.handle_message(UID, "Продолжить ✅")

    assert "вариант 2/2" in vk.last_message.lower()
    assert "70%" in vk.last_message

    ex2.handle_message(UID, "Почему2")
    session = ex2.user_sessions[UID]
    current_answer = session["answers"][-1]
    assert session["question_step"] == 4
    assert current_answer["ideal_details"] == [
        {"text": "надо мной не шутят", "percent": 60, "why": "Почему1"},
        {"text": "шутят когда я сам захочу", "percent": 70, "why": "Почему2"},
    ]


# ---------------------------------------------------------------------------
# Кнопка «✏️ Изменить пункт» на экране Вопроса 1/4 — правка текста/оценки
# самого образа, если он неточно сформулирован, без выхода из разбора.
# ---------------------------------------------------------------------------

def test_stress_search_edit_item_button_appears_on_question1():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    assert "✏️ Изменить пункт" in vk.last_buttons
    assert "Вопрос 1/4" in vk.last_message


def test_stress_search_edit_item_updates_text_and_rate_everywhere():
    """Правка пункта на экране Вопроса 1/4 должна обновить и сам образ
    (items), и current_item, и уже созданную запись в answers — иначе
    итоговая сводка и результат для наблюдателя не совпадут с картой."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")  # -> Вопрос 1/4 по «Опоздание»

    ex.handle_message(UID, "✏️ Изменить пункт")
    assert ex.user_sessions[UID]["_editing_item"] is True
    assert "Опоздание" in vk.last_message

    ex.handle_message(UID, "Опоздание на встречу 9")

    session = ex.user_sessions[UID]
    assert "_editing_item" not in session
    assert session["items"][0] == {"text": "Опоздание на встречу", "rate": 9}
    assert session["current_item"] == {"text": "Опоздание на встречу", "rate": 9}
    assert session["answers"][-1]["text"] == "Опоздание на встречу"
    assert session["answers"][-1]["rate"] == 9
    assert "Пункт изменён" in vk.last_message
    assert "Опоздание на встречу" in vk.last_message
    assert "9/10" in vk.last_message
    assert "✏️ Изменить пункт" in vk.last_buttons, "После правки снова показывается Вопрос 1/4"


def test_stress_search_edit_item_rejects_bad_format():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "✏️ Изменить пункт")
    ex.handle_message(UID, "просто текст без оценки")

    session = ex.user_sessions[UID]
    assert session["_editing_item"] is True, "Должен остаться в режиме редактирования"
    assert session["items"][0] == {"text": "Опоздание", "rate": 8}, "Исходный пункт не должен измениться"
    assert "не разобрал формат" in vk.last_message.lower()


def test_stress_search_edit_item_rejects_duplicate_of_another_item():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "Шум 5")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")  # -> Вопрос 1/4 по «Опоздание» (index 0)

    ex.handle_message(UID, "✏️ Изменить пункт")
    ex.handle_message(UID, "шум 6")  # совпадает с другим уже записанным пунктом

    session = ex.user_sessions[UID]
    assert session["_editing_item"] is True
    assert session["items"][0] == {"text": "Опоздание", "rate": 8}, "Правка не должна была примениться"
    assert "уже есть в твоей карте" in vk.last_message.lower()


def test_stress_search_edit_item_reflected_in_finish_result_data():
    """Правка пункта должна дойти до result_data, сохраняемого через
    save_result — это тот же JSON, который читает статистика на сайте."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "✏️ Изменить пункт")
    ex.handle_message(UID, "Опоздание на встречу 9")

    _stress_do_item(ex, "Пунктуальность", 60, "Почему", "Рефлексия", 4)

    assert UID not in ex.user_sessions
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["items"][0] == {"text": "Опоздание на встречу", "rate": 9}
    assert result["analysis"][0]["text"] == "Опоздание на встречу"
    assert result["analysis"][0]["rate"] == 9
    assert result["analysis"][0]["ideal"] == "Пунктуальность"


# ---------------------------------------------------------------------------
# Устойчивость к обрыву сессии (эмуляция рестарта процесса — новый
# экземпляр упражнения с тем же api, память self.user_sessions потеряна)
# ровно на «неудобных» экранах: подтверждение Вопроса 1 и пауза между
# образами. Найдено адверсариальным ревью — раньше в этих двух случаях
# resume либо терял написанные варианты, либо перескакивал через экран.
# ---------------------------------------------------------------------------

def test_stress_search_confirm_ideal_draft_survives_restart():
    """Если процесс бота перезапустится ровно на экране подтверждения
    Вопроса 1 (варианты ещё не зафиксированы «➡️ Продолжить») — написанные
    варианты не должны потеряться при возврате."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "Плохой вариант")
    ex.handle_message(UID, "Пунктуальность")  # 2 варианта в черновике, не подтверждено

    # эмулируем рестарт процесса: новый экземпляр, тот же api (= тот же
    # сохранённый прогресс), но session-память ex.user_sessions недоступна
    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    ex2.handle_message(UID, "Продолжить ✅")  # подтверждаем resume-промпт

    session = ex2.user_sessions[UID]
    assert session.get("_confirm_ideal") is True
    assert session.get("_pending_ideal_variants") == ["Плохой вариант", "Пунктуальность"]
    assert "Пунктуальность" in vk.last_message
    assert "Плохой вариант" in vk.last_message, "Оба варианта должны быть видны после восстановления"


def test_stress_search_between_items_pause_survives_restart():
    """Если процесс перезапустится ровно на паузе между образами (после
    поздравления с новой оценкой) — resume должен снова показать эту
    паузу с кнопками, а не сразу перескочить к следующему образу."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "Семья 5")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    _stress_do_item(ex, "Идеал 1", 80, "Почему 1", "Рефлексия 1", 5)

    assert ex.user_sessions[UID]["_between_items"] is True

    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    ex2.handle_message(UID, "Продолжить ✅")

    session = ex2.user_sessions[UID]
    assert session.get("_between_items") is True
    assert len(session["answers"]) == 1, "Новая запись для образа 2 ещё не должна была создаться"
    assert "к следующему образу" in vk.last_message


def test_stress_search_resume_question2_single_variant_shows_forecast_hint():
    """Косметическая нестыковка, найденная ревью: экран Вопроса 2/4 при
    обычном показе объясняет, что процент — это прогноз пользователя;
    при resume это пояснение должно быть тем же, а не короче."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Опоздание 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "Пунктуальность")
    ex.handle_message(UID, "➡️ Продолжить")  # -> Вопрос 2/4

    ex2, vk2, _ = make(StressSearchExercise)
    ex2.vk, ex2.api = ex.vk, api
    ex2.start(UID)
    ex2.handle_message(UID, "Продолжить ✅")

    assert "Это твой прогноз" in vk.last_message


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

        if name == "diary":
            # Первый же ответ ("Сон") уже сам закрыл сессию на границе блока
            # Утро -> День (см. _show_block_boundary) — вести себя как
            # обычное "Сохранить и выйти" не нужно, сессия и так закрыта, а
            # прогресс уже сохранён.
            assert UID not in ex.user_sessions, f"{name}: после ответа на 'Сон' сессия уже должна быть закрыта"
        else:
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
    ex.handle_message(UID, "Гулял по парку")     # dream -> блок "День" ждёт
    _diary_resume(ex)                             # заглянули через час
    ex.handle_message(UID, "Спокойное")           # mood
    ex.handle_message(UID, "Лёгкость в теле")     # body
    ex.handle_message(UID, "Мысли о работе")      # thoughts
    ex.handle_message(UID, "Хочу кофе")           # wants -> блок "Вечер" ждёт
    _diary_resume(ex)                             # заглянули вечером
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


def test_diary_finish_with_very_long_answers_does_not_crash_and_truncates():
    """Баг #4: dream/mood/body/differences эхались в _finish() без
    ограничения длины — с очень длинным ответом сообщение легко превышает
    ~4096-символьный лимит VK. Упражнение должно завершиться нормально
    (сохранить результат ПОЛНОСТЬЮ, без обрезки) и показать ОБРЕЗАННОЕ
    эхо, а не упасть/зависнуть."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    long_text = "А" * 5000
    ex.handle_message(UID, long_text)       # dream -> блок "День" ждёт
    _diary_resume(ex)                        # заглянули через час
    ex.handle_message(UID, "Спокойное")     # mood
    ex.handle_message(UID, "Лёгкость")      # body
    ex.handle_message(UID, "Мысли")         # thoughts
    ex.handle_message(UID, "Хочу кофе")     # wants -> блок "Вечер" ждёт
    _diary_resume(ex)                        # заглянули вечером
    ex.handle_message(UID, long_text)       # differences -> _finish()

    assert UID not in ex.user_sessions, "Упражнение должно было завершиться, а не упасть"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    # Сохранённый результат — полный, без обрезки (обрезается только эхо)
    assert result["dream"] == long_text
    assert result["differences"] == long_text
    # А вот в сообщении-эхе длинный текст должен быть обрезан
    assert len(vk.last_message) < 4096
    assert long_text not in vk.last_message


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


def test_conscious_choice_pasted_multiline_list_splits_into_separate_items():
    """Тот же баг, что был в 'Мои роли' (см.
    test_my_roles_pasted_multiline_list_splits_into_separate_roles):
    пользователь вставляет сразу весь список одним сообщением, каждый
    пункт на своей строке — раньше это сохранялось как ОДИН пункт ('1/20')
    вместо того, чтобы разложиться на отдельные."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)

    pasted = (
        "Должен работать\n"
        "Должен зарабатывать\n"
        "Должен быть ответственным\n"
        "Должен заботиться о близких\n"
        "Должен быть сильным"
    )
    ex.handle_message(UID, pasted)

    items = ex.user_sessions[UID]["must_items"]
    assert len(items) == 5, "Каждая строка списка должна была стать отдельным пунктом"
    assert items[0] == "Должен работать"
    assert items[4] == "Должен быть сильным"
    assert "(1/20)" not in vk.last_message
    assert "Добавлено пунктов: 5" in vk.last_message
    assert "Всего: 5/20" in vk.last_message


def test_conscious_choice_step2_asks_for_own_affirmation_before_the_question():
    """Шаг 2 разбит на два экрана: сначала пример фразы на ДРУГОМ пункте
    (не на том, что написал пользователь — иначе фразу можно было бы просто
    списать) с просьбой сформулировать свою по образцу, и только следующим
    сообщением показывается сам вопрос «Кто отнял...», уже со СВОИМ
    вариантом фразы пользователя."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Зарабатывать деньги")
    ex.handle_message(UID, "➡️ Продолжить")  # -> step 2, экран примера

    assert ex.user_sessions[UID]["_awaiting_own_affirmation"] is True
    assert "Зарабатывать деньги" in vk.last_message, "Сам пункт для контекста показать нужно"
    assert "Я имею право не хотеть «Зарабатывать деньги»" not in vk.last_message, (
        "Пример не должен быть один в один с тем, что нужно написать — иначе его можно списать"
    )
    assert "Убирать за всеми" in vk.last_message, "Пример должен быть на другом, нейтральном пункте"
    assert "Сформулируй сам" in vk.last_message
    assert "Кто отнял" not in vk.last_message, "Вопрос не должен показываться на экране примера"

    ex.handle_message(UID, "Я не обязан зарабатывать больше, чем мне нужно")
    assert "_awaiting_own_affirmation" not in ex.user_sessions[UID]
    assert ex.user_sessions[UID]["right_phrase"] == "Я не обязан зарабатывать больше, чем мне нужно"
    assert "Я не обязан зарабатывать больше, чем мне нужно" in vk.last_message
    assert "Кто отнял" in vk.last_message


def test_conscious_choice_step2_skip_own_affirmation_uses_example_as_is():
    """На экране примера можно просто нажать «Продолжить», не формулируя
    свой вариант — тогда используется фраза из примера как есть."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Зарабатывать деньги")
    ex.handle_message(UID, "➡️ Продолжить")  # -> step 2, экран примера
    ex.handle_message(UID, "➡️ Продолжить")  # пропускаем свой вариант

    assert "_awaiting_own_affirmation" not in ex.user_sessions[UID]
    assert "right_phrase" not in ex.user_sessions[UID], "Свой вариант не написан — фраза не сохраняется отдельно"
    assert "Я имею право не хотеть «Зарабатывать деньги»" in vk.last_message
    assert "Кто отнял" in vk.last_message


def test_conscious_choice_full_flow_to_finish():
    """Шаг 4 ("Анализ выбора") показывает сразу и сам выбор, и просьбу
    написать минусы одним сообщением (раньше это были два отдельных экрана
    с "Продолжить" между ними без какого-либо ввода). Шаг 5 ("Альтернативы")
    объединён с "другими минусами" по тому же принципу. На всех четырёх
    экранах "Не хочу"/"Хочу" (choice_minus/choice_plus/alt_minus/alt_plus)
    можно писать сколько угодно раз — пункты копятся, а шаг двигает только
    явное "Продолжить" (тот же приём, что и на шаге 1 — сбор must_items)."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    assert ex.user_sessions[UID]["step"] == 1

    ex.handle_message(UID, "Кормить детей")        # добавлен must-пункт
    ex.handle_message(UID, "➡️ Продолжить")        # -> step 2 (current_must = "Кормить детей")
    assert ex.user_sessions[UID]["step"] == 2
    assert ex.user_sessions[UID]["_awaiting_own_affirmation"] is True

    ex.handle_message(UID, "Имею право отдохнуть")  # свой вариант фразы -> экран вопроса
    assert ex.user_sessions[UID]["step"] == 2
    assert "_awaiting_own_affirmation" not in ex.user_sessions[UID]
    assert ex.user_sessions[UID]["right_phrase"] == "Имею право отдохнуть"

    ex.handle_message(UID, "Никто не отнял")        # who_took -> step 3
    assert ex.user_sessions[UID]["step"] == 3

    ex.handle_message(UID, "Я сам")                 # who_greater -> step 4 (выбор + минусы одним сообщением)
    assert ex.user_sessions[UID]["step"] == 4
    assert "Я выбираю" in vk.last_message
    assert "Не хочу" in vk.last_message

    ex.handle_message(UID, "устану")                # добавлен минус-пункт, шаг НЕ двигается сам
    assert ex.user_sessions[UID]["step"] == 4
    assert ex.user_sessions[UID]["choice_minus_items"] == ["устану"]
    assert "Уже добавил(а)" in vk.last_message

    ex.handle_message(UID, "расстроюсь")            # можно дописать ещё пункт тем же образом
    assert ex.user_sessions[UID]["choice_minus_items"] == ["устану", "расстроюсь"]

    ex.handle_message(UID, "➡️ Продолжить")        # только явным "Продолжить" -> step 6 (плюсы)
    assert ex.user_sessions[UID]["step"] == 6
    assert "Хочу" in vk.last_message

    ex.handle_message(UID, "увижу улыбку")          # добавлен плюс-пункт, шаг НЕ двигается сам
    assert ex.user_sessions[UID]["step"] == 6
    assert ex.user_sessions[UID]["choice_plus_items"] == ["увижу улыбку"]

    ex.handle_message(UID, "➡️ Продолжить")        # -> step 7 (Альтернативы + другие минусы одним сообщением)
    assert ex.user_sessions[UID]["step"] == 7
    assert "устану" in ex.user_sessions[UID]["choice_analysis"]
    assert "расстроюсь" in ex.user_sessions[UID]["choice_analysis"]
    assert "увижу улыбку" in ex.user_sessions[UID]["choice_analysis"]
    assert "Альтернативы" in vk.last_message
    assert "Не хочу" in vk.last_message

    ex.handle_message(UID, "➡️ Продолжить")        # пропускаем другие минусы -> step 9 (другие плюсы)
    assert ex.user_sessions[UID]["step"] == 9

    ex.handle_message(UID, "энергия")               # добавлен плюс-пункт, шаг НЕ двигается сам
    assert ex.user_sessions[UID]["step"] == 9
    ex.handle_message(UID, "➡️ Продолжить")        # только явным "Продолжить" -> единственный пункт разобран -> _finish()

    assert UID not in ex.user_sessions, "Упражнение должно завершиться после шага 9"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["must_items"] == ["Кормить детей"]
    assert len(result["analysis"]) == 1
    entry = result["analysis"][0]
    assert entry["must"] == "Кормить детей"
    assert entry["right_phrase"] == "Имею право отдохнуть"
    assert entry["who_took"] == "Никто не отнял"
    assert entry["who_greater"] == "Я сам"
    assert "устану" in entry["choice_analysis"]
    assert "энергия" in entry["alternatives"]
    assert "—" in entry["alternatives"], "Пропущенные минусы должны отметиться прочерком"


def test_conscious_choice_choice_minus_accepts_multiline_list_in_one_message():
    """Экраны "Не хочу"/"Хочу" заявляют "по одному или сразу списком" — как
    и на шаге 1 (сбор must_items), вставленный одним сообщением список
    (каждый пункт с новой строки или через ";") должен разложиться на
    отдельные пункты, а не превратиться в один длинный пункт целиком."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Имею право")
    ex.handle_message(UID, "Никто не отнял")
    ex.handle_message(UID, "Я сам")            # -> step 4

    ex.handle_message(UID, "устану\nрасстроюсь; будет тяжело")
    assert ex.user_sessions[UID]["step"] == 4, "Список пунктов не должен сам продвигать шаг"
    assert ex.user_sessions[UID]["choice_minus_items"] == ["устану", "расстроюсь", "будет тяжело"]


def test_conscious_choice_item_collection_reprompts_when_nothing_parsed():
    """Если из сообщения не удалось выделить ни одного пункта (пустые
    разделители/мусор) — переспрашиваем, а не молча добавляем пустой
    пункт и не продвигаем шаг."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Имею право")
    ex.handle_message(UID, "Никто не отнял")
    ex.handle_message(UID, "Я сам")            # -> step 4

    ex.handle_message(UID, " ; ; ")
    assert ex.user_sessions[UID]["step"] == 4
    assert "choice_minus_items" not in ex.user_sessions[UID] or ex.user_sessions[UID]["choice_minus_items"] == []
    assert "не нашёл" in vk.last_message.lower()


def test_conscious_choice_skip_all_minus_plus_via_continue():
    """Все экраны минусов/плюсов (шаги 4, 6, 7 — бывшие 5 и 8 теперь
    показываются вместе с 4 и 7 соответственно, см. _show_choice_minus/
    _show_alt_minus) можно пропустить одной кнопкой «Продолжить», не
    отвечая ни разу — упражнение всё равно доходит до конца."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")   # -> step 2 (экран примера фразы)
    ex.handle_message(UID, "➡️ Продолжить")   # пропускаем свой вариант -> экран вопроса
    ex.handle_message(UID, "Никто не отнял")   # -> step 3
    ex.handle_message(UID, "Я сам")            # -> step 4

    for _ in range(4):  # шаги 4,6,7,9 — каждый пропускается "Продолжить"
        ex.handle_message(UID, "➡️ Продолжить")

    assert UID not in ex.user_sessions, "Упражнение должно завершиться, даже если все минусы/плюсы пропущены"
    result = api.results[-1]["result_data"]
    entry = result["analysis"][0]
    assert entry["choice_analysis"] == "Минусы: —, Плюсы: —"
    assert entry["alternatives"] == "Минусы: —, Плюсы: —"


def test_conscious_choice_analyzes_every_collected_item_not_just_the_last():
    """Правка (редизайн по типу stress_search): раньше глубокий разбор
    (шаги 2-9) проходил только для ПОСЛЕДНЕГО записанного пункта — остальные
    пункты сохранялись в must_items, но полностью выпадали из итогового
    анализа. Теперь цикл разбора проходит по КАЖДОМУ пункту по очереди."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "Ходить на работу")
    ex.handle_message(UID, "➡️ Продолжить")  # -> начало разбора, пункт 1/2

    session = ex.user_sessions[UID]
    assert session["step"] == 2
    assert session["analysis_index"] == 0
    assert session["current_must"] == "Кормить детей"
    assert session["_awaiting_own_affirmation"] is True
    assert "1/2" in vk.last_message

    # разбираем пункт 1 полностью (шаги 2-9)
    ex.handle_message(UID, "Имею право 1")     # свой вариант фразы -> экран вопроса
    ex.handle_message(UID, "Никто не отнял")   # -> 3
    ex.handle_message(UID, "Я сам")            # -> 4 (выбор + минусы одним сообщением)
    ex.handle_message(UID, "устану 1")         # добавлен минус-пункт, шаг остаётся 4
    ex.handle_message(UID, "➡️ Продолжить")    # -> 6 (плюсы)
    ex.handle_message(UID, "улыбка 1")         # добавлен плюс-пункт, шаг остаётся 6
    ex.handle_message(UID, "➡️ Продолжить")    # -> 7 (Альтернативы + другие минусы)
    ex.handle_message(UID, "➡️ Продолжить")    # -> 9 (другие плюсы)

    # ещё не должно было завершиться — есть второй пункт
    assert UID in ex.user_sessions
    ex.handle_message(UID, "энергия 1")        # добавлен плюс-пункт, шаг остаётся 9
    ex.handle_message(UID, "➡️ Продолжить")    # завершает пункт 1 -> должен начаться пункт 2

    session = ex.user_sessions[UID]
    assert UID in ex.user_sessions, "Упражнение не должно было завершиться — есть ещё пункт 2"
    assert session["step"] == 2, "Должен был начаться разбор пункта 2 с шага 2"
    assert session["analysis_index"] == 1
    assert session["current_must"] == "Ходить на работу"
    assert session["_awaiting_own_affirmation"] is True, "Для нового пункта снова нужно спросить свой вариант фразы"
    assert "2/2" in vk.last_message
    assert len(session["analysis_results"]) == 1, "Разбор пункта 1 должен был сохраниться промежуточно"
    # состояние предыдущего пункта не должно протекать в разбор нового
    assert "current_answer" not in session
    assert "right_phrase" not in session

    # разбираем пункт 2
    ex.handle_message(UID, "Имею право 2")     # свой вариант фразы -> экран вопроса
    ex.handle_message(UID, "Родители")         # -> 3
    ex.handle_message(UID, "Никто")            # -> 4 (выбор + минусы одним сообщением)
    ex.handle_message(UID, "➡️ Продолжить")    # -> 6 (пропуск минусов)
    ex.handle_message(UID, "➡️ Продолжить")    # -> 7 (пропуск плюсов; Альтернативы + другие минусы)
    ex.handle_message(UID, "➡️ Продолжить")    # -> 9 (пропуск других минусов)
    ex.handle_message(UID, "энергия 2")        # добавлен плюс-пункт, шаг остаётся 9
    ex.handle_message(UID, "➡️ Продолжить")    # завершает пункт 2 -> оба разобраны -> _finish()

    assert UID not in ex.user_sessions, "После разбора ВСЕХ пунктов упражнение должно завершиться"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["must_items"] == ["Кормить детей", "Ходить на работу"]
    assert len(result["analysis"]) == 2, "Должны быть разобраны ОБА пункта, а не только последний"

    a1, a2 = result["analysis"]
    assert a1["must"] == "Кормить детей"
    assert a1["right_phrase"] == "Имею право 1"
    assert a1["who_took"] == "Никто не отнял"
    assert a1["who_greater"] == "Я сам"
    assert "устану 1" in a1["choice_analysis"]
    assert "энергия 1" in a1["alternatives"]

    assert a2["must"] == "Ходить на работу"
    assert a2["right_phrase"] == "Имею право 2"
    assert a2["who_took"] == "Родители"
    assert a2["who_greater"] == "Никто"
    assert a2["choice_analysis"] == "Минусы: —, Плюсы: —"
    assert "энергия 2" in a2["alternatives"]


def test_conscious_choice_save_and_restart_with_no_items_does_not_save_empty_result():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 0
    assert "нечего сохранять" in vk.sent[-2]["message"].lower()
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["step"] == 1


def test_conscious_choice_save_and_restart_failure_keeps_progress_instead_of_wiping_it():
    """Дыра: раньше _handle_save_and_start_over вызывал _finish() и следом
    БЕЗУСЛОВНО _handle_start_over() — даже если save_result() падал.
    _finish() уже сохранял черновик прогресса, но _handle_start_over() тут
    же удалял его и открывал пустую сессию, теряя весь разбор."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["must_items"] == ["Кормить детей"]
    assert api.progress_store.get((UID, "conscious_choice"), {}).get("must_items") == ["Кормить детей"]

    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["must_items"] == []


def test_my_roles_save_and_restart_failure_keeps_roles_instead_of_wiping_them():
    """Тот же баг, что уже был найден и исправлен в conscious_choice/diary/
    stop_technique/happiness_list: my_roles._handle_save_and_start_over()
    вызывал _finish() и следом БЕЗУСЛОВНО _handle_start_over(), не проверяя
    результат save_result() — при сбое сохранения _finish() уже сохранял
    записанные роли как черновик прогресса, но _handle_start_over() тут же
    удалял этот черновик и открывал пустую сессию, теряя все роли насовсем,
    хотя пользователю только что сказали "ничего не потеряно"."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Повар")  # social_roles += 1

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["social_roles"] == ["Повар"]
    assert api.progress_store.get((UID, "my_roles"), {}).get("social_roles") == ["Повар"]

    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["social_roles"] == []


def test_stress_search_save_and_restart_failure_keeps_items_instead_of_wiping_them():
    """Тот же баг: stress_search._handle_save_and_start_over() вызывал
    _finish_exercise() и следом БЕЗУСЛОВНО _handle_start_over(), не проверяя
    результат — при сбое сохранения _finish_exercise() уже сохранял
    записанную карту стресса как черновик прогресса, но _handle_start_over()
    тут же удалял этот черновик и открывал пустую сессию, теряя всю карту
    насовсем. Воспроизводится только когда набрано достаточно образов для
    досрочного завершения (MIN_ITEMS_TO_FINISH_EARLY) — иначе
    _handle_save_and_start_over вообще не вызывает _finish_exercise."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 5")

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    assert UID in ex.user_sessions
    assert len(ex.user_sessions[UID]["items"]) == 10

    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["items"] == []


def test_conscious_choice_typing_never_auto_advances_only_continue_does():
    """После слияния 4+5 и 7+8 (см. _show_choice_minus/_show_alt_minus) в
    упражнении больше нет "чистых" экранов-подтверждений без поля ввода —
    но и обратного тоже нет: печатать текст на экранах "Не хочу"/"Хочу"
    (choice_minus/choice_plus/alt_minus/alt_plus) добавляет пункт (см.
    _collect_items) и ОСТАЁТСЯ на том же шаге — двигает шаг дальше только
    явное «Продолжить», ровно как на шаге 1 со сбором must_items."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Имею право")       # свой вариант фразы -> экран вопроса
    ex.handle_message(UID, "Никто не отнял")
    ex.handle_message(UID, "Я сам")            # -> step 4 (выбор + минусы одним сообщением)

    ex.handle_message(UID, "случайный текст")  # добавлен пункт, шаг НЕ меняется
    assert ex.user_sessions[UID]["step"] == 4
    assert ex.user_sessions[UID]["choice_minus_items"] == ["случайный текст"]

    ex.handle_message(UID, "➡️ Продолжить")    # -> 6
    ex.handle_message(UID, "улыбка")           # добавлен пункт, шаг НЕ меняется
    assert ex.user_sessions[UID]["step"] == 6
    assert ex.user_sessions[UID]["choice_plus_items"] == ["улыбка"]

    ex.handle_message(UID, "➡️ Продолжить")    # -> 7 (Альтернативы + другие минусы)
    ex.handle_message(UID, "случайный текст")  # добавлен пункт, шаг НЕ меняется
    assert ex.user_sessions[UID]["step"] == 7
    assert ex.user_sessions[UID]["alt_minus_items"] == ["случайный текст"]


def test_my_roles_preanalyze_confirm_shows_counts_with_empty_marker():
    """Экран перед стартом разбора должен показывать счёт по каждому
    разделу с целью (N/target), а пустой раздел — с заметным ⚠️, чтобы
    не потерялся среди чисел (запрошено пользователем: 'индикатор, если
    не хватает ролей')."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")   # social(1) -> сразу interpersonal
    ex.handle_message(UID, "➡️ Продолжить")   # interpersonal(0) -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")    # -> intrapersonal
    ex.handle_message(UID, "Смелый")
    ex.handle_message(UID, "➡️ Продолжить")   # -> экран подтверждения перед разбором

    msg = vk.last_message
    assert "Социальных: 1/20" in msg
    assert "Межличностных: 0/20 ⚠️ пусто" in msg
    assert "Внутриличностных: 1/10" in msg
    assert "⚠️ пусто" not in msg.split("Межличностных")[0], "Непустые разделы не должны помечаться"


def test_my_roles_preanalyze_confirm_return_to_phase_and_back():
    """«Нет, буду писать» должно дать выбрать раздел, вернуть туда, и по
    следующему «Продолжить» из этого раздела — снова показать экран
    подтверждения (со свежими цифрами), а не покатиться дальше по обычной
    цепочке разделов."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Друг для Саши")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Смелый")
    ex.handle_message(UID, "➡️ Продолжить")   # -> экран подтверждения

    ex.handle_message(UID, "✏️ Нет, буду писать")
    assert vk.last_buttons == ["1. Социальные", "2. Межличностные", "3. Внутриличностные"]

    ex.handle_message(UID, "1. Социальные")
    session = ex.user_sessions[UID]
    assert session["phase"] == "social"
    assert session["_reviewing_phase"] is True
    assert "Часть 1: Социальные роли" in vk.last_message

    ex.handle_message(UID, "Ещё роль")
    ex.handle_message(UID, "➡️ Продолжить")   # должно вернуть на экран подтверждения, а не в interpersonal

    assert ex.user_sessions[UID]["phase"] == "social", "Не должно было провалиться в обычную цепочку разделов"
    assert "РОЛИ СОБРАНЫ" in vk.last_message
    assert "Социальных: 2/20" in vk.last_message
    assert "_reviewing_phase" not in ex.user_sessions[UID]

    ex.handle_message(UID, "✅ Да, дальше")
    assert ex.user_sessions[UID]["phase"] == "analyze"


def test_my_roles_preanalyze_confirm_transient_flags_do_not_survive_save_and_exit():
    """Как и '_confirm_empty_phase', новые флаги '_pre_analyze_confirm' и
    '_choosing_return_phase' — транзитные, не должны буквально сохраниться
    через 'Сохранить и выйти'."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Продавец")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Друг для Саши")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Смелый")
    ex.handle_message(UID, "➡️ Продолжить")   # -> экран подтверждения, _pre_analyze_confirm=True
    ex.handle_message(UID, "💾 Сохранить и выйти")

    saved = api.progress_store.get((UID, "my_roles"))
    assert saved is not None
    assert "_pre_analyze_confirm" not in saved
    assert "_choosing_return_phase" not in saved
    assert "_reviewing_phase" not in saved


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
    ex.handle_message(UID, "➡️ Продолжить")        # -> экран подтверждения перед разбором
    ex.handle_message(UID, "✅ Да, дальше")         # -> analyze, роль 1 ("Продавец"), шаг 1

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

    # новый день — роль 2 (Друг для Саши). Правка: первое сообщение после
    # смены дня заново показывает роль 2 (а не тратится как псевдо-ответ на
    # вопрос, который ещё ни разу не показывался) — реальные ответы уходят
    # только следующими двумя сообщениями.
    ex._today_str = lambda: "2026-08-30"
    ex.handle_message(UID, "проснулся")
    assert ex.user_sessions[UID]["analysis_step"] == 1
    assert "идеально" in vk.last_message.lower()
    ex.handle_message(UID, "дружба")
    ex.handle_message(UID, "ссора")
    assert ex.user_sessions[UID]["analysis_index"] == 2

    # тот же день — роль 3 заблокирована
    ex.handle_message(UID, "смелость")
    assert ex.user_sessions[UID]["analysis_index"] == 2

    # ещё один новый день — роль 3 (Смелый), последняя, упражнение завершается
    ex._today_str = lambda: "2026-08-31"
    ex.handle_message(UID, "проснулся")
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
    ex.handle_message(UID, "➡️ Продолжить")   # -> экран подтверждения перед разбором
    ex.handle_message(UID, "✅ Да, дальше")    # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "идеально 1")
    ex.handle_message(UID, "ужасно 1")        # роль 1 разобрана сегодня

    assert ex.user_sessions[UID]["analysis_index"] == 1
    assert "снижает" in vk.last_message.lower(), "Должно быть предупреждение об эффективности"
    assert vk.last_buttons == ["⚠️ Всё равно продолжить", "💾 Сохранить и выйти"]

    ex.handle_message(UID, "⚠️ Всё равно продолжить")
    assert ex.user_sessions[UID]["analysis_step"] == 1
    assert "идеально" in vk.last_message.lower(), "После подтверждения роль 2 должна начать разбор"

    ex.handle_message(UID, "идеально 2")
    ex.handle_message(UID, "ужасно 2")        # роль 2 разобрана в переопределённом режиме

    assert ex.user_sessions[UID]["analysis_index"] == 2

    # роль 3 в тот же день — лимит снова спрашивает подтверждение, override
    # не переносится молча на все последующие роли
    assert "снижает" in vk.last_message.lower()
    ex.handle_message(UID, "идеально 3")
    assert ex.user_sessions[UID]["analysis_index"] == 2, "Без нового подтверждения роль 3 не должна начаться"


def test_my_roles_daily_limit_prompt_becomes_stale_after_midnight():
    """Если сообщение о лимите ещё висит на экране, а календарный день уже
    сменился, лимит больше не действует — но правка: раньше следующее
    сообщение (что бы в нём ни было) проглатывалось как "ответ" на вопрос
    про идеальный сценарий следующей роли, а сама роль и вопрос к ней
    пользователю ни разу не показывались. Теперь на такое сообщение бот
    заново показывает роль (сообщение-триггер не тратится как псевдо-ответ),
    и только следующий текст реально станет ответом."""
    ex, vk, api = make(MyRolesExercise)
    ex._today_str = lambda: "2026-08-31"
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль Б")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Продолжить")  # intrapersonal: 0 ролей -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")   # -> экран подтверждения перед разбором
    ex.handle_message(UID, "✅ Да, дальше")   # -> analyze, роль 1, шаг 1
    ex.handle_message(UID, "идеально 1")
    ex.handle_message(UID, "ужасно 1")
    assert ex.user_sessions[UID]["_daily_limit_prompt"] is True

    ex._today_str = lambda: "2026-09-01"  # наступил новый день
    ex.handle_message(UID, "новый идеальный ответ")
    assert "_daily_limit_prompt" not in ex.user_sessions[UID]
    assert ex.user_sessions[UID]["analysis_step"] == 1, "Роль должна была показаться заново с шага 1"
    assert "current_ideal" not in ex.user_sessions[UID], (
        "Триггерное сообщение не должно было засчитаться как ответ на вопрос"
    )
    assert "идеально" in vk.last_message.lower(), "Должен был снова показаться вопрос про идеальный сценарий"

    # А вот СЛЕДУЮЩЕЕ сообщение — уже реальный ответ на заново показанный вопрос
    ex.handle_message(UID, "настоящий идеальный ответ")
    assert ex.user_sessions[UID]["current_ideal"] == "настоящий идеальный ответ"
    assert ex.user_sessions[UID]["analysis_step"] == 2


def test_my_roles_advance_text_during_analysis_does_not_get_swallowed():
    """Правка: фаза 'analyze' ждёт только свободный текст-ответ, кнопок
    навигации там нет — но раньше global-перехват ADVANCE_TEXTS в
    handle_message срабатывал ДО диспетчера по фазам. Если ответ
    пользователя на вопрос анализа случайно совпадал по тексту с одной из
    этих кнопок (например буквально "продолжить" или "завершить"),
    сообщение уходило в _advance_phase, где для 'analyze' нет ни одной
    ветки — ответ молча терялся, бот не отвечал вообще ничем."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль Б")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "Роль В")
    ex.handle_message(UID, "➡️ Продолжить")  # -> экран подтверждения перед разбором
    ex.handle_message(UID, "✅ Да, дальше")   # -> analyze, роль 1, шаг 1

    before = len(vk.sent)
    ex.handle_message(UID, "продолжить")  # текст совпадает с ADVANCE_TEXTS
    assert len(vk.sent) == before + 1, "Сообщение не должно было потеряться без ответа"
    assert ex.user_sessions[UID]["current_ideal"] == "продолжить"
    assert ex.user_sessions[UID]["analysis_step"] == 2
    assert "ужасно" in vk.last_message.lower()


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
    ex.handle_message(UID, "✅ Да, дальше")   # -> экран подтверждения перед разбором
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


def test_my_roles_handle_analysis_out_of_range_index_finishes_instead_of_crashing():
    """Защитный тест на добавленный bounds-check: если analysis_index когда-либо
    окажется за пределами all_roles (не должно случаться при нормальной
    работе, но раньше не проверялось вообще и грозило IndexError), метод
    должен честно завершить упражнение, а не уронить обработчик."""
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "Роль А")
    ex.handle_message(UID, "➡️ Продолжить")   # -> interpersonal
    ex.handle_message(UID, "➡️ Продолжить")   # interpersonal пуст -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")    # -> intrapersonal
    ex.handle_message(UID, "➡️ Продолжить")   # intrapersonal пуст -> переспрос
    ex.handle_message(UID, "✅ Да, дальше")    # -> экран подтверждения перед разбором
    ex.handle_message(UID, "✅ Да, дальше")    # -> analyze, 1 роль всего

    session = ex.user_sessions[UID]
    session['analysis_index'] = 5  # намеренно рассинхронизировано

    ex._handle_analysis(UID, "любой текст", session)

    assert UID not in ex.user_sessions, "Должно было честно завершиться, а не упасть"
    assert len(api.results) == 1


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
    ex.handle_message(UID, "✅ Да, дальше")   # -> экран подтверждения перед разбором
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
    ex.handle_message(UID, "Идеальная ситуация")  # step 1 -> ждём подтверждения
    ex.handle_message(UID, "➡️ Продолжить")        # подтверждение -> step 1 -> step 2

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

    # образ 1: все 4 вопроса + новая оценка (шаг 5)
    ex.handle_message(UID, "Идеал 1")
    ex.handle_message(UID, "➡️ Продолжить")  # подтверждение шага 1
    ex.handle_message(UID, "80")
    ex.handle_message(UID, "Почему 1")
    ex.handle_message(UID, "Рефлексия 1")  # step 4 -> связный разбор, ждёт новую оценку
    session = ex.user_sessions[UID]
    assert session["question_index"] == 0, "Индекс сдвигается только после ответа на новую оценку"
    ex.handle_message(UID, "5")  # шаг 5: новая оценка -> поздравление + пауза «Продолжить»

    session = ex.user_sessions[UID]
    assert session["question_index"] == 1, "После образа 1 индекс должен указывать на образ 2"
    assert session.get("_between_items") is True, "Между образами должна быть пауза с кнопкой «Продолжить»"
    assert len(session["answers"]) == 1, "Новая запись answers для образа 2 появится только после «Продолжить»"
    assert session["answers"][0] == {
        "text": "Работа", "rate": 8,
        "ideal": "Идеал 1", "percent": 80, "why": "Почему 1", "reflection": "Рефлексия 1",
        "new_rate": 5,
    }

    ex.handle_message(UID, "➡️ Продолжить")  # -> вопрос по образу 2, step 1
    session = ex.user_sessions[UID]
    assert "_between_items" not in session
    assert len(session["answers"]) == 2, "Для образа 2 должна была добавиться новая запись answers"

    # образ 2: все 4 вопроса + новая оценка -> естественное завершение (index >= len(items))
    ex.handle_message(UID, "Идеал 2")
    ex.handle_message(UID, "➡️ Продолжить")  # подтверждение шага 1
    ex.handle_message(UID, "40")
    ex.handle_message(UID, "Почему 2")
    ex.handle_message(UID, "Рефлексия 2")
    ex.handle_message(UID, "3")  # шаг 5 -> последний образ, упражнение завершается

    assert UID not in ex.user_sessions, "После разбора обоих образов упражнение должно завершиться само"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 2
    assert len(result["analysis"]) == 2
    assert result["analysis"][1] == {
        "text": "Семья", "rate": 5,
        "ideal": "Идеал 2", "percent": 40, "why": "Почему 2", "reflection": "Рефлексия 2",
        "new_rate": 3,
    }


def test_stress_search_between_items_pause_reprompts_and_supports_restart():
    """Пауза между образами (после '✅ Итог...') ждёт '➡️ Продолжить' —
    любой другой текст переспрашивает, а 'Сохранить и начать сначала'
    работает и из этой паузы, как и из любой другой точки упражнения."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "Семья 5")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    ex.handle_message(UID, "Идеал 1")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "80")
    ex.handle_message(UID, "Почему 1")
    ex.handle_message(UID, "Рефлексия 1")  # -> связный разбор, ждёт новую оценку
    ex.handle_message(UID, "5")  # шаг 5 -> поздравление + пауза между образами

    assert ex.user_sessions[UID]["_between_items"] is True

    # случайный текст во время паузы — не продвигает, просто переспрашивает
    ex.handle_message(UID, "чтотоещё")
    assert ex.user_sessions[UID]["_between_items"] is True
    assert "Продолжить" in vk.last_message

    # «Сохранить и начать заново» работает и из этой паузы — но с 01.09.2026
    # только разобран 1 образ из 2 (меньше MIN_ANALYZED_TO_FINISH_EARLY=3,
    # и записано меньше MIN_ITEMS_TO_FINISH_EARLY=10), так что отправлять
    # наблюдателю ещё рано: результат НЕ сохраняется, но новая сессия всё
    # равно открывается с нуля.
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 0, "Маловато материала — рано отправлять наблюдателю"
    assert ex.user_sessions[UID]["phase"] == "collecting"
    assert ex.user_sessions[UID]["items"] == []


def test_stress_search_new_rate_step_validates_1_to_10():
    """Шаг 5 (новая оценка после разбора) принимает только число 1-10 —
    не цифры и выход за диапазон переспрашивают, не продвигая упражнение."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")
    ex.handle_message(UID, "Идеал")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "80")
    ex.handle_message(UID, "Почему")
    ex.handle_message(UID, "Рефлексия")  # -> шаг 5, ждёт новую оценку

    ex.handle_message(UID, "не число")
    assert ex.user_sessions[UID]["question_step"] == 5
    assert "Напиши число от 1 до 10" in vk.last_message

    ex.handle_message(UID, "11")
    assert ex.user_sessions[UID]["question_step"] == 5
    assert "от 1 до 10" in vk.last_message

    ex.handle_message(UID, "0")
    assert ex.user_sessions[UID]["question_step"] == 5

    ex.handle_message(UID, "4")  # валидное значение -> завершение (единственный образ)
    assert UID not in ex.user_sessions
    assert api.results[0]["result_data"]["analysis"][0]["new_rate"] == 4


def test_diary_advance_without_answer_shows_error_and_does_not_advance():
    """Нажатие «➡️ Продолжить» до того, как что-то написано на шаге,
    должно показать «❌ Напиши...» и не сдвигать фазу вперёд."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "dream", "Фаза не должна была смениться без ответа"
    assert "Напиши свой сон" in vk.last_message

    ex.handle_message(UID, "Гулял по парку")  # dream -> блок "День" ждёт
    assert UID not in ex.user_sessions, "Между блоками (Утро -> День) сессия завершается"
    _diary_resume(ex)  # заглянули через час, теперь фаза 'mood'
    assert ex.user_sessions[UID]["phase"] == "mood"

    # на новой фазе тот же guard снова срабатывает, пока нет ответа
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "mood", "Фаза не должна была смениться без ответа на 'mood'"
    assert "Напиши настроение" in vk.last_message


def test_diary_blank_text_from_sticker_does_not_advance():
    """Баг #3: main.py превращает стикер/фото/голосовое в text="" — такой
    пустой ответ не должен молча записываться и продвигать шаг."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    assert ex.user_sessions[UID]["phase"] == "dream"

    ex.handle_message(UID, "")  # "стикер"
    assert ex.user_sessions[UID]["phase"] == "dream", "Пустой текст не должен продвигать фазу"
    assert ex.user_sessions[UID]["dream"] == "", "Пустой текст не должен был записаться"
    assert "не могу обработать стикер" in vk.last_message

    ex.handle_message(UID, "   ")  # только пробелы — тоже "пусто"
    assert ex.user_sessions[UID]["phase"] == "dream"

    ex.handle_message(UID, "Гулял по парку")  # настоящий ответ работает как обычно
    assert UID not in ex.user_sessions, "После сна блок 'Утро' завершён — сессия закрыта до 'Дня'"


def test_stop_technique_advance_without_answer_shows_error_and_does_not_advance():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
    assert ex.user_sessions[UID]["phase"] == "thoughts"
    assert "Напиши, о чём думаешь" in vk.last_message


def test_stop_technique_blank_text_from_sticker_does_not_advance():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "")  # "стикер"
    assert ex.user_sessions[UID]["phase"] == "thoughts"
    assert ex.user_sessions[UID]["thoughts"] == ""
    assert "не могу обработать стикер" in vk.last_message

    ex.handle_message(UID, "Думаю о работе")
    assert ex.user_sessions[UID]["phase"] == "feelings"


def test_diary_save_and_restart_with_no_answers_does_not_save_empty_result():
    """Гейт: «Сохранить и начать заново» на самом первом экране (ни на один
    из 6 шагов ещё не ответили) раньше всё равно создавал на сервере
    полностью пустую запись дневника."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 0, "Пустая запись не должна была сохраниться"
    # sent[-2] — предупреждение; последнее сообщение — уже приглашение
    # новой сессии из _handle_start_over
    assert "нечего сохранять" in vk.sent[-2]["message"].lower()
    assert UID in ex.user_sessions, "Новая сессия должна была открыться"
    assert ex.user_sessions[UID]["phase"] == "dream"


def test_diary_save_and_restart_failure_keeps_answers_instead_of_wiping_them():
    """Дыра: если save_result() падает, _finish() уже сохраняет ответы как
    черновик прогресса и честно сообщает о сбое — но раньше
    _handle_save_and_start_over() всё равно СРАЗУ ЖЕ вызывал
    _handle_start_over(), который удалял этот самый черновик (delete_progress)
    и открывал пустую сессию — ответы терялись насовсем, хотя пользователю
    сказали "ничего не потеряно"."""
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")  # dream -> блок "День" ждёт, есть хоть что-то
    _diary_resume(ex)                          # заглянули через час, сессия снова активна

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    # Сессия НЕ должна была сброситься — ответ "Гулял по парку" всё ещё на месте
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["dream"] == "Гулял по парку"
    assert ex.user_sessions[UID]["phase"] == "mood"
    # И черновик прогресса должен был реально уйти на сервер (see _report_save_failure)
    assert api.progress_store.get((UID, "diary"), {}).get("dream") == "Гулял по парку"

    # Повторная попытка той же кнопкой после того, как сервис отошёл — работает
    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["phase"] == "dream", "Теперь должна была открыться новая сессия"


def test_stop_technique_save_and_restart_with_no_answers_does_not_save_empty_result():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 0, "Пустая 'остановка' без единого ответа не должна была сохраниться"
    assert "нечего сохранять" in vk.sent[-2]["message"].lower()
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["phase"] == "thoughts"


def test_stop_technique_save_and_restart_failure_keeps_answers_instead_of_wiping_them():
    ex, vk, api = make(StopTechniqueExercise)
    ex.start(UID)
    ex.handle_message(UID, "Думаю о работе")  # thoughts -> feelings

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["thoughts"] == "Думаю о работе"
    assert ex.user_sessions[UID]["phase"] == "feelings"
    assert api.progress_store.get((UID, "stop_technique"), {}).get("thoughts") == "Думаю о работе"

    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["phase"] == "thoughts"


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
    ex.handle_message(UID, "➡️ Продолжить")     # -> step 2 (экран примера фразы)
    assert ex.user_sessions[UID]["step"] == 2

    # экран примера фразы: "Продолжить" без своего варианта — разрешён,
    # просто оставляет фразу как в примере и открывает сам вопрос
    ex.handle_message(UID, "✅ Завершить")
    assert ex.user_sessions[UID]["step"] == 2
    assert "_awaiting_own_affirmation" not in ex.user_sessions[UID]

    # а вот сам вопрос ("кто отнял") уже обязателен — "Продолжить" без ответа отклоняется
    ex.handle_message(UID, "✅ Завершить")
    assert ex.user_sessions[UID]["step"] == 2
    assert "Напиши свой ответ" in vk.last_message

    ex.handle_message(UID, "Никто не отнял")
    # шаг 3: "Продолжить" без ответа
    ex.handle_message(UID, "✅ Завершить")
    assert ex.user_sessions[UID]["step"] == 3
    assert "Напиши свой ответ" in vk.last_message


def test_conscious_choice_blank_text_from_sticker_does_not_advance():
    """Баг #3: пустой текст (стикер/фото/голосовое) не должен молча
    записываться и продвигать шаг — проверяем на нескольких из
    затронутых шагов (2, 3, 5, 6, 8, 9)."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")   # step 1 -> запись первого пункта
    ex.handle_message(UID, "➡️ Продолжить")   # -> step 2 (экран примера фразы)

    ex.handle_message(UID, "")  # "стикер" на экране примера фразы
    assert ex.user_sessions[UID]["step"] == 2
    assert ex.user_sessions[UID]["_awaiting_own_affirmation"] is True
    assert "не могу обработать стикер" in vk.last_message

    ex.handle_message(UID, "Имею право")      # свой вариант фразы -> экран вопроса
    assert "_awaiting_own_affirmation" not in ex.user_sessions[UID]

    ex.handle_message(UID, "")  # "стикер" на самом вопросе
    assert ex.user_sessions[UID]["step"] == 2
    assert "current_answer" not in ex.user_sessions[UID]
    assert "не могу обработать стикер" in vk.last_message

    ex.handle_message(UID, "Никто")           # step 2 -> 3 (реальный ответ)
    assert ex.user_sessions[UID]["step"] == 3

    ex.handle_message(UID, "   ")  # "стикер" на шаге 3 (только пробелы)
    assert ex.user_sessions[UID]["step"] == 3
    assert "who_greater" not in ex.user_sessions[UID]


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
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 8")  # хватает, чтобы завершить без разбора
    ex.handle_message(UID, "➡️ Продолжить")   # analysis
    ex.handle_message(UID, "✅ Завершить")     # завершить сразу из анализа

    assert len(api.results) == 1
    assert api.results[0]["exercise_type"] == "stress_search", (
        f"Результат сохранён с exercise_type={api.results[0]['exercise_type']!r}, "
        f"а не 'stress_search' — см. _finish_exercise(), там 'exercise_id = 1'"
    )


# ---------------------------------------------------------------------------
# save_result() возвращает falsy при сбое сети/сервера (баг #1) — упражнение
# должно честно сообщить об ошибке, НЕ удалять прогресс и НЕ закрывать сессию.
# ---------------------------------------------------------------------------

def test_happiness_list_save_result_failure_is_reported_honestly():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Пункт1 — 5")

    api.fail_save_result = True
    ex.handle_message(UID, "➡️ Продолжить")  # -> _finish() -> save_result() падает

    assert "Не получилось сохранить результат" in vk.last_message
    assert len(api.results) == 0, "Результат не должен был сохраниться при сбое"
    assert UID in ex.user_sessions, "Сессия должна пережить сбой сохранения — для повторной попытки"
    # прогресс сохранён как резервная копия (см. _report_save_failure)
    assert api.progress_store.get((UID, "happiness_list")) is not None

    # повторная попытка после восстановления сервиса должна отработать штатно
    api.fail_save_result = False
    ex.handle_message(UID, "➡️ Продолжить")
    assert len(api.results) == 1
    assert UID not in ex.user_sessions


def test_happiness_list_save_and_restart_failure_keeps_items_instead_of_wiping_them():
    """Дыра: раньше «Сохранить и начать заново» с непустым списком вызывал
    _finish() и БЕЗУСЛОВНО следом _start_new() — даже если save_result()
    падал. _finish() уже честно сообщал о сбое и сохранял items как
    черновик прогресса, но _start_new() тут же подменял текущую сессию
    пустой ({'items': []}) — пользователю говорили "ничего не потеряно", а
    его список пунктов в тот же момент пропадал из вида."""
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кофе утром — 8")

    api.fail_save_result = True
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    assert "Не получилось сохранить" in vk.last_message
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["items"] == [{"text": "Кофе утром", "score": 8}], (
        "Список не должен был обнулиться при сбое сохранения"
    )
    assert api.progress_store.get((UID, "happiness_list"), {}).get("items") == [
        {"text": "Кофе утром", "score": 8}
    ]

    # повторная попытка после восстановления сервиса должна отработать штатно
    api.fail_save_result = False
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["items"] == [], "Теперь должна была открыться новая пустая сессия"


def test_happiness_list_save_and_restart_with_empty_list_starts_fresh_without_saving():
    """Ветка 'нечего сохранять' не должна ломаться отдельно от ветки со
    сбоем — с пустым списком сразу чистый рестарт, без обращения к
    save_result вообще."""
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 0
    assert UID in ex.user_sessions
    assert ex.user_sessions[UID]["items"] == []


def test_stress_search_save_result_failure_is_reported_honestly():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 8")  # хватает, чтобы завершить без разбора
    ex.handle_message(UID, "➡️ Продолжить")   # -> analysis

    api.fail_save_result = True
    ex.handle_message(UID, "✅ Завершить")     # -> _finish_exercise() -> save_result() падает

    assert "Не получилось сохранить результат" in vk.last_message
    assert len(api.results) == 0, "Результат не должен был сохраниться при сбое"
    assert UID in ex.user_sessions, "Сессия должна пережить сбой сохранения — для повторной попытки"

    api.fail_save_result = False
    ex.handle_message(UID, "✅ Завершить")
    assert len(api.results) == 1
    assert UID not in ex.user_sessions


# ---------------------------------------------------------------------------
# Досрочное завершение разбора «Поиска стресса»: после того как разобрано
# минимум MIN_ANALYZED_TO_FINISH_EARLY (3) образов, между образами
# появляется кнопка «✅ Завершить и отправить», позволяющая отправить
# упражнение наблюдателю на проверку, не разбирая остальные записанные
# образы — не нужно ждать разбора всех.
# ---------------------------------------------------------------------------

def _stress_do_item(ex, ideal, percent, why, reflection, new_rate):
    ex.handle_message(UID, ideal)
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, str(percent))
    ex.handle_message(UID, why)
    ex.handle_message(UID, reflection)
    ex.handle_message(UID, str(new_rate))


def test_stress_search_no_early_finish_button_before_3_analyzed():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "A 5")
    ex.handle_message(UID, "B 5")
    ex.handle_message(UID, "C 5")
    ex.handle_message(UID, "D 5")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    _stress_do_item(ex, "i1", 10, "w1", "r1", 3)  # разобран 1 — кнопки ещё нет
    assert "✅ Завершить и отправить" not in vk.last_buttons
    ex.handle_message(UID, "➡️ Продолжить")

    _stress_do_item(ex, "i2", 10, "w2", "r2", 3)  # разобрано 2 — кнопки всё ещё нет
    assert "✅ Завершить и отправить" not in vk.last_buttons
    ex.handle_message(UID, "➡️ Продолжить")

    _stress_do_item(ex, "i3", 10, "w3", "r3", 3)  # разобрано 3 — кнопка должна появиться
    assert "✅ Завершить и отправить" in vk.last_buttons
    assert ex.user_sessions[UID]["_between_items"] is True
    assert len(api.results) == 0, "Само по себе появление кнопки ничего не завершает"


def test_stress_search_finish_and_send_text_ignored_before_3_analyzed():
    """Текст «Завершить и отправить», написанный раньше 3 разобранных
    образов (когда кнопки такой ещё нет), не должен досрочно завершать
    упражнение — это просто нераспознанный текст паузы между образами."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "A 5")
    ex.handle_message(UID, "B 5")
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    _stress_do_item(ex, "i1", 10, "w1", "r1", 3)  # разобран только 1
    ex.handle_message(UID, "✅ Завершить и отправить")

    assert len(api.results) == 0
    assert ex.user_sessions[UID]["_between_items"] is True


def test_stress_search_finish_early_after_3_analyzed_skips_remaining_items():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "A 5")
    ex.handle_message(UID, "B 5")
    ex.handle_message(UID, "C 5")
    ex.handle_message(UID, "D 5")  # 4 образа записано, разберём только 3
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")

    _stress_do_item(ex, "i1", 10, "w1", "r1", 3)
    ex.handle_message(UID, "➡️ Продолжить")
    _stress_do_item(ex, "i2", 10, "w2", "r2", 3)
    ex.handle_message(UID, "➡️ Продолжить")
    _stress_do_item(ex, "i3", 10, "w3", "r3", 3)

    assert "✅ Завершить и отправить" in vk.last_buttons
    ex.handle_message(UID, "✅ Завершить и отправить")

    assert UID not in ex.user_sessions, "Упражнение должно полностью завершиться"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 4, "Все 4 записанных образа остаются в items"
    assert len(result["analysis"]) == 3, "Но разобрано (analysis) только 3, четвёртый не трогали"


# ---------------------------------------------------------------------------
# Досрочное завершение прямо из части 1 (сбор образов) — второй, независимый
# от разбора путь отправить упражнение на проверку: как только записано
# MIN_ITEMS_TO_FINISH_EARLY (10) образов, не заходя в часть 2 вообще.
# ---------------------------------------------------------------------------

def _stress_write_items(ex, n):
    for i in range(n):
        ex.handle_message(UID, f"Причина{i} 5")


def test_stress_search_part1_no_finish_button_before_10_items():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    _stress_write_items(ex, 9)
    assert "✅ Завершить и отправить" not in vk.last_buttons


def test_stress_search_part1_finish_button_appears_at_10_items():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    _stress_write_items(ex, 10)
    assert "✅ Завершить и отправить" in vk.last_buttons
    assert len(api.results) == 0


def test_stress_search_part1_finish_and_send_too_early_is_rejected():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    _stress_write_items(ex, 5)
    ex.handle_message(UID, "✅ Завершить и отправить")

    assert len(api.results) == 0, "Рано — 10 ещё не набрано"
    assert "5" in vk.last_message, "Честно называет текущий счётчик"
    assert ex.user_sessions[UID]["phase"] == "collecting"


def test_stress_search_part1_finish_and_send_at_10_items_saves_without_analysis():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    _stress_write_items(ex, 10)
    ex.handle_message(UID, "✅ Завершить и отправить")

    assert UID not in ex.user_sessions, "Упражнение должно полностью завершиться"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 10
    assert result["analysis"] == [], "Разбора не было вообще — analysis пуст"


def test_stress_search_part1_finish_and_send_also_works_via_pasted_list():
    """Тот же путь, но образы добавлены не по одному, а вставкой списком
    (другая ветка кода — _add_stress_items, а не инлайновая в handle_collect)."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    pasted = "\n".join(f"Причина{i} 5" for i in range(12))
    ex.handle_message(UID, pasted)
    assert "✅ Завершить и отправить" in vk.last_buttons

    ex.handle_message(UID, "✅ Завершить и отправить")
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 12
    assert result["analysis"] == []


# ---------------------------------------------------------------------------
# Пороги досрочного завершения должны действовать ОТОВСЮДУ, откуда можно
# закончить упражнение — не только через «✅ Завершить и отправить». Правка
# от 01.09.2026 после независимого код-ревью: раньше экран входа в разбор
# («➡️ Далее» / «✅ Завершить») и «💾 Сохранить и начать заново» вызывали
# _finish_exercise() без проверки, полностью обходя оба порога.
# ---------------------------------------------------------------------------

def test_stress_search_analysis_screen_finish_blocked_below_threshold():
    """Экран входа в разбор («➡️ Нажми «Далее»... ✅ «Завершить»») — это тоже
    завершение с 0 разобранных, и должно требовать тот же порог по items,
    что и «✅ Завершить и отправить» из части 1."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")  # только 1 образ
    ex.handle_message(UID, "➡️ Продолжить")  # -> экран входа в разбор

    ex.handle_message(UID, "✅ Завершить")
    assert len(api.results) == 0, "1 образ и 0 разобранных — рано завершать"
    assert "1" in vk.last_message
    assert ex.user_sessions[UID]["phase"] == "analysis", "Сессия не должна была сброситься"


def test_stress_search_analysis_screen_finish_allowed_at_threshold():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 5")
    ex.handle_message(UID, "➡️ Продолжить")

    ex.handle_message(UID, "✅ Завершить")
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 10
    assert result["analysis"] == []


def test_stress_search_save_and_restart_blocked_below_threshold():
    """'Сохранить и начать заново' с недостаточным материалом (см. также
    test_stress_search_between_items_pause_reprompts_and_supports_restart)
    не должно отправлять наблюдателю пустышку — только честно предупредить
    и начать заново без отправки."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    ex.handle_message(UID, "Работа 8")
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 0
    # Предупреждение отправляется отдельным сообщением ПЕРЕД интро нового
    # захода — последнее сообщение (vk.last_message) это уже само интро.
    assert "рано" in vk.sent[-2]["message"].lower()
    assert ex.user_sessions[UID]["phase"] == "collecting"
    assert ex.user_sessions[UID]["items"] == []


def test_stress_search_save_and_restart_allowed_at_threshold():
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 5")
    ex.handle_message(UID, "💾 Сохранить и начать заново")

    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["total_count"] == 10
    assert ex.user_sessions[UID]["phase"] == "collecting"
    assert ex.user_sessions[UID]["items"] == []


def test_stress_search_in_progress_answer_not_counted_as_analyzed_or_sent():
    """Незавершённая запись answers (образ, который сейчас разбирается, но
    ещё не дошли до переоценки) не должна ни засчитываться в 'разобрано',
    ни попадать в отправляемый analysis — раньше session['answers'] включал
    её как есть, что могло досрочно (и ошибочно) открыть порог в 3, а сам
    result_data['analysis'] содержал бы недоделанную запись без 'new_rate'."""
    ex, vk, api = make(StressSearchExercise)
    ex.start(UID)
    for i in range(10):
        ex.handle_message(UID, f"Причина{i} 5")  # 10 items, ни один не разобран
    ex.handle_message(UID, "➡️ Продолжить")
    ex.handle_message(UID, "➡️ Далее")  # -> вопрос 1 по образу 1

    ex.handle_message(UID, "Идеал 1")
    ex.handle_message(UID, "➡️ Продолжить")  # застряли на середине вопроса 2/4

    session = ex.user_sessions[UID]
    assert len(session["answers"]) == 1, "Запись уже добавлена, хоть и не закончена"
    assert "new_rate" not in session["answers"][0]
    assert ex._completed_answers(session) == [], "Незаконченная запись не считается разобранной"

    ex.handle_message(UID, "💾 Сохранить и начать заново")
    assert len(api.results) == 1, "10 items >= порога — сохранение всё равно должно пройти"
    result = api.results[0]["result_data"]
    assert result["analysis"] == [], "Незаконченный разбор не должен попасть в отправляемые данные"


# ---------------------------------------------------------------------------
# send_message() не должен ронять вызывающий код (баг #4б) — актуально
# особенно для _finish(), где save_result()/delete_progress() уже
# отработали к моменту отправки завершающего сообщения.
# ---------------------------------------------------------------------------

def test_happiness_list_finish_survives_send_message_failure():
    ex, vk, api = make(HappinessListExercise)
    ex.start(UID)
    ex.handle_message(UID, "Пункт1 — 5")

    def broken_method(name, params):
        raise RuntimeError("VK API недоступен")

    vk.method = broken_method

    ex.handle_message(UID, "➡️ Продолжить")  # -> _finish() -> send_message() падает внутри

    # save_result()/delete_progress() уже успели отработать до отправки
    # сообщения — упражнение должно было нормально завершиться, а не
    # упасть с необработанным исключением.
    assert len(api.results) == 1
    assert UID not in ex.user_sessions


# ---------------------------------------------------------------------------
# Навигация по шагам (⬅️ Назад / 🏠 В начало / 🏁 В конец) — diary,
# stop_technique, conscious_choice
# ---------------------------------------------------------------------------

def test_diary_back_to_start_and_end_navigation():
    ex, vk, api = make(DiaryExercise)
    ex.start(UID)
    ex.handle_message(UID, "Гулял по парку")   # dream -> блок "День" ждёт
    _diary_resume(ex)                           # заглянули через час
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
    ex.handle_message(UID, "➡️ Продолжить")        # -> step 2 (экран примера фразы)
    ex.handle_message(UID, "Имею право")           # свой вариант фразы -> экран вопроса
    ex.handle_message(UID, "Никто")                # step 2 -> 3
    ex.handle_message(UID, "Никто")                # step 3 -> 4

    session = ex.user_sessions[UID]
    assert session["step"] == 4
    assert session["_max_step"] == 4

    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["step"] == 3
    assert "Текущий ответ" in vk.last_message

    # «В начало» во время разбора ведёт на начало разбора ТЕКУЩЕГО пункта
    # (шаг 2), а не откатывает к уже законченному и замороженному сбору
    # пунктов (шаг 1) — там больше нечего редактировать.
    ex.handle_message(UID, "🏠 В начало")
    assert ex.user_sessions[UID]["step"] == 2

    ex.handle_message(UID, "🏁 В конец")
    assert ex.user_sessions[UID]["step"] == 4, (
        "«В конец» должно вести на самый дальний из достигнутых шагов"
    )


def test_conscious_choice_back_floor_is_start_of_current_item_analysis():
    """Пол для «Назад» — шаг 2 (начало разбора текущего пункта), а не шаг 1
    (сбор пунктов) — раньше с шага 2 «Назад» уводил обратно на уже
    законченный и замороженный экран сбора пунктов."""
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "Кормить детей")
    ex.handle_message(UID, "➡️ Продолжить")  # -> step 2

    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["step"] == 2, "Из шага 2 назад некуда — сбор пунктов уже заморожен"
    assert "первый шаг" in vk.last_message


def test_conscious_choice_back_at_step1_is_noop():
    ex, vk, api = make(ConsciousChoiceExercise)
    ex.start(UID)
    ex.handle_message(UID, "⬅️ Назад")
    assert ex.user_sessions[UID]["step"] == 1
    assert "первый шаг" in vk.last_message
