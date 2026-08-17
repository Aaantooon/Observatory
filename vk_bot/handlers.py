# vk_bot/handlers.py
from vk_api.utils import get_random_id
from api_client import APIClient
from keyboards import main_menu, exercises_menu
from exercises.stress_search import StressSearchExercise
from datetime import datetime
import re


class BotHandlers:
    def __init__(self, vk_session):
        self.vk = vk_session
        self.api = APIClient()
        self.user_states = {}
        self.stress_search = StressSearchExercise(vk_session, self.api)

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    def show_placeholder(self, user_id, exercise_name, emoji):
        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            f"║    {emoji} {exercise_name}            ║\n"
            "╚══════════════════════════════════╝\n\n"
            "🌫️ Это упражнение пока в тумане.\n"
            "· Скоро оно появится здесь ✨\n\n"
            "· А пока попробуй **«Поиск стресса»**\n"
            "· Свет фонарика уже ждёт тебя 🔥",
            main_menu()
        )

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
        if user_id in self.stress_search.user_sessions:
            self.stress_search.handle_message(user_id, text)
            return

        if user_id not in self.user_states:
            self.api.get_or_create_user(user_id, first_name, last_name)
            self.user_states[user_id] = 'main'
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║       🔦 ПУТЬ НАБЛЮДАТЕЛЯ      ║\n"
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
            if "упражн" in text_clean:
                self.show_exercises(user_id)
            elif "результат" in text_clean or "мои" in text_clean:
                self.show_results(user_id)
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
                return

            elif "список счастья" in text_clean or "счасть" in text_clean or text_clean == "2":
                self.show_placeholder(user_id, "Список счастья", "✨")
            elif "роли" in text_clean or text_clean == "3":
                self.show_placeholder(user_id, "Мои роли", "🎭")
            elif "осознанный выбор" in text_clean or "выбор" in text_clean or text_clean == "4":
                self.show_placeholder(user_id, "Осознанный выбор", "🧘")
            elif "дневник" in text_clean or text_clean == "5":
                self.show_placeholder(user_id, "Дневник", "📖")
            elif "стоп" in text_clean or text_clean == "6":
                self.show_placeholder(user_id, "Стоп-техника", "🛑")
            else:
                self.send_message(
                    user_id,
                    "🔦 Выбери упражнение из списка кнопок.",
                    exercises_menu()
                )

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
            f"{self._get_separator()}\n"
            "🔥 Нажми на кнопку, чтобы начать!"
        )

        self.send_message(user_id, message, exercises_menu())

    def _get_separator(self):
        return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

    def show_results(self, user_id):
        results = self.api.get_user_results(user_id)
        
        streak_info = self.api.update_streak(user_id)
        streak_text = ""
        if streak_info:
            streak = streak_info.get('streak', 0)
            if streak >= 365:
                streak_text = f"👑 **{streak}** дней! Ты легенда!"
            elif streak >= 100:
                streak_text = f"🔥 **{streak}** дней! Ты монстр!"
            elif streak >= 30:
                streak_text = f"🔥 **{streak}** дней! Круто!"
            elif streak >= 7:
                streak_text = f"🔥 **{streak}** дней! Отличная привычка!"
            elif streak >= 3:
                streak_text = f"🔥 **{streak}** дней! Так держать!"
            elif streak == 1:
                streak_text = f"🔥 **{streak}** день! Начинаем!"

        progress = self.api.get_progress(user_id, 'stress_search')
        stress_progress = None
        if progress and progress.get('exists'):
            data = progress.get('data', {})
            items = data.get('items', [])
            if items:
                stress_progress = {
                    'count': len(items),
                    'target': 100,
                    'phase': data.get('phase', 'collecting')
                }

        stress_completed = False
        for res in results:
            if res.get('exercise_title', '').lower() == 'поиск стресса':
                stress_completed = True
                break

        if not results and not stress_progress:
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║        🌫️ ПУТЬ ПУСТ            ║\n"
                "╚══════════════════════════════════╝\n\n"
                "· Твой путь ещё пуст\n"
                "· Начни с **«Поиска стресса»**\n"
                "· Свет фонарика уже ждёт тебя 🔥",
                main_menu()
            )
            return

        message = "╔══════════════════════════════════╗\n"
        message += "║        📊 МОЙ ПУТЬ              ║\n"
        message += "╚══════════════════════════════════╝\n\n"
        
        if streak_text:
            message += f"{streak_text}\n\n"

        message += "📋 **Образы в тумане:**\n\n"

        stress_status = "🔘 Не начат"
        stress_detail = ""
        
        if stress_completed:
            stress_status = "✅ Путь пройден"
            for res in results:
                if res.get('exercise_title', '').lower() == 'поиск стресса':
                    if res.get('result_data'):
                        if isinstance(res['result_data'], dict):
                            if 'total_count' in res['result_data']:
                                stress_detail = f" ({res['result_data']['total_count']} образов)"
                            elif 'items' in res['result_data']:
                                stress_detail = f" ({len(res['result_data']['items'])} образов)"
                    break
        elif stress_progress:
            count = stress_progress['count']
            phase = stress_progress['phase']
            stress_detail = f" ({count}/100 образов)"
            
            if phase == 'collecting':
                stress_status = "🔄 Собираем образы"
            elif phase == 'analysis':
                stress_status = "🔄 Разбираем путь"
            elif phase == 'question':
                stress_status = "🔄 Вглядываемся в туман"
            else:
                stress_status = "🔄 В пути"

        message += f"**1. Поиск стресса** {stress_status}{stress_detail}\n"

        exercise_names = [
            ("2. Список счастья", "✨"),
            ("3. Мои роли", "🎭"),
            ("4. Осознанный выбор", "🧘"),
            ("5. Дневник", "📖"),
            ("6. Стоп-техника", "🛑")
        ]
        
        for name, emoji in exercise_names:
            completed = False
            for res in results:
                title_lower = res.get('exercise_title', '').lower()
                clean_name = name.replace("2. ", "").replace("3. ", "").replace("4. ", "").replace("5. ", "").replace("6. ", "")
                if title_lower == clean_name.lower():
                    completed = True
                    break
            
            if completed:
                message += f"{name} ✅ Пройдено\n"
            else:
                message += f"{name} 🔘 Не начат\n"

        message += "\n"

        if results:
            message += "📝 **Разобранные образы:**\n\n"
            for i, res in enumerate(results[:10], 1):
                status = "✅ Освещён" if res.get('is_approved') else "⏳ В тумане"
                title = res.get('exercise_title', 'Упражнение')
                
                count_text = ""
                if res.get('result_data'):
                    if isinstance(res['result_data'], dict):
                        if 'items' in res['result_data']:
                            count = len(res['result_data']['items'])
                            count_text = f" ({count} образов)"
                        elif 'total_count' in res['result_data']:
                            count = res['result_data']['total_count']
                            count_text = f" ({count} образов)"
                
                message += f"{i}. {title}{count_text}\n"
                message += f"   {status}\n"
                
                completed_at = res.get('completed_at')
                if completed_at:
                    try:
                        dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        message += f"   📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
                    except:
                        pass
                message += "\n"

        self.send_message(user_id, message, main_menu())