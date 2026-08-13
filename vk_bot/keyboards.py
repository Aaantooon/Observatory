# keyboards.py
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def main_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Упражнения", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Мои результаты", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("Бесилки", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("Синхронизация", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def exercises_menu():
    keyboard = VkKeyboard(one_time=True)
    # По 2 кнопки в строке (максимум 4)
    keyboard.add_button("Упражнение 1", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Упражнение 2", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Упражнение 3", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Упражнение 4", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Упражнение 5", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Упражнение 6", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def exercise_detail():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Выполнить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("К списку", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("Главное меню", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def cancel_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Отмена", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()