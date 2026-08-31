from keyboards import main_menu, exercises_menu, get_reminder_keyboard, back_keyboard
from vk_api.utils import get_random_id
from api_client import APIClient
from keyboards import main_menu, exercises_menu, get_reminder_keyboard
from exercises.stress_search import StressSearchExercise
from exercises.happiness_list import HappinessListExercise
from exercises.my_roles import MyRolesExercise
from exercises.conscious_choice import ConsciousChoiceExercise
from exercises.diary import DiaryExercise
from exercises.stop_technique import StopTechniqueExercise
from admin_check import AdminCheck
from notifications import NotificationSystem
from datetime import datetime
import re


class BotHandlers:

    def show_review_menu(self, user_id):
        results = self.api.get_user_results(user_id)
        if not results:
            self.send_message(user_id, "🌫️ У тебя пока нет пройденных упражнений.", main_menu())
            return

        self.user_states[user_id] = 'sending_review'
        exercises_map = {
            'stress_search': '1. Поиск стресса',
            'happiness_list': '2. Список счастья',
            'my_roles': '3. Мои роли',
            'conscious_choice': '4. Осознанный выбор',
            'diary': '5. Дневник',
            'stop_technique': '6. Стоп-техника'
        }
        done = set(r.get('exercise_type') for r in results)
        message = "📨 Отправить на проверку:\n\n"
        for ex_type, name in exercises_map.items():
            if ex_type in done:
                message += f"{name}\n"
        message += "\nНапиши номер упражнения, чтобы отправить."
        self.send_message(user_id, message, back_keyboard())

    def handle_send_review(self, user_id, text_clean):
        results = self.api.get_user_results(user_id)
        exercises_map = {
            '1': 'stress_search', '2': 'happiness_list', '3': 'my_roles',
            '4': 'conscious_choice', '5': 'diary', '6': 'stop_technique'
        }
        if "назад" in text_clean:
            self.user_states[user_id] = 'main'
            self.send_message(user_id, "🔦 Возвращаемся.", main_menu())
            return

        ex_type = exercises_map.get(text_clean[0]) if text_clean and text_clean[0].isdigit() else None
        if not ex_type:
            self.send_message(user_id, "Напиши номер упражнения из списка.", back_keyboard())
            return

        result = next((r for r in results if r.get('exercise_type') == ex_type), None)
        if not result:
            self.send_message(user_id, "Это упражнение ещё не пройдено.", back_keyboard())
            return

        self.api.send_for_review(user_id, ex_type, result.get('result_data', {}))
        self.user_states[user_id] = 'main'
        self.send_message(
            user_id,
            "✅ Отправлено на проверку! Ожидай комментарий от наблюдателя.",
            main_menu()
        )
        
    def __init__(self, vk_session):
        self.vk = vk_session
        self.api = APIClient()
        self.user_states = {}
        
        self.stress_search = StressSearchExercise(vk_session, self.api)
        self.happiness_list = HappinessListExercise(vk_session, self.api)
        self.my_roles = MyRolesExercise(vk_session, self.api)
        self.conscious_choice = ConsciousChoiceExercise(vk_session, self.api)
        self.diary = DiaryExercise(vk_session, self.api)
        self.stop_technique = StopTechniqueExercise(vk_session, self.api)
        
        self.admin_check = AdminCheck(vk_session, self.api)
        self.notifications = NotificationSystem(vk_session, self.api)
        self.notifications.start()

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    def _normalize_text(self, text):
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F700-\U0001F77F"
            u"\U0001F780-\U0001F7FF"
            u"\U0001F800-\U0001F8FF"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA00-\U0001FA6F"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text).strip().lower()

    def handle_message(self, user_id, text, first_name, last_name):
        active_review = self.api.get_active_review(user_id)
        if active_review and active_review.get('status') == 'in_review':
            text_lower = self._normalize_text(text)
            if text_lower not in ['упражнения', 'мои результаты', 'напоминания', 'проверка']:
                self.api.add_comment(active_review['id'], text, is_admin=False)
                self.send_message(user_id, "✅ Ответ отправлен наблюдателю.", main_menu())
                return
        # Проверка сессий упражнений
        if user_id in self.stress_search.user_sessions:
            self.stress_search.handle_message(user_id, text)
            return
        if user_id in self.happiness_list.user_sessions:
            self.happiness_list.handle_message(user_id, text)
            return
        if user_id in self.my_roles.user_sessions:
            self.my_roles.handle_message(user_id, text)
            return
        if user_id in self.conscious_choice.user_sessions:
            self.conscious_choice.handle_message(user_id, text)
            return
        if user_id in self.diary.user_sessions:
            self.diary.handle_message(user_id, text)
            return
        if user_id in self.stop_technique.user_sessions:
            self.stop_technique.handle_message(user_id, text)
            return

        if user_id not in self.user_states:
            self.api.get_or_create_user(user_id, first_name, last_name)
            self.user_states[user_id] = 'main'
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║       🔦 ПУТЬ НАБЛЮДАТЕЛЯ        ║\n"
                "╚══════════════════════════════════╝\n\n"
                f"· Привет, {first_name}!\n"
                "· Я провожу тебя через туман\n"
                "· Выбери, куда направим свет фонарика:",
                main_menu()
            )
            return

        state = self.user_states.get(user_id, 'main')
        text_clean = self._normalize_text(text)

        if state == 'main':
            if "упражнен" in text_clean:
                self.show_exercises(user_id)
            elif "результат" in text_clean or "мои" in text_clean:
                self.show_results(user_id)
            elif "проверк" in text_clean:
                self.show_review_menu(user_id)
            elif "напомина" in text_clean:
                self.show_reminders(user_id)
            else:
                self.send_message(
                    user_id,
                    "🔦 Используй кнопки меню, чтобы выбрать путь.",
                    main_menu()
                )

        elif state == 'selecting_exercise':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "поиск стресса" in text_clean or "стресс" in text_clean or text_clean == "1":
                self.user_states[user_id] = 'main'
                self.stress_search.start(user_id)
            elif "список счастья" in text_clean or "счасть" in text_clean or text_clean == "2":
                self.user_states[user_id] = 'main'
                self.happiness_list.start(user_id)
            elif "роли" in text_clean or text_clean == "3":
                self.user_states[user_id] = 'main'
                self.my_roles.start(user_id)
            elif "осознанный выбор" in text_clean or "выбор" in text_clean or text_clean == "4":
                self.user_states[user_id] = 'main'
                self.conscious_choice.start(user_id)
            elif "дневник" in text_clean or text_clean == "5":
                self.user_states[user_id] = 'main'
                self.diary.start(user_id)
            elif "стоп" in text_clean or text_clean == "6":
                self.user_states[user_id] = 'main'
                self.stop_technique.start(user_id)
            else:
                self.send_message(
                    user_id,
                    "🔦 Выбери упражнение из списка кнопок.",
                    exercises_menu()
                )

        elif state == 'sending_review':
            self.handle_send_review(user_id, text_clean)

        elif state == 'reminders':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "1 час" in text_clean:
                self.notifications.setup_reminder_to_continue(user_id, 'general', hours=1)
                self.send_message(user_id, "✅ Напомню через 1 час.", get_reminder_keyboard())
            elif "3 часа" in text_clean:
                self.notifications.setup_reminder_to_continue(user_id, 'general', hours=3)
                self.send_message(user_id, "✅ Напомню через 3 часа.", get_reminder_keyboard())
            elif "завтра утром" in text_clean:
                self.notifications.setup_diary_reminder(user_id, "08:00")
                self.send_message(user_id, "✅ Напомню завтра утром в 08:00.", get_reminder_keyboard())
            elif "отключить" in text_clean:
                self.send_message(user_id, "🔕 Напоминания отключены.", get_reminder_keyboard())
            else:
                self.send_message(user_id, "⏰ Выбери настройку из кнопок.", get_reminder_keyboard())
    def show_exercises(self, user_id):
        self.user_states[user_id] = 'selecting_exercise'

        message = (
            "╔══════════════════════════════════╗\n"
            "║       📋 ВЫБЕРИ УПРАЖНЕНИЕ      ║\n"
            "╚══════════════════════════════════╝\n\n"
            "1️⃣ Поиск стресса — найди источники напряжения 🎯\n"
            "2️⃣ Список счастья — вспомни, что радует ✨\n"
            "3️⃣ Мои роли — кто ты в этом мире 🎭\n"
            "4️⃣ Осознанный выбор — научись выбирать 🧘\n"
            "5️⃣ Дневник — запиши свои мысли 📖\n"
            "6️⃣ Стоп-техника — останови момент 🛑\n\n"
            "🔥 Нажми на кнопку, чтобы начать!"
        )

        self.send_message(user_id, message, exercises_menu())

    def show_results(self, user_id):
        results = self.api.get_user_results(user_id)
        
        streak_info = self.api.update_streak(user_id)
        streak_text = ""
        if streak_info:
            streak = streak_info.get('streak', 0)
            if streak >= 365:
                streak_text = f"👑 {streak} дней! Ты легенда!"
            elif streak >= 100:
                streak_text = f"🔥 {streak} дней! Ты монстр!"
            elif streak >= 30:
                streak_text = f"🔥 {streak} дней! Круто!"
            elif streak >= 7:
                streak_text = f"🔥 {streak} дней! Отличная привычка!"
            elif streak >= 3:
                streak_text = f"🔥 {streak} дней! Так держать!"
            elif streak == 1:
                streak_text = f"🔥 {streak} день! Начинаем!"

        if not results:
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║        🌫️ ПУТЬ ПУСТ            ║\n"
                "╚══════════════════════════════════╝\n\n"
                "· Твой путь ещё пуст\n"
                "· Начни с любого упражнения\n"
                "· Свет фонарика уже ждёт тебя 🔥",
                main_menu()
            )
            return

        message = "╔══════════════════════════════════╗\n"
        message += "║        📊 МОЙ ПУТЬ              ║\n"
        message += "╚══════════════════════════════════╝\n\n"
        
        if streak_text:
            message += f"{streak_text}\n\n"

        message += "📋 Пройденные упражнения:\n\n"

        exercises_map = {
            'stress_search': '1️⃣ Поиск стресса',
            'happiness_list': '2️⃣ Список счастья',
            'my_roles': '3️⃣ Мои роли',
            'conscious_choice': '4️⃣ Осознанный выбор',
            'diary': '5️⃣ Дневник',
            'stop_technique': '6️⃣ Стоп-техника'
        }

        completed = set()
        for res in results:
            ex_type = res.get('exercise_type')
            if ex_type in exercises_map:
                completed.add(ex_type)

        for ex_type, name in exercises_map.items():
            if ex_type in completed:
                message += f"{name} ✅ Пройдено\n"
            else:
                message += f"{name} 🔘 Не начат\n"

        message += "\n📝 Последние записи:\n\n"
        
        for res in results[:5]:
            ex_type = res.get('exercise_type')
            name = exercises_map.get(ex_type, ex_type)
            data = res.get('result_data', {})
            
            if ex_type == 'stress_search':
                count = len(data.get('items', []))
                message += f"· {name}: {count} образов\n"
            elif ex_type == 'happiness_list':
                count = len(data.get('items', []))
                message += f"· {name}: {count} пунктов\n"
            elif ex_type == 'diary':
                if data.get('mood'):
                    message += f"· {name}: {data.get('mood')[:30]}\n"
            elif ex_type == 'stop_technique':
                message += f"· {name}: #{data.get('count', 1)}\n"
            else:
                message += f"· {name}: ✅\n"

        self.send_message(user_id, message, main_menu())

    def show_reminders(self, user_id):
        self.user_states[user_id] = 'reminders'
        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║        ⏰ НАПОМИНАНИЯ           ║\n"
            "╚══════════════════════════════════╝\n\n"
            "Ты можешь настроить напоминания:\n\n"
            "📖 Дневник — утреннее напоминание\n"
            "🛑 Стоп-техника — в течение дня\n"
            "📋 Любое упражнение — продолжить позже\n\n"
            "Выбери настройку:",
            get_reminder_keyboard()
        )