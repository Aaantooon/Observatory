# handlers.py
from vk_api.utils import get_random_id
from api_client import APIClient
from keyboards import main_menu, exercises_menu, exercise_detail, cancel_keyboard
from exercises.besilki import BesilkiExercise

class BotHandlers:
    def __init__(self, vk_session):
        self.vk = vk_session
        self.api = APIClient()
        self.user_states = {}
        self.selected_exercise = {}
        self.besilki = BesilkiExercise(vk_session, self.api)

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    def handle_message(self, user_id, text, first_name, last_name):
        # Проверяем, не активен ли Бесилки
        if user_id in self.besilki.user_sessions:
            self.besilki.handle_message(user_id, text)
            return

        if user_id not in self.user_states:
            self.api.get_or_create_user(user_id, first_name, last_name)
            self.user_states[user_id] = 'main'
            self.send_message(
                user_id,
                f"Привет, {first_name}! Я помогу тебе выполнять упражнения.\n\nВыбери действие:",
                main_menu()
            )
            return

        state = self.user_states.get(user_id, 'main')
        text_clean = text.lower().strip()

        if state == 'main':
            if text_clean == "упражнения":
                self.show_exercises(user_id)
            elif text_clean == "мои результаты":
                self.show_results(user_id)
            elif text_clean == "бесилки":
                self.besilki.start(user_id)
            elif text_clean == "синхронизация":
                self.send_message(user_id, "Данные синхронизированы!", main_menu())
            else:
                self.send_message(user_id, "Используй кнопки меню", main_menu())

        elif state == 'selecting_exercise':
            if text_clean == "назад":
                self.user_states[user_id] = 'main'
                self.send_message(user_id, "Главное меню:", main_menu())
            elif text.startswith("Упражнение"):
                try:
                    num = int(text.split()[1])
                    exercises = self.api.get_exercises()
                    if 1 <= num <= len(exercises):
                        exercise = exercises[num-1]
                        self.selected_exercise[user_id] = exercise['id']
                        self.user_states[user_id] = 'viewing_exercise'
                        msg = f"{exercise['title']}\n\n{exercise.get('description', 'Описание отсутствует')}\n\nЧто будем делать?"
                        self.send_message(user_id, msg, exercise_detail())
                    else:
                        self.send_message(user_id, "Выбери упражнение из списка")
                except:
                    self.send_message(user_id, "Выбери упражнение из списка")

        elif state == 'viewing_exercise':
            if text_clean == "выполнить":
                self.user_states[user_id] = 'waiting_result'
                self.send_message(
                    user_id,
                    "Введи свой результат:\nНапример: 15 повторений, текст, 10 минут",
                    cancel_keyboard()
                )
            elif text_clean == "к списку":
                self.show_exercises(user_id)
            elif text_clean == "главное меню":
                self.user_states[user_id] = 'main'
                self.send_message(user_id, "Главное меню:", main_menu())

        elif state == 'waiting_result':
            if text_clean == "отмена":
                self.user_states[user_id] = 'main'
                self.send_message(user_id, "Отменено. Главное меню:", main_menu())
            else:
                exercise_id = self.selected_exercise.get(user_id, 1)
                self.api.save_result(user_id, exercise_id, text)
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    f"Результат сохранён!\n\nТвой ответ: {text}\nПсихолог проверит и может скорректировать.",
                    main_menu()
                )

    def show_exercises(self, user_id):
        self.user_states[user_id] = 'selecting_exercise'
        exercises = self.api.get_exercises()
        if not exercises:
            self.send_message(user_id, "Упражнения пока не добавлены.", main_menu())
            return

        message = "Выбери упражнение:\n\n"
        for i, ex in enumerate(exercises, 1):
            message += f"{i}. {ex['title']}\n"
        self.send_message(user_id, message, exercises_menu())

    def show_results(self, user_id):
        results = self.api.get_user_results(user_id)
        if not results:
            self.send_message(user_id, "У тебя пока нет выполненных упражнений.", main_menu())
            return

        message = "Твои последние результаты:\n\n"
        for i, res in enumerate(results[:5], 1):
            status = "Проверено" if res.get('is_approved') else "Ожидает проверки"
            message += f"{i}. {res.get('exercise_title', 'Упражнение')}\n"
            message += f"   Твой ответ: {res.get('result_data')}\n"
            if res.get('corrected_data'):
                message += f"   Коррекция: {res['corrected_data']}\n"
            message += f"   {status}\n\n"

        self.send_message(user_id, message, main_menu())