from .base import BaseExercise
from keyboards import exercise_keyboard, finish_keyboard, back_keyboard, main_menu, continue_keyboard


class StopTechniqueExercise(BaseExercise):
    def get_exercise_type(self):
        return "stop_technique"

    def get_exercise_title(self):
        return "Стоп-техника"

    def _fresh_session(self):
        return {
            'phase': 'thoughts',
            'thoughts': '',
            'feelings': '',
            'wants': '',
            'completed': False,
            'count': 0
        }

    def _handle_start_over(self, user_id, prev_count=0):
        self.delete_progress(user_id)
        session = self._fresh_session()
        session['count'] = prev_count + 1
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and (
            data.get('thoughts') or data.get('feelings') or data.get('wants') or
            (data.get('phase') and data.get('phase') != 'thoughts')
        ))

        if has_saved:
            session = self._fresh_session()
            session.update(data)
            self.user_sessions[user_id] = session

            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║     🛑 СТОП-ТЕХНИКА             ║\n"
                "╚══════════════════════════════════╝\n\n"
                "· У тебя есть незаконченная остановка\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        session['count'] = 1
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    def _show_phase(self, user_id, session):
        count = session.get('count', 0)

        phase = session.get('phase')
        
        if phase == 'thoughts':
            self.send_message(
                user_id,
                f"╔══════════════════════════════════╗\n"
                f"║     🛑 СТОП-ТЕХНИКА #{count}     ║\n"
                f"╚══════════════════════════════════╝\n\n"
                f"**Вопрос 1/3: О чём я думаю?**\n\n"
                f"Здесь и сейчас.\n\n"
                f"Примеры:\n"
                f"· Устал как собака\n"
                f"· Думаю о вкусном ужине\n"
                f"· Мысли о работе\n\n"
                f"✏️ Напиши, о чём думаешь:",
                exercise_keyboard()
            )
        
        elif phase == 'feelings':
            self.send_message(
                user_id,
                f"**Вопрос 2/3: Что я сейчас чувствую?**\n\n"
                f"Примеры:\n"
                f"· Усталость\n"
                f"· Радость\n"
                f"· Тревога\n"
                f"· Спокойствие\n\n"
                f"✏️ Напиши свои чувства:",
                exercise_keyboard()
            )
        
        elif phase == 'wants':
            self.send_message(
                user_id,
                f"**Вопрос 3/3: Чего я сейчас хочу?**\n\n"
                f"Примеры:\n"
                f"· Сходить купить что-нибудь вкусное\n"
                f"· Лечь и посмотреть сериал\n"
                f"· Пойти на прогулку\n\n"
                f"✏️ Напиши, чего хочешь:",
                exercise_keyboard()
            )

    def handle_message(self, user_id, text):
        session = self.user_sessions.get(user_id)
        if not session:
            self.start(user_id)
            return

        text_lower = text.lower().strip()

        if "продолжи" in text_lower:
            self._show_phase(user_id, session)
            return

        if "заново" in text_lower:
            self._handle_start_over(user_id, session.get('count', 0))
            return

        if text_lower in ["отмена", "❌ отмена", "cancel", "сохранить и выйти", "💾 сохранить и выйти"]:
            self._handle_cancel(user_id, session)
            return

        if text_lower in ["стоп", "⏹️ стоп", "завершить", "✅ завершить"]:
            self._next_phase(user_id, session)
            return

        phase = session.get('phase')
        
        if phase == 'thoughts':
            session['thoughts'] = text
            session['phase'] = 'feelings'
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)
        
        elif phase == 'feelings':
            session['feelings'] = text
            session['phase'] = 'wants'
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)
        
        elif phase == 'wants':
            session['wants'] = text
            session['phase'] = 'complete'
            session['completed'] = True
            self.save_progress(user_id, session)
            self._finish(user_id, session)

    def _next_phase(self, user_id, session):
        phase = session.get('phase')
        
        if phase == 'thoughts' and not session.get('thoughts'):
            self.send_message(
                user_id,
                "❌ Напиши, о чём думаешь",
                exercise_keyboard()
            )
            return
        elif phase == 'feelings' and not session.get('feelings'):
            self.send_message(
                user_id,
                "❌ Напиши свои чувства",
                exercise_keyboard()
            )
            return
        elif phase == 'wants' and not session.get('wants'):
            self.send_message(
                user_id,
                "❌ Напиши, чего хочешь",
                exercise_keyboard()
            )
            return
        
        self._next_phase_forced(user_id, session)

    def _next_phase_forced(self, user_id, session):
        phase = session.get('phase')
        
        if phase == 'thoughts':
            session['phase'] = 'feelings'
        elif phase == 'feelings':
            session['phase'] = 'wants'
        elif phase == 'wants':
            session['phase'] = 'complete'
            session['completed'] = True
            self.save_progress(user_id, session)
            self._finish(user_id, session)
            return
        
        self.save_progress(user_id, session)
        self._show_phase(user_id, session)

    def _finish(self, user_id, session):
        result = {
            'thoughts': session.get('thoughts'),
            'feelings': session.get('feelings'),
            'wants': session.get('wants'),
            'count': session.get('count', 0)
        }
        
        self.save_result(user_id, result)
        self.delete_progress(user_id)
        self.end_session(user_id)

        count = session.get('count', 0)

        self.send_message(
            user_id,
            f"╔══════════════════════════════════╗\n"
            f"║        ✨ СТОП #{count}           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💭 **Мысли:** {result['thoughts']}\n\n"
            f"❤️ **Чувства:** {result['feelings']}\n\n"
            f"🎯 **Хочу:** {result['wants']}\n\n"
            f"🛑 Ты остановился и осознал момент.\n"
            f"Это уже победа ✨\n\n"
            f"Хочешь сделать ещё одну остановку?\n"
            f"Нажми «Упражнения» → «Стоп-техника»",
            main_menu()
        )

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, session)
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Прогресс сохранён\n"
            "Возвращайся, чтобы продолжить ✨",
            main_menu()
        )