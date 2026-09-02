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


def exercises_menu():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("1. Поиск стресса 🎯", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("2. Список счастья ✨", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("3. Мои роли 🎭", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("4. Осознанный выбор 🧘", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("5. Дневник 📖", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("6. Стоп-техника 🛑", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def stress_search_parts_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("🌫️ Часть 1: Собрать стресс", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🧠 Часть 2: Разобрать стресс", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

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
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    if can_finish:
        keyboard.add_button("✅ Завершить и отправить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и начать заново", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def analysis_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Далее", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("✅ Завершить", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def daily_limit_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("⚠️ Всё равно продолжить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def confirm_skip_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Да, дальше", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("✏️ Нет, буду писать", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def role_phase_choice_keyboard():
    """Клавиатура выбора части «Мои роли», в которую человек хочет
    вернуться и дописать роли — на экране перед стартом разбора (см.
    _show_preanalyze_confirm в my_roles.py)."""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("1. Социальные", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("2. Межличностные", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("3. Внутриличностные", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def simple_continue_keyboard():
    """Клавиатура с единственной кнопкой «Продолжить» — для экранов, где не
    нужен выбор да/нет, а просто подтверждение «готов, двигаюсь дальше»."""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def cancel_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def question1_keyboard():
    """Клавиатура экрана Вопроса 1/4 («какая противоположность?») — с
    кнопкой «Изменить пункт», чтобы поправить текст/оценку образа прямо
    здесь, если он неточно сформулирован, не выходя из разбора."""
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✏️ Изменить пункт", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def continue_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Продолжить ✅", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("Начать заново 🔄", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_reminder_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⏰ Напомнить через 1 час", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("⏰ Напомнить через 3 часа", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⏰ Напомнить завтра утром", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("❌ Отключить напоминания", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def back_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def finish_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Завершить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def conscious_choice_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🏠 В начало", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🏁 В конец", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🔄 Начать заново и сохранить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Выйти и сохранить", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def step_nav_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🏠 В начало", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🏁 В конец", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и начать заново", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def main_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔦 Упражнения", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Мои результаты", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⏰ Напоминания", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📨 Проверка", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("📅 Мой план на день", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def results_keyboard(has_more=False):
    """Клавиатура экрана «Мои результаты» — с кнопкой «Вся история»,
    если записей больше, чем показано в кратком списке."""
    keyboard = VkKeyboard(one_time=False)
    if has_more:
        keyboard.add_button("📜 Вся история", color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
    keyboard.add_button("🔦 Упражнения", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔙 Меню", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()