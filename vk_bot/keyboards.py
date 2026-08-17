# vk_bot/keyboards.py
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def main_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔦 Упражнения", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Мои результаты", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

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
    keyboard.add_button("⏹️ Стоп", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("✅ Завершить", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def analysis_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("➡️ Далее", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("✅ Завершить", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def cancel_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def continue_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Продолжить ✅", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("Начать заново 🔄", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()