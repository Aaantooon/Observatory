from .base import BaseExercise
from keyboards import (
    step_nav_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    BACK_TEXTS, TO_START_TEXTS, TO_END_TEXTS,
)


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
            'count': 0,
            '_max_phase_index': 0,
        }

    def _handle_start_over(self, user_id, prev_count=0):
        self.delete_progress(user_id)
        session = self._fresh_session()
        session['count'] = prev_count + 1
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    def _handle_save_and_start_over(self, user_id, session):
        prev_count = session.get('count', 0)

        has_content = bool(
            session.get('thoughts') or session.get('feelings') or session.get('wants')
        )
        if not has_content:
            # Нечего сохранять — ни на один из 3 вопросов ещё не ответили.
            # Раньше это всё равно уходило в _finish() и создавало на
            # сервере пустую "остановку" без единого слова.
            self.send_message(
                user_id,
                "🌫️ Пока нечего сохранять — ты ещё не ответил(а) ни на один вопрос. Начинаем заново."
            )
            self._handle_start_over(user_id, prev_count)
            return

        if not self._finish(user_id, session):
            # _finish() уже сообщил о сбое и сохранил текущие ответы как
            # черновик прогресса (см. _report_save_failure) — раньше сюда
            # заходили безусловно и следующей же строкой удаляли этот самый
            # черновик и открывали пустую сессию, теряя ответы насовсем.
            return

        self._handle_start_over(user_id, prev_count)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        if progress is None:
            self._progress_unavailable_notice(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and (
            data.get('thoughts') or data.get('feelings') or data.get('wants') or
            (data.get('phase') and data.get('phase') != 'thoughts')
        ))

        if has_saved:
            session = self._fresh_session()
            session.update(data)
            session['_max_phase_index'] = max(
                session.get('_max_phase_index', 0), self._phase_index(session.get('phase'))
            )
            session['_resume_prompt'] = True
            self.user_sessions[user_id] = session

            self.send_message(
                user_id,
                "🛑 СТОП-ТЕХНИКА\n\n"
                "· У тебя есть незаконченная остановка\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        session['count'] = 1
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    PHASES_ORDER = ['thoughts', 'feelings', 'wants']

    def _phase_index(self, phase):
        return self.PHASES_ORDER.index(phase) if phase in self.PHASES_ORDER else len(self.PHASES_ORDER) - 1

    def _bump_max_phase(self, session):
        idx = self._phase_index(session.get('phase'))
        if idx > session.get('_max_phase_index', 0):
            session['_max_phase_index'] = idx

    def _existing_answer_note(self, value):
        if not value:
            return ""
        return f"📝 Текущий ответ: «{value}»\n(напиши новый, чтобы заменить)\n\n"

    def _show_phase(self, user_id, session):
        count = session.get('count', 0)

        phase = session.get('phase')
        step_num = self._phase_index(phase) + 1
        progress = self._get_progress_bar(step_num, target=len(self.PHASES_ORDER))
        note = self._existing_answer_note(session.get(phase))

        if phase == 'thoughts':
            self.send_message(
                user_id,
                f"🛑 СТОП-ТЕХНИКА #{count}\n\n"
                f"Вопрос 1/3: О чём я думаю?\n"
                f"{progress}\n\n"
                f"{note}"
                f"Здесь и сейчас.\n\n"
                f"Примеры:\n"
                f"· Устал как собака\n"
                f"· Думаю о вкусном ужине\n"
                f"· Мысли о работе\n\n"
                f"✏️ Напиши, о чём думаешь:",
                step_nav_keyboard()
            )

        elif phase == 'feelings':
            self.send_message(
                user_id,
                f"Вопрос 2/3: Что я сейчас чувствую?\n"
                f"{progress}\n\n"
                f"{note}"
                f"Примеры:\n"
                f"· Усталость\n"
                f"· Радость\n"
                f"· Тревога\n"
                f"· Спокойствие\n\n"
                f"✏️ Напиши свои чувства:",
                step_nav_keyboard()
            )

        elif phase == 'wants':
            self.send_message(
                user_id,
                f"Вопрос 3/3: Чего я сейчас хочу?\n"
                f"{progress}\n\n"
                f"{note}"
                f"Примеры:\n"
                f"· Сходить купить что-нибудь вкусное\n"
                f"· Лечь и посмотреть сериал\n"
                f"· Пойти на прогулку\n\n"
                f"✏️ Напиши, чего хочешь:",
                step_nav_keyboard()
            )

    def handle_message(self, user_id, text):
        session = self.user_sessions.get(user_id)
        if not session:
            self.start(user_id)
            return

        text_lower = text.lower().strip()

        if text_lower in SAVE_AND_RESTART_TEXTS:
            self._handle_save_and_start_over(user_id, session)
            return

        if session.get('_resume_prompt'):
            if text_lower in CONTINUE_TEXTS:
                session.pop('_resume_prompt', None)
                self._show_phase(user_id, session)
                return
            if text_lower in RESTART_TEXTS:
                self._handle_start_over(user_id, session.get('count', 0))
                return
            self.send_message(
                user_id,
                "🕯️ Нажми «Продолжить ✅» или «Начать заново 🔄».",
                continue_keyboard()
            )
            return

        if text_lower in RESTART_TEXTS:
            self._handle_start_over(user_id, session.get('count', 0))
            return

        if text_lower in CANCEL_TEXTS:
            self._handle_cancel(user_id, session)
            return

        if text_lower in BACK_TEXTS:
            self._handle_back(user_id, session)
            return

        if text_lower in TO_START_TEXTS:
            self._handle_to_start(user_id, session)
            return

        if text_lower in TO_END_TEXTS:
            self._handle_to_end(user_id, session)
            return

        if text_lower in ADVANCE_TEXTS:
            self._next_phase(user_id, session)
            return

        phase = session.get('phase')

        if not text_lower:
            # Стикер/фото/голосовое приходят из main.py как text="" — не
            # записывать пустой ответ и не продвигать шаг молча.
            self.send_message(
                user_id,
                "Пожалуйста, напиши текстом — я не могу обработать стикер/фото здесь.",
                step_nav_keyboard()
            )
            return

        if phase == 'thoughts':
            session['thoughts'] = text
            session['phase'] = 'feelings'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'feelings':
            session['feelings'] = text
            session['phase'] = 'wants'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'wants':
            session['wants'] = text
            session['phase'] = 'complete'
            session['completed'] = True
            self.save_progress(user_id, session)
            self._finish(user_id, session)

    def _handle_back(self, user_id, session):
        idx = self._phase_index(session.get('phase'))
        if idx <= 0:
            self.send_message(
                user_id,
                "🔙 Это первый шаг — дальше назад некуда.",
                step_nav_keyboard()
            )
            return
        session['phase'] = self.PHASES_ORDER[idx - 1]
        self.save_progress(user_id, session)
        self._show_phase(user_id, session)

    def _handle_to_start(self, user_id, session):
        session['phase'] = self.PHASES_ORDER[0]
        self.save_progress(user_id, session)
        self._show_phase(user_id, session)

    def _handle_to_end(self, user_id, session):
        max_idx = session.get('_max_phase_index', 0)
        session['phase'] = self.PHASES_ORDER[max_idx]
        self.save_progress(user_id, session)
        self._show_phase(user_id, session)

    def _next_phase(self, user_id, session):
        phase = session.get('phase')

        if phase == 'thoughts' and not session.get('thoughts'):
            self.send_message(
                user_id,
                "❌ Напиши, о чём думаешь",
                step_nav_keyboard()
            )
            return
        elif phase == 'feelings' and not session.get('feelings'):
            self.send_message(
                user_id,
                "❌ Напиши свои чувства",
                step_nav_keyboard()
            )
            return
        elif phase == 'wants' and not session.get('wants'):
            self.send_message(
                user_id,
                "❌ Напиши, чего хочешь",
                step_nav_keyboard()
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

        self._bump_max_phase(session)
        self.save_progress(user_id, session)
        self._show_phase(user_id, session)

    def _finish(self, user_id, session):
        result = {
            'thoughts': session.get('thoughts') or '',
            'feelings': session.get('feelings') or '',
            'wants': session.get('wants') or '',
            'count': session.get('count', 0)
        }

        if not self.save_result(user_id, result):
            self._report_save_failure(user_id, session, main_menu())
            return False
        self.delete_progress(user_id)
        self.end_session(user_id)

        count = session.get('count', 0)

        self.send_message(
            user_id,
            f"✨ СТОП #{count}\n\n"
            f"💭 Мысли: {result['thoughts']}\n\n"
            f"❤️ Чувства: {result['feelings']}\n\n"
            f"🎯 Хочу: {result['wants']}\n\n"
            f"🛑 Ты остановился и осознал момент.\n"
            f"Это уже победа ✨\n\n"
            f"Хочешь сделать ещё одну остановку?\n"
            f"Нажми «Упражнения» → «Стоп-техника»",
            main_menu()
        )
        return True

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, session)
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Прогресс сохранён\n"
            "Возвращайся, чтобы продолжить ✨",
            main_menu()
        )
