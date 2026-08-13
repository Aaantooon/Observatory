from vk_api.utils import get_random_id
from keyboards import main_menu, cancel_keyboard

class BesilkiExercise:
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.user_sessions = {}

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    # ФИШКА 1: Визуальный прогресс-бар (палочки)
    def _get_progress_bar(self, count, target=2):
        filled = "🟩" * min(count, target)
        empty = "⬜" * max(0, target - count)
        return f"{filled}{empty} {count}/{target}"

    def start(self, user_id):
        self.user_sessions[user_id] = {'step': 'collect_besilki', 'besilki': []}
        self.send_message(
            user_id,
            "🔥 **Упражнение «Бесилки»**\n\n"
            "🧠 Это упражнение помогает выявить, что именно тебя раздражает.\n"
            "Честность здесь — лучший друг!\n\n"
            "📝 **Правила очень простые:**\n"
            "1️⃣ Пиши, что тебя бесит.\n"
            "2️⃣ Ставь оценку от 1 до 10 (где 10 — *это просто выбешивает до невозможности*).\n"
            "3️⃣ Напиши минимум 2 пункта.\n\n"
            "📌 **Пример:**\n"
            "`Пробки по утрам 9`\n"
            "`Громкий сосед 6`\n\n"
            "✨ Когда закончишь — просто напиши **«Стоп»**.\n"
            "Чтобы выйти в любой момент — нажми кнопку **«Отмена»**.",
            cancel_keyboard()
        )

    def handle_message(self, user_id, text):
        session = self.user_sessions.get(user_id)
        if not session or session['step'] != 'collect_besilki':
            return
        self.handle_collect(user_id, text.strip(), session)

    def handle_collect(self, user_id, text, session):
        # 1. Мгновенный выход по кнопке и синонимам отмены
        if text in ["Отмена", "отмена", "Выйти", "выйти", "/cancel"]:
            del self.user_sessions[user_id]
            self.send_message(
                user_id,
                "🚪 **Выход выполнен.**\n"
                "Ты всегда можешь вернуться, когда будешь готов! 👋",
                main_menu()
            )
            return

        # 2. Завершение упражнения (поддержка синонимов)
        if text.lower() in ("стоп", "закончить", "хватит", "всё", "готово", "завершить", "done"):
            if len(session['besilki']) < 2:
                self.send_message(
                    user_id,
                    f"⚠️ **Пока маловато.** Нужно минимум 2 пункта.\n"
                    f"Сейчас у тебя: {len(session['besilki'])}. Напиши ещё что-нибудь, что бесит!\n\n"
                    f"Или нажми «Отмена», если передумал.",
                    cancel_keyboard()
                )
                return
            self.finish_exercise(user_id, session)
            return

        # 3. ФИШКА 2: Проверка на пустые или бессмысленные сообщения
        if not text:
            self.send_message(
                user_id,
                "🙃 Сообщение не может быть пустым. Напиши в формате:\n"
                "`Причина 9` (слово + пробел + оценка).",
                cancel_keyboard()
            )
            return

        # 4. ФИШКА 3: Форматирование и защита (если в конце цифра)
        parts = text.rsplit(' ', 1)
        
        if len(parts) != 2:
            self.send_message(
                user_id,
                "❌ **Ошибка формата.**\n"
                "Ты забыл поставить пробел перед оценкой!\n"
                "Правильно: `Раздражитель 8`\n"
                "Неправильно: `Раздражитель8` или `Раздражитель`\n\n"
                "Попробуй ещё раз или нажми «Отмена».",
                cancel_keyboard()
            )
            return

        if not parts[1].isdigit():
            self.send_message(
                user_id,
                "❌ **Ошибка.**\n"
                "В конце должно быть число от 1 до 10.\n"
                "Ты написал: `{}`\n\n"
                "Попробуй ещё раз или нажми «Отмена».".format(parts[1]),
                cancel_keyboard()
            )
            return

        rate = int(parts[1])
        if not (1 <= rate <= 10):
            self.send_message(
                user_id,
                "❌ Оценка должна быть **от 1 до 10**!\n"
                "Ты поставил `{}`.\n"
                "Попробуй исправить.".format(rate),
                cancel_keyboard()
            )
            return

        # 5. ВСЁ ОТЛИЧНО! Сохраняем запись
        besilka = parts[0].strip()
        session['besilki'].append({'text': besilka, 'rate': rate})
        count = len(session['besilki'])

        # ФИШКА 4: Приятные реплики-мотиваторы при каждом вводе
        if count == 1:
            reply = "🔥 Отлично, поехали! Добавим ещё один?"
        elif count == 2:
            reply = "✅ Вот и второй! Молодец! Можно останавливаться, если хочешь."
        elif count >= 3:
            replies = [
                "🧘 Продолжаем выпускать пар...",
                "💪 Отлично, копится!",
                "✨ Ты молодец, что проговариваешь это.",
                "👌 Хороший список получается!"
            ]
            import random
            reply = random.choice(replies)

        # Визуальный прогресс
        progress = self._get_progress_bar(count)

        self.send_message(
            user_id,
            f"✅ **{count}. {besilka} — {rate}/10**\n"
            f"Прогресс: {progress}\n\n"
            f"{reply}\n"
            f"Напиши **«Стоп»**, если этого достаточно, или продолжай.",
            cancel_keyboard()
        )

    def finish_exercise(self, user_id, session):
        result_data = {'type': 'besilki', 'besilki': session['besilki']}
        exercise_id = 7  # ID для базы данных
        self.api.save_result(user_id, exercise_id, result_data)

        # ФИШКА 5: Красивое эмоциональное завершение
        total_besilki = len(session['besilki'])
        top_anger = sorted(session['besilki'], key=lambda x: x['rate'], reverse=True)[:3]
        
        top_text = "\n".join([f"• {b['text']} ({b['rate']}/10)" for b in top_anger])

        self.send_message(
            user_id,
            f"🎉 **Упражнение «Бесилки» завершено!**\n\n"
            f"📊 Ты выпустил пар аж по **{total_besilki}** поводам! 🫧\n"
            f"Твой топ-3 раздражителей на сегодня:\n"
            f"{top_text}\n\n"
            
            f"🧠 Дыши глубже. Осознать проблему — это уже половина решения.\n"
            f"Береги себя ❤️",
            main_menu()
        )
        del self.user_sessions[user_id]