from .base import BaseExercise
from keyboards import exercise_keyboard, finish_keyboard, back_keyboard, main_menu, continue_keyboard


class HappinessListExercise(BaseExercise):
    def get_exercise_type(self):
        return "happiness_list"

    def get_exercise_title(self):
        return "Список счастья"

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        self._start_new(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)

        items = []
        if progress and progress.get('data'):
            items = progress.get('data', {}).get('items', [])

        if items:
            self.user_sessions[user_id] = {'phase': 'continue', 'items': items}
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║       ✨ СПИСОК СЧАСТЬЯ        ║\n"
                "╚══════════════════════════════════╝\n\n"
                f"· Ты уже записал: **{len(items)}** пунктов\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        self._start_new(user_id)

    def _start_new(self, user_id):
        self.user_sessions[user_id] = {'phase': 'collecting', 'items': []}
        
        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║       ✨ СПИСОК СЧАСТЬЯ        ║\n"
            "╚══════════════════════════════════╝\n\n"
            "Давай вспомним, что приносит тебе радость.\n\n"
            "📝 Пиши по пунктам, что тебя радует, и ставь оценку от 1 до 10.\n"
            "Например:\n"
            "· Кофе утром — 8\n"
            "· Прогулка в парке — 9\n"
            "· Общение с друзьями — 10\n\n"
            "Нужно набрать до 20 пунктов.\n"
            "Ты можешь завершить в любой момент — я сохраню прогресс.\n\n"
            "✏️ Напиши первый пункт и оценку:",
            exercise_keyboard()
        )

    def _show_items(self, user_id, items):
        message = "📋 **Твой список счастья:**\n\n"
        for i, item in enumerate(items, 1):
            message += f"{i}. {item.get('text')} — {item.get('score')}/10\n"
        
        message += f"\nВсего: {len(items)}/20 пунктов\n\n"
        message += "✏️ Продолжай добавлять или нажми «Завершить»."
        
        self.send_message(user_id, message, exercise_keyboard())

    def handle_message(self, user_id, text):
        session = self.user_sessions.get(user_id)
        if not session:
            self.start(user_id)
            return

        text_lower = text.lower().strip()

        if "продолжи" in text_lower:
            self._show_items(user_id, session.get('items', []))
            return

        if "заново" in text_lower:
            self._handle_start_over(user_id)
            return

        if text_lower in ["отмена", "❌ отмена", "cancel", "сохранить и выйти", "💾 сохранить и выйти"]:
            self._handle_cancel(user_id, session)
            return

        if text_lower in ["стоп", "⏹️ стоп", "завершить", "✅ завершить"]:
            self._finish(user_id, session)
            return

        if session.get('phase') == 'collecting' or session.get('phase') == 'continue':
            self._handle_item(user_id, text, session)

    def _handle_item(self, user_id, text, session):
        parts = text.rsplit(' ', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            self.send_message(
                user_id,
                "❌ Формат: `Что радует — 9` (число от 1 до 10)\n"
                "Пример: `Кофе утром — 8`",
                exercise_keyboard()
            )
            return

        score = int(parts[1])
        if not (1 <= score <= 10):
            self.send_message(
                user_id,
                "❌ Оценка должна быть от 1 до 10",
                exercise_keyboard()
            )
            return

        item_text = parts[0].strip()
        session['items'].append({'text': item_text, 'score': score})
        
        self.save_progress(user_id, {'items': session['items']})

        count = len(session['items'])
        
        if count >= 20:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} пунктов счастья!\n"
                "Нажми «Завершить» чтобы сохранить результат.",
                finish_keyboard()
            )
        else:
            self.send_message(
                user_id,
                f"✅ Добавлено! {count}/20\n\n"
                f"📌 {item_text} — {score}/10\n\n"
                "Продолжай или нажми «Завершить»",
                exercise_keyboard()
            )

    def _finish(self, user_id, session):
        items = session.get('items', [])
        if not items:
            self.send_message(
                user_id,
                "❌ Список пуст. Добавь хотя бы один пункт.",
                exercise_keyboard()
            )
            return

        self.save_result(user_id, {'items': items, 'total': len(items)})
        self.delete_progress(user_id)
        self.end_session(user_id)

        avg_score = sum(i['score'] for i in items) / len(items)

        self.send_message(
            user_id,
            f"╔══════════════════════════════════╗\n"
            f"║        ✨ ПУТЬ ЗАВЕРШЁН         ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"📋 Собрано: {len(items)} пунктов счастья\n"
            f"📊 Средняя оценка: {avg_score:.1f}/10\n\n"
            f"Топ-3:\n" + "\n".join(
                f"  · {i['text']} ({i['score']}/10)" 
                for i in sorted(items, key=lambda x: x['score'], reverse=True)[:3]
            ) + "\n\n✨ Сохраняй этот список и дополняй!",
            main_menu()
        )

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, {'items': session.get('items', [])})
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Прогресс сохранён\n"
            "Возвращайся, чтобы продолжить ✨",
            main_menu()
        )