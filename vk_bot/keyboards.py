from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# Точные (не по подстроке!) варианты текста для распознавания нажатий кнопок
# "Продолжить"/"Начать заново"/"Сохранить и начать заново" в обычном тексте
# пользователя (например в ответе на упражнение) — чтобы случайное слово
# "заново" или "продолжить" внутри реального ответа не путалось с командой.
CONTINUE_TEXTS = {"продолжи", "продолжить", "➡️ продолжить", "продолжить ✅", "✅ продолжить"}
RESTART_TEXTS = {"заново", "начать заново", "начать заново 🔄", "🔄 начать заново"}
SAVE_AND_RESTART_TEXTS = {
    "сохранить и начать заново",
    "💾 сохранить и начать заново",
    "начать заново и сохранить",
    "🔄 начать заново и сохранить",
}
CANCEL_TEXTS = {
    "отмена", "❌ отмена", "cancel",
    "сохранить и выйти", "💾 сохранить и выйти",
    "выйти и сохранить", "💾 выйти и сохранить",
}
ADVANCE_TEXTS = {"стоп", "⏹️ стоп", "завершить", "✅ завершить"} | CONTINUE_TEXTS
# Досрочное завершение разбора «Поиска стресса» между образами (когда уже
# разобрано минимум 3 из них) — специально другая формулировка, чтобы не
# путаться с обычным ADVANCE_TEXTS "завершить" в других местах упражнения.
FINISH_AND_SEND_TEXTS = {
    "завершить и отправить",
    "✅ завершить и отправить",
    "завершить и отправить на проверку",
}
CONFIRM_YES_TEXTS = {"да", "да, дальше", "да, дальше ✅", "✅ да, дальше"}
CONFIRM_NO_TEXTS = {"нет", "нет, буду писать", "нет, буду писать ✏️", "✏️ нет, буду писать"}
OVERRIDE_LIMIT_TEXTS = {"всё равно продолжить", "⚠️ всё равно продолжить"}
# Кнопка на экране Вопроса 1/4 «Поиска стресса» — изменить текст/оценку
# самого пункта, если он неточно сформулирован (не найти противоположность).
EDIT_ITEM_TEXTS = {"изменить пункт", "✏️ изменить пункт"}

# Навигация по шагам упражнения — доступна в любой момент внутри сессии
BACK_TEXTS = {"назад", "⬅️ назад"}
TO_START_TEXTS = {"в начало", "🏠 в начало"}
TO_END_TEXTS = {"в конец", "🏁 в конец"}


# ---------------------------------------------------------------------------
# Нейтральное представление клавиатуры + конвертер в формат VK.
#
# Каждая функция ниже (exercise_keyboard, main_menu и т.д.) возвращает не
# VK-специфичный объект, а нейтральную структуру — список рядов, каждый ряд
# список кнопок (текст, цвет). Цвет — платформонезависимая строка
# ('positive'/'negative'/'primary'/'secondary'); платформы без цветных
# кнопок (Telegram и т.п.) её просто игнорируют. Так эти же функции годятся
# для любого MessagingAdapter (см. platform_bots/README.md) — VK остаётся
# лишь ОДНИМ из потребителей, а не единственным, для кого они написаны.
#
# to_vk_keyboard() — единственное место, которое превращает нейтральную
# структуру в JSON, ожидаемый vk.method('messages.send', {'keyboard': ...}).
# Вызывается из send_message() в exercises/base.py, exercises/stress_search.py
# и handlers.py — это единственные 3 места, которые реально отправляют
# сообщение в VK. Раньше каждая функция ниже сама строила VkKeyboard и
# отдавала готовый VK JSON — поведение (сами кнопки, их цвета, разбивка на
# ряды, one_time) не изменилось ни на бит, изменилось только КТО и КОГДА
# знает про VkKeyboard.
# ---------------------------------------------------------------------------

_VK_COLORS = {
    "positive": VkKeyboardColor.POSITIVE,
    "negative": VkKeyboardColor.NEGATIVE,
    "primary": VkKeyboardColor.PRIMARY,
    "secondary": VkKeyboardColor.SECONDARY,
}


def _kb(rows, one_time=True):
    """Собирает нейтральную клавиатуру: rows — список рядов, каждый ряд —
    список кортежей (текст, цвет)."""
    return {"rows": rows, "one_time": one_time}


def to_vk_keyboard(keyboard):
    """Конвертирует нейтральную клавиатуру (см. _kb выше) в VK JSON-строку.
    keyboard=None -> None (сообщение без клавиатуры, VK это понимает)."""
    if keyboard is None:
        return None
    vk_keyboard = VkKeyboard(one_time=keyboard.get("one_time", True))
    for i, row in enumerate(keyboard.get("rows", [])):
        if i > 0:
            vk_keyboard.add_line()
        for text, color in row:
            vk_keyboard.add_button(text, color=_VK_COLORS.get(color, VkKeyboardColor.PRIMARY))
    return vk_keyboard.get_keyboard()


def exercises_menu():
    rows = [
        [("1. Поиск стресса 🎯", "positive")],
        [("2. Список счастья ✨", "primary"), ("3. Мои роли 🎭", "primary")],
        [("4. Осознанный выбор 🧘", "primary"), ("5. Дневник 📖", "primary")],
        [("6. Стоп-техника 🛑", "primary")],
        [("🔙 Назад", "secondary")],
    ]
    return _kb(rows)

def stress_search_parts_keyboard():
    rows = [
        [("🌫️ Часть 1: Собрать стресс", "positive")],
        [("🧠 Часть 2: Разобрать стресс", "primary")],
        [("🔙 Назад", "secondary")],
    ]
    return _kb(rows)

def exercise_keyboard(can_finish=False):
    """Основная клавиатура «Поиска стресса» — и в части 1 (сбор образов),
    и в паузе между образами в части 2 (разбор). Компактная раскладка — по
    две кнопки в ряд, чтобы клавиатура не растягивалась на 4 строки.
    Кнопка «Завершить и отправить» показывается только когда уже достаточно
    материала для психолога (см. вызывающий код в stress_search.py — два
    независимых порога: MIN_ITEMS_TO_FINISH_EARLY в части 1,
    MIN_ANALYZED_TO_FINISH_EARLY в части 2), чтобы не звать отправлять на
    проверку то, что ещё рано смотреть — и стоит сразу под «Продолжить»,
    а не в самом низу."""
    first_row = [("➡️ Продолжить", "positive")]
    if can_finish:
        first_row.append(("✅ Завершить и отправить", "positive"))
    rows = [
        first_row,
        [("💾 Сохранить и начать заново", "negative"), ("💾 Сохранить и выйти", "secondary")],
    ]
    return _kb(rows)

def analysis_keyboard():
    rows = [
        [("➡️ Далее", "primary")],
        [("✅ Завершить", "positive")],
    ]
    return _kb(rows)

def daily_limit_keyboard():
    rows = [
        [("⚠️ Всё равно продолжить", "negative")],
        [("💾 Сохранить и выйти", "secondary")],
    ]
    return _kb(rows)

def confirm_skip_keyboard():
    rows = [
        [("✅ Да, дальше", "positive")],
        [("✏️ Нет, буду писать", "secondary")],
    ]
    return _kb(rows)

def role_phase_choice_keyboard():
    """Клавиатура выбора части «Мои роли», в которую человек хочет
    вернуться и дописать роли — на экране перед стартом разбора (см.
    _show_preanalyze_confirm в my_roles.py)."""
    rows = [
        [("1. Социальные", "primary")],
        [("2. Межличностные", "primary")],
        [("3. Внутриличностные", "primary")],
    ]
    return _kb(rows)

