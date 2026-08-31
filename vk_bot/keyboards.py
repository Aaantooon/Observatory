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
}
CANCEL_TEXTS = {"отмена", "❌ отмена", "cancel", "сохранить и выйти", "💾 сохранить и выйти"}
ADVANCE_TEXTS = {"стоп", "⏹️ стоп", "завершить", "✅ завершить"} | CONTINUE_TEXTS


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

def exercise_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("💾 Сохранить и начать заново", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def analysis_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Далее", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("✅ Завершить", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def cancel_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("💾 Сохранить и выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def continue_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Продолжить ✅", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("Начать заново 🔄", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_review_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("💬 Ответить", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("✅ Завершить проверку", color=VkKeyboardColor.POSITIVE)
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

def main_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔦 Упражнения", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Мои результаты", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⏰ Напоминания", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📨 Проверка", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()