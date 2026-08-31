from .base import BaseExercise
from keyboards import (
    step_nav_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    BACK_TEXTS, TO_START_TEXTS, TO_END_TEXTS,
)
from datetime import datetime


class DiaryExercise(BaseExercise):
    def get_exercise_type(self):
        return "diary"

    def get_exercise_title(self):
        return "Дневник"

    def _fresh_session(self):
        return {
            'phase': 'dream',
            'dream': '',
            'mood': '',
            'body': '',
            'thoughts': '',
            'wants': '',
            'differences': '',
            'step': 1,
            'completed': False,
            '_max_phase_index': 0,
        }

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    def _handle_save_and_start_over(self, user_id, session):
        self._finish(user_id, session)
        self._handle_start_over(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and (
            data.get('dream') or data.get('mood') or data.get('body') or
            data.get('thoughts') or data.get('wants') or data.get('differences') or
            (data.get('phase') and data.get('phase') != 'dream')
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
                "📖 ДНЕВНИК\n\n"
                "· У тебя есть незаконченная запись\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    PHASES_ORDER = ['dream', 'mood', 'body', 'thoughts', 'wants', 'differences']

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
        phase = session.get('phase')
        step_num = self._phase_index(phase) + 1
        progress = self._get_progress_bar(step_num, target=len(self.PHASES_ORDER))
        note = self._existing_answer_note(session.get(phase))

        if phase == 'dream':
            self.send_message(
                user_id,
                "📖 ДНЕВНИК\n\n"
                "Шаг 1: Сон\n"
                f"{progress}\n\n"
                f"{note}"
                "Напиши коротко самое основное.\n"
                "Не весь клубок разматывай — а ниточку,\n"
                "за которую дернишь и всё вспомнишь.\n\n"
                "Пример: «Гулял по парку и увидел белку»\n\n"
                "✏️ Напиши свой сон:",
                step_nav_keyboard()
            )

        elif phase == 'mood':
            self.send_message(
                user_id,
                "Шаг 2: Настроение\n"
                f"{progress}\n\n"
                f"{note}"
                "Всё что угодно, кроме «нормально».\n\n"
                "Примеры:\n"
                "· Замечательное, приятное\n"
                "· Тоскливое, тревожное\n"
                "· Бодрое, энергичное\n\n"
                "✏️ Напиши своё настроение:",
                step_nav_keyboard()
            )

        elif phase == 'body':
            self.send_message(
                user_id,
                "Шаг 3: Общее ощущение в теле\n"
                f"{progress}\n\n"
                f"{note}"
                "Что чувствуешь?\n\n"
                "Примеры:\n"
                "· Ноги ноют\n"
                "· Голова как кисель\n"
                "· В теле лёгкость\n\n"
                "✏️ Напиши свои ощущения:",
                step_nav_keyboard()
            )

        elif phase == 'thoughts':
            self.send_message(
                user_id,
                "Шаг 4: О чём думаешь?\n"
                f"{progress}\n\n"
                f"{note}"
                "Не всех козлов перечисляй — а папочку о козлах.\n"
                "Не всех родственниках — а папку «родственники».\n\n"
                "Папка обязательная: долги\n\n"
                "✏️ Напиши свои мысли (папками):",
                step_nav_keyboard()
            )

        elif phase == 'wants':
            self.send_message(
                user_id,
                "Шаг 5: Чего я хочу?\n"
                f"{progress}\n\n"
                f"{note}"
                "Сейчас. Без ограничений. Всё, что приходит в голову.\n\n"
                "Пример:\n"
                "«Сон неприятный и ноги ноют — сейчас разминку сделаю\n"
                "и кофе выпью. Потом посмотрим.»\n\n"
                "✏️ Напиши, чего хочешь:",
                step_nav_keyboard()
            )

        elif phase == 'differences':
            self.send_message(
                user_id,
                "Шаг 6: Чем этот день отличается от других?\n"
                f"{progress}\n\n"
                f"{note}"
                "Важно заметить уникальность каждого дня.\n\n"
                "✏️ Напиши, что особенного в этом дне:",
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
                self._handle_start_over(user_id)
                return
            self.send_message(
                user_id,
                "🕯️ Нажми «Продолжить ✅» или «Начать заново 🔄».",
                continue_keyboard()
            )
            return

        if text_lower in RESTART_TEXTS:
            self._handle_start_over(user_id)
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

        if phase == 'dream':
            session['dream'] = text
            session['phase'] = 'mood'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'mood':
            session['mood'] = text
            session['phase'] = 'body'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'body':
            session['body'] = text
            session['phase'] = 'thoughts'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'thoughts':
            session['thoughts'] = text
            session['phase'] = 'wants'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'wants':
            session['wants'] = text
            session['phase'] = 'differences'
            self._bump_max_phase(session)
            self.save_progress(user_id, session)
            self._show_phase(user_id, session)

        elif phase == 'differences':
            session['differences'] = text
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

        if phase == 'dream' and not session.get('dream'):
            self.send_message(
                user_id,
                "❌ Напиши свой сон",
                step_nav_keyboard()
            )
            return
        elif phase == 'mood' and not session.get('mood'):
            self.send_message(
                user_id,
                "❌ Напиши настроение",
                step_nav_keyboard()
            )
            return
        elif phase == 'body' and not session.get('body'):
            self.send_message(
                user_id,
                "❌ Напиши ощущения в теле",
                step_nav_keyboard()
            )
            return
        elif phase == 'thoughts' and not session.get('thoughts'):
            self.send_message(
                user_id,
                "❌ Напиши свои мысли",
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
        elif phase == 'differences' and not session.get('differences'):
            self.send_message(
                user_id,
                "❌ Напиши, чем отличается день",
                step_nav_keyboard()
            )
            return

        self._next_phase_forced(user_id, session)

    def _next_phase_forced(self, user_id, session):
        phase = session.get('phase')

        if phase == 'dream':
            session['phase'] = 'mood'
        elif phase == 'mood':
            session['phase'] = 'body'
        elif phase == 'body':
            session['phase'] = 'thoughts'
        elif phase == 'thoughts':
            session['phase'] = 'wants'
        elif phase == 'wants':
            session['phase'] = 'differences'
        elif phase == 'differences':
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
            'dream': session.get('dream') or '',
            'mood': session.get('mood') or '',
            'body': session.get('body') or '',
            'thoughts': session.get('thoughts') or '',
            'wants': session.get('wants') or '',
            'differences': session.get('differences') or ''
        }

        self.save_result(user_id, result)
        self.delete_progress(user_id)
        self.end_session(user_id)

        self.send_message(
            user_id,
            f"✨ ДНЕВНИК ЗАПИСАН\n\n"
            f"📖 Сон: {result['dream']}\n\n"
            f"😊 Настроение: {result['mood']}\n\n"
            f"💪 Тело: {result['body']}\n\n"
            f"💭 Мысли: {result['thoughts'][:100]}...\n\n"
            f"🎯 Хочу: {result['wants'][:100]}...\n\n"
            f"🌟 Особенность дня: {result['differences']}\n\n"
            f"✨ Береги себя ❤️",
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
