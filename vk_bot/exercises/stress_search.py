# vk_bot/exercises/stress_search.py
import random
import logging
from vk_api.utils import get_random_id
from keyboards import main_menu, exercise_keyboard, analysis_keyboard, cancel_keyboard, continue_keyboard

logger = logging.getLogger(__name__)


class StressSearchExercise:
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

    def _get_progress_bar(self, count, target=100):
        percent = min(100, int((count / target) * 100))
        filled = "▰" * (percent // 5)
        empty = "▱" * (20 - len(filled))
        return f"▰{filled}{empty}▱ {percent}%"

    def _get_separator(self):
        return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

    def _save_progress(self, user_id, session):
        data = {
            'items': session.get('items', []),
            'phase': session.get('phase', 'collecting'),
            'question_index': session.get('question_index', 0),
            'question_step': session.get('question_step', 1),
            'answers': session.get('answers', []),
            'current_item': session.get('current_item', {})
        }
        self.api.save_progress(user_id, 'stress_search', data)

    def _load_progress(self, user_id):
        progress = self.api.get_progress(user_id, 'stress_search')
        if progress and progress.get('exists'):
            data = progress.get('data', {})
            return {
                'items': data.get('items', []),
                'phase': data.get('phase', 'collecting'),
                'question_index': data.get('question_index', 0),
                'question_step': data.get('question_step', 1),
                'answers': data.get('answers', []),
                'current_item': data.get('current_item', {})
            }
        return None

    def _delete_progress(self, user_id):
        self.api.delete_progress(user_id, 'stress_search')

    def _handle_cancel(self, user_id, session):
        self._save_progress(user_id, session)
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        self.send_message(
            user_id,
            "🌫️ **Туман сгущается...**\n\n"
            "· Ты сохранил свой путь\n"
            "· Фонарик ждёт тебя, чтобы продолжить\n\n"
            "✨ Возвращайся, когда будешь готов",
            main_menu()
        )
        return True

    def _handle_start_over(self, user_id):
        self._delete_progress(user_id)
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        self.user_sessions[user_id] = {
            'items': [],
            'phase': 'collecting',
            'question_index': 0,
            'question_step': 1,
            'answers': [],
            'current_item': {}
        }
        
        self._send_intro(user_id)

    def start(self, user_id):
        saved = self._load_progress(user_id)
        if saved and len(saved.get('items', [])) > 0:
            self.user_sessions[user_id] = saved
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║       🔦 СВЕТ В ТУМАНЕ          ║\n"
                "╚══════════════════════════════════╝\n\n"
                f"· Ты уже записал: **{len(saved['items'])}** образов\n"
                f"· Текущая точка: {self._get_phase_text(saved['phase'])}\n\n"
                "🕯️ Продолжим путь?",
                continue_keyboard()
            )
            return

        self.user_sessions[user_id] = {
            'items': [],
            'phase': 'collecting',
            'question_index': 0,
            'question_step': 1,
            'answers': [],
            'current_item': {}
        }
        self._send_intro(user_id)

    def _get_phase_text(self, phase):
        if phase == 'collecting':
            return "🌫️ Собираем образы"
        elif phase == 'analysis':
            return "🧠 Вглядываемся в туман"
        elif phase == 'question':
            return "🔍 Разбираем путь"
        return "Неизвестно"

    def _send_intro(self, user_id):
        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║       🎯 ПОИСК СТРЕССА          ║\n"
            "║       ПУТЬ НАБЛЮДАТЕЛЯ          ║\n"
            "╚══════════════════════════════════╝\n\n"
            "🌫️ *Цель:* найти источники стресса в своей жизни.\n\n"
            "📖 **Формула стресса:**\n"
            "`Стресс = Прогноз ≠ Реальность`\n\n"
            "🕯️ **Часть 1: Собираем образы**\n"
            "· Что вызывает напряжение?\n"
            "· Что забирает энергию?\n"
            "· Запиши это и поставь оценку от 1 до 10\n\n"
            "📌 **Пример:** `Работа 8`\n\n"
            f"{self._get_separator()}\n"
            "⏹️ **«Стоп»** — перейти к разбору\n"
            "✅ **«Завершить»** — завершить путь",
            exercise_keyboard()
        )

    def handle_message(self, user_id, text):
        session = self.user_sessions.get(user_id)
        
        if not session:
            self.start(user_id)
            return

        text_lower = text.lower().strip()

        if "продолжи" in text_lower:
            self._restore_progress(user_id, session)
            return

        if "заново" in text_lower:
            self._handle_start_over(user_id)
            return

        if text_lower in ["отмена", "❌ отмена", "cancel", "сохранить и выйти", "💾 сохранить и выйти"]:
            self._handle_cancel(user_id, session)
            return

        phase = session.get('phase')
        
        if phase == 'collecting':
            self.handle_collect(user_id, text.strip(), session)
        elif phase == 'analysis':
            self.handle_analysis(user_id, text.strip(), session)
        elif phase == 'question':
            self.handle_question(user_id, text.strip(), session)

    def _restore_progress(self, user_id, session):
        phase = session.get('phase')
        if phase == 'collecting':
            count = len(session.get('items', []))
            progress = self._get_progress_bar(count, target=100)
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║       🔦 ПРОДОЛЖАЕМ ПУТЬ        ║\n"
                "╚══════════════════════════════════╝\n\n"
                f"· Уже записано: {count} образов\n"
                f"· {progress}\n\n"
                "🕯️ Продолжай или нажми **«Стоп»**.",
                exercise_keyboard()
            )
        elif phase == 'analysis':
            session['phase'] = 'question'
            session['question_index'] = 0
            session['answers'] = []
            self._start_analysis(user_id, session)
        elif phase == 'question':
            self._show_current_question(user_id, session)

    def handle_collect(self, user_id, text, session):
        self._save_progress(user_id, session)

        if text.lower() in ["стоп", "⏹️ стоп"]:
            if len(session['items']) == 0:
                self.send_message(
                    user_id,
                    "╔══════════════════════════════════╗\n"
                    "║        🌫️ ТУМАН ПУСТ            ║\n"
                    "╚══════════════════════════════════╝\n\n"
                    "· Запиши хотя бы один образ\n"
                    "· 📌 **Формат:** `Причина 9`\n\n"
                    "💾 **«Сохранить и выйти»**",
                    cancel_keyboard()
                )
                return
            
            session['phase'] = 'analysis'
            self._save_progress(user_id, session)
            self._start_analysis(user_id, session)
            return

        if text.lower() in ["завершить", "✅ завершить"]:
            if len(session['items']) == 0:
                self.send_message(
                    user_id,
                    "╔══════════════════════════════════╗\n"
                    "║        🌫️ ТУМАН ПУСТ            ║\n"
                    "╚══════════════════════════════════╝\n\n"
                    "· Запиши хотя бы один образ\n"
                    "· 📌 **Формат:** `Причина 9`\n\n"
                    "💾 **«Сохранить и выйти»**",
                    cancel_keyboard()
                )
                return
            self._finish_exercise(user_id, session)
            return

        parts = text.rsplit(' ', 1)
        if len(parts) != 2:
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║     🌫️ ОБРАЗ НЕ ПРОЯВИЛСЯ      ║\n"
                "╚══════════════════════════════════╝\n\n"
                "· Нужно: `Причина 9` (слово + пробел + оценка)\n"
                "· 📌 **Пример:** `Работа 8`\n\n"
                "💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )
            return

        if not parts[1].isdigit():
            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║    🌫️ НЕВЕРНАЯ ОЦЕНКА          ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"· Оценка должна быть числом от 1 до 10\n"
                f"· Ты написал: `{parts[1]}`\n\n"
                f"· 📌 **Пример:** `Работа 8`\n\n"
                f"💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )
            return

        rate = int(parts[1])
        if not (1 <= rate <= 10):
            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║    🌫️ ОЦЕНКА ВНЕ ДИАПАЗОНА    ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"· Оценка должна быть от 1 до 10\n"
                f"· Ты поставил: `{rate}`\n\n"
                f"💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )
            return

        item = parts[0].strip()
        session['items'].append({'text': item, 'rate': rate})
        count = len(session['items'])

        replies = [
            "🔦 Ты заметил образ. Он больше не в тумане.",
            "🕯️ Свет фонарика выхватывает ещё один.",
            "🌫️ Образ проявился. Ты его видишь.",
            "✨ Ещё один фрагмент карты прояснился.",
            "👁️ Ты разглядел. Хорошо.",
            "📝 Образ записан. Путь становится яснее."
        ]
        reply = random.choice(replies)

        progress = self._get_progress_bar(count, target=100)

        self.send_message(
            user_id,
            f"╔══════════════════════════════════╗\n"
            f"║       🔦 ОБРАЗ #{count}            ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"📌 *«{item}»* — {rate}/10\n\n"
            f"· {progress}\n\n"
            f"{reply}\n\n"
            f"{self._get_separator()}\n"
            f"· Продолжай или нажми **«Стоп»**",
            exercise_keyboard()
        )

        self._save_progress(user_id, session)

    def _start_analysis(self, user_id, session):
        items = session.get('items', [])
        
        if len(items) == 0:
            self.send_message(
                user_id,
                "🌫️ **Туман пуст...**\n"
                "· Запиши хотя бы один образ",
                exercise_keyboard()
            )
            return

        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║       🧠 РАЗБОР ПУТИ            ║\n"
            "╚══════════════════════════════════╝\n\n"
            f"· У тебя **{len(items)}** образов\n\n"
            "· Теперь будем разбирать каждый\n"
            "· Ты увидишь, где твоя карта расходится с реальностью\n\n"
            f"{self._get_separator()}\n"
            "➡️ Нажми **«Далее»**, чтобы начать",
            analysis_keyboard()
        )

    def handle_analysis(self, user_id, text, session):
        if text.lower() in ["завершить", "✅ завершить"]:
            self._finish_exercise(user_id, session)
            return

        if text.lower() in ["далее", "➡️ далее"]:
            self._show_current_question(user_id, session)
        else:
            self.send_message(
                user_id,
                "➡️ Нажми **«Далее»**\n"
                "✅ **«Завершить»** — завершить путь",
                analysis_keyboard()
            )

    def _show_current_question(self, user_id, session):
        index = session.get('question_index', 0)
        items = session.get('items', [])

        if not items or index >= len(items):
            self._finish_exercise(user_id, session)
            return

        item = items[index]
        session['current_item'] = item
        session['question_step'] = 1
        
        if 'answers' not in session:
            session['answers'] = []
        session['answers'].append({
            'text': item['text'], 
            'rate': item['rate']
        })

        self.send_message(
            user_id,
            f"╔══════════════════════════════════╗\n"
            f"║    🔦 ОБРАЗ {index + 1}/{len(items)}          ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"📌 *«{item['text']}»* — {item['rate']}/10\n\n"
            f"❓ **Вопрос 1/4:**\n"
            f"· Как должно быть? Опиши идеальную ситуацию.\n\n"
            f"{self._get_separator()}\n"
            f"💾 **«Сохранить и выйти»**",
            cancel_keyboard()
        )
        
        session['phase'] = 'question'
        self._save_progress(user_id, session)

    def handle_question(self, user_id, text, session):
        text_lower = text.lower().strip()

        if text_lower in ["отмена", "❌ отмена", "cancel", "сохранить и выйти", "💾 сохранить и выйти"]:
            self._handle_cancel(user_id, session)
            return

        self._save_progress(user_id, session)

        step = session.get('question_step', 1)
        answers = session.get('answers', [])
        current_answer = answers[-1] if answers else {}

        current_item = session.get('current_item', {})
        item_text = current_item.get('text', '')
        item_rate = current_item.get('rate', '')
        total = len(session.get('items', []))
        index = session.get('question_index', 0)

        if step == 1:
            current_answer['ideal'] = text
            session['question_step'] = 2

            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║    🔦 ОБРАЗ {index + 1}/{total}          ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"📌 *«{item_text}»* — {item_rate}/10\n\n"
                f"❓ **Вопрос 2/4:**\n"
                f"· На сколько процентов это реально?\n"
                f"· Напиши число от 0 до 100\n\n"
                f"💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )

        elif step == 2:
            if not text.isdigit():
                self.send_message(
                    user_id,
                    "❌ Напиши число от 0 до 100 (только цифры)",
                    cancel_keyboard()
                )
                return

            percent = int(text)
            if not (0 <= percent <= 100):
                self.send_message(
                    user_id,
                    "❌ Число должно быть от 0 до 100",
                    cancel_keyboard()
                )
                return

            current_answer['percent'] = percent
            session['question_step'] = 3

            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║    🔦 ОБРАЗ {index + 1}/{total}          ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"📌 *«{item_text}»* — {item_rate}/10\n"
                f"· 📊 Реалистичность: {percent}%\n\n"
                f"❓ **Вопрос 3/4:**\n"
                f"· Почему так должно быть?\n"
                f"· Объясни\n\n"
                f"💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )

        elif step == 3:
            current_answer['why'] = text
            session['question_step'] = 4

            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║    🔦 ОБРАЗ {index + 1}/{total}          ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"📌 *«{item_text}»* — {item_rate}/10\n"
                f"· 📊 Реалистичность: {current_answer.get('percent', '?')}%\n\n"
                f"❓ **Вопрос 4/4:**\n\n"
                f"· «Ты — пуп земли и пуп вселенной.\n"
                f"· И всё должно быть по-твоему?»\n\n"
                f"· Это нормально так думать 😊\n\n"
                f"· Важно сформулировать:\n"
                f"  · **Как** должно быть?\n"
                f"  · **Почему**?\n"
                f"  · **На сколько %** это реально?\n\n"
                f"· Напиши свои размышления\n\n"
                f"💾 **«Сохранить и выйти»**",
                cancel_keyboard()
            )

        elif step == 4:
            current_answer['reflection'] = text
            session['question_step'] = 0

            self._save_progress(user_id, session)

            session['question_index'] += 1
            
            if session['question_index'] >= len(session.get('items', [])):
                self._finish_exercise(user_id, session)
            else:
                self._show_current_question(user_id, session)

    def _finish_exercise(self, user_id, session):
        result_data = {
            'type': 'stress_search',
            'items': session.get('items', []),
            'analysis': session.get('answers', []),
            'total_count': len(session.get('items', []))
        }

        exercise_id = 1
        self.api.save_result(user_id, exercise_id, result_data)

        self._delete_progress(user_id)

        streak_info = self.api.update_streak(user_id)
        streak_text = ""
        if streak_info:
            streak = streak_info.get('streak', 0)
            if streak >= 365:
                streak_text = f"\n· 👑 Серия: **{streak}** дней! Ты легенда!"
            elif streak >= 100:
                streak_text = f"\n· 🔥 Серия: **{streak}** дней! Ты монстр!"
            elif streak >= 30:
                streak_text = f"\n· 🔥 Серия: **{streak}** дней! Круто!"
            elif streak >= 7:
                streak_text = f"\n· 🔥 Серия: **{streak}** дней! Отличная привычка!"
            elif streak >= 3:
                streak_text = f"\n· 🔥 Серия: **{streak}** дней! Так держать!"
            else:
                streak_text = f"\n· 🔥 Серия: **{streak}** день! Начинаем!"

        total = len(session.get('items', []))
        top = sorted(session.get('items', []), key=lambda x: x['rate'], reverse=True)[:3]
        top_text = "\n".join([f"  · {b['text']} ({b['rate']}/10)" for b in top])

        analyzed = len(session.get('answers', []))
        avg_percent = 0
        if analyzed > 0:
            avg_percent = sum(a.get('percent', 0) for a in session.get('answers', [])) // analyzed

        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║        ✨ ПУТЬ ЗАВЕРШЁН         ║\n"
            "╚══════════════════════════════════╝\n\n"
            f"· 🔦 Ты осветил **{total}** образов в тумане\n"
            f"· 🧠 Разобрано: **{analyzed}**\n"
            f"· 📊 Реалистичность твоей карты: **{avg_percent}%**"
            f"{streak_text}\n\n"
            f"{self._get_separator()}\n"
            f"🔥 **Топ-3 образа:**\n{top_text}\n\n"
            f"{self._get_separator()}\n"
            f"📖 **Формула стресса:**\n"
            f"`Стресс = Прогноз ≠ Реальность`\n\n"
            f"🌫️ Ты сделал шаг к ясности\n"
            f"· Карта становится точнее\n"
            f"· Туман рассеивается\n\n"
            f"✨ Береги себя ❤️",
            main_menu()
        )

        if user_id in self.user_sessions:
            del self.user_sessions[user_id]