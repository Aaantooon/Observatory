"""
Автоматические тесты VK-бота "Путь наблюдателя".

Эмулируют реальную переписку пользователя с ботом (без сети — VK и Django API
подменены in-memory заглушками из conftest.py) и проверяют:
  - редизайн клавиатуры упражнений (2 кнопки: Продолжить / Сохранить и начать заново)
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


def test_fresh_start_shows_two_button_keyboard():
    for name, cls in ALL_EXERCISES:
        ex, vk, api = make(cls)
        ex.start(UID)
        buttons = vk.last_buttons
        assert buttons == ["➡️ Продолжить", "💾 Сохранить и начать заново"], (
            f"{name}: ожидались ровно 2 кнопки на стартовом экране, получено {buttons}"
        )


def test_advance_button_is_not_swallowed_as_data():
    """Кнопка 'Продолжить'/'Стоп'/'Завершить' должна распознаваться, а не
    записываться как обычный ответ пользователя."""
    # my_roles: пустая фаза 'social' сразу принимает "Продолжить" без блокировки
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    ex.handle_message(UID, "➡️ Продолжить")
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
    assert session["items"][0]["text"] == "Заново начать жизнь —"
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
        assert buttons == ["➡️ Продолжить", "💾 Сохранить и начать заново"], (
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
        assert ex3.vk.last_buttons == ["➡️ Продолжить", "💾 Сохранить и начать заново"], (
            f"{name}: после 'Начать заново' должен показаться чистый старт"
        )


# ---------------------------------------------------------------------------
# my_roles — снятое ограничение "минимум 1 роль"
# ---------------------------------------------------------------------------

def test_my_roles_no_minimum_items_restriction():
    ex, vk, api = make(MyRolesExercise)
    ex.start(UID)
    session = ex.user_sessions[UID]
    assert session["phase"] == "social"

    ex.handle_message(UID, "➡️ Продолжить")  # 0 ролей введено
    assert ex.user_sessions[UID]["phase"] == "interpersonal", (
        "Переход должен происходить даже с 0 ролей в разделе"
    )

    ex.handle_message(UID, "➡️ Продолжить")  # снова 0 ролей
    assert ex.user_sessions[UID]["phase"] == "intrapersonal"

    ex.handle_message(UID, "➡️ Продолжить")  # снова 0 ролей -> фаза 'analyze'
    # список ролей пуст -> анализировать нечего, упражнение сразу завершается
    assert UID not in ex.user_sessions, "С пустым списком ролей анализ должен сразу завершить упражнение"
    assert len(api.results) == 1
    result = api.results[0]["result_data"]
    assert result["social_roles"] == []
    assert result["interpersonal_roles"] == []
    assert result["intrapersonal_roles"] == []


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

    assert vk.last_buttons == ["➡️ Продолжить", "💾 Сохранить и начать заново"], (
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