def simple_continue_keyboard():
    """Клавиатура с единственной кнопкой «Продолжить» — для экранов, где не
    нужен выбор да/нет, а просто подтверждение «готов, двигаюсь дальше»."""
    rows = [[("➡️ Продолжить", "positive")]]
    return _kb(rows)

def cancel_keyboard():
    rows = [[("💾 Сохранить и выйти", "negative")]]
    return _kb(rows)

def question1_keyboard():
    """Клавиатура экрана Вопроса 1/4 («какая противоположность?») — с
    кнопкой «Изменить пункт», чтобы поправить текст/оценку образа прямо
    здесь, если он неточно сформулирован, не выходя из разбора."""
    rows = [
        [("✏️ Изменить пункт", "primary")],
        [("💾 Сохранить и выйти", "negative")],
    ]
    return _kb(rows)

def continue_keyboard():
    rows = [
        [("Продолжить ✅", "positive")],
        [("Начать заново 🔄", "secondary")],
    ]
    return _kb(rows)

def get_reminder_keyboard():
    rows = [
        [("⏰ Напомнить через 1 час", "primary"), ("⏰ Напомнить через 3 часа", "secondary")],
        [("⏰ Напомнить завтра утром", "primary")],
        [("🛑 Стоп-техника в течение дня", "primary")],
        [("❌ Отключить напоминания", "negative")],
        [("🔙 Назад", "secondary")],
    ]
    return _kb(rows, one_time=False)

def back_keyboard():
    rows = [[("🔙 Назад", "secondary")]]
    return _kb(rows)

def finish_keyboard():
    rows = [
        [("✅ Завершить", "positive")],
        [("💾 Сохранить и выйти", "negative")],
    ]
    return _kb(rows)

def conscious_choice_keyboard():
    rows = [
        [("➡️ Продолжить", "positive")],
        [("🔄 Начать заново и сохранить", "negative")],
        [("💾 Выйти и сохранить", "secondary")],
    ]
    return _kb(rows)

def step_nav_keyboard():
    # Раньше здесь ещё был ряд «⬅️ Назад / 🏠 В начало / 🏁 В конец» — по
    # просьбе пользователя убран (лишние кнопки на экране). Сама навигация
    # (_handle_back/_handle_to_start/_handle_to_end в stop_technique.py и
    # diary.py) никуда не делась — доступна как и раньше, если написать
    # текстом «назад»/«в начало»/«в конец» (BACK_TEXTS/TO_START_TEXTS/
    # TO_END_TEXTS в этом же файле), просто без кнопок в клавиатуре.
    rows = [
        [("➡️ Продолжить", "positive")],
        [("💾 Сохранить и начать заново", "negative")],
        [("💾 Сохранить и выйти", "secondary")],
    ]
    return _kb(rows)

def main_menu():
    rows = [
        [("🔦 Упражнения", "primary"), ("📊 Мои результаты", "secondary")],
        [("⏰ Напоминания", "primary"), ("📨 Проверка", "secondary")],
        [("📅 Мой план на день", "primary")],
        [("🔗 Привязать аккаунт", "secondary")],
    ]
    return _kb(rows, one_time=False)

def account_link_menu_keyboard():
    """Экран «Привязка аккаунта» (объединить VK и Telegram в один — см.
    handlers.py::show_account_link_menu, platform_bots/README.md, раздел
    «Модель пользователя»)."""
    rows = [
        [("🔑 Получить код", "primary")],
        [("✍️ Ввести код", "primary")],
        [("🔙 Назад", "secondary")],
    ]
    return _kb(rows, one_time=False)

def results_keyboard(has_more=False):
    """Клавиатура экрана «Мои результаты» — с кнопкой «Вся история»,
    если записей больше, чем показано в кратком списке."""
    rows = []
    if has_more:
        rows.append([("📜 Вся история", "secondary")])
    rows.append([("🔦 Упражнения", "primary"), ("🔙 Меню", "secondary")])
    return _kb(rows, one_time=False)
