from .base import BaseExercise
from keyboards import (
    exercise_keyboard, finish_keyboard, back_keyboard, main_menu, cancel_keyboard, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
)


class MyRolesExercise(BaseExercise):
    def get_exercise_type(self):
        return "my_roles"

    def get_exercise_title(self):
        return "Мои роли"

    def _fresh_session(self):
        return {
            'phase': 'social',
            'social_roles': [],
            'interpersonal_roles': [],
            'intrapersonal_roles': [],
            'current_type': 'social',
            'step': 1
        }

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_instruction(user_id, session)

    def _handle_save_and_start_over(self, user_id, session):
        self._finish(user_id, session)
        self._handle_start_over(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and (
            data.get('social_roles') or
            data.get('interpersonal_roles') or
            data.get('intrapersonal_roles')
        ))

        if has_saved:
            session = self._fresh_session()
            session.update(data)
            session['_resume_prompt'] = True
            self.user_sessions[user_id] = session

            total = (len(session.get('social_roles', [])) +
                      len(session.get('interpersonal_roles', [])) +
                      len(session.get('intrapersonal_roles', [])))

            self.send_message(
                user_id,
                "🎭 МОИ РОЛИ\n\n"
                f"· Ты уже записал: {total} ролей\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_instruction(user_id, session)

    def _show_instruction(self, user_id, session):
        phase = session.get('phase', 'social')
        
        if phase == 'social':
            self.send_message(
                user_id,
                "🎭 МОИ РОЛИ\n\n"
                "Это игра-открытие, а не тест — тут нет правильных и неправильных ответов.\n\n"
                "Часть 1: Социальные роли\n"
                "Представь себя актёром: какие роли ты играешь для общества?\n\n"
                "Примеры:\n"
                "· Повар, прохожий, пешеход\n"
                "· Продавец, гуляющий в парке\n"
                "· Смотрящий на деревья\n\n"
                "📝 Пиши по одной роли за раз (до 20, можно и меньше)\n"
                "💡 Спешить некуда: комфортнее добавлять не больше одной роли в день,\n"
                "чтобы каждую успеть прочувствовать\n\n"
                "Когда закончишь раздел — жми «➡️ Продолжить»",
                exercise_keyboard()
            )
        elif phase == 'interpersonal':
            self.send_message(
                user_id,
                "Часть 2: Межличностные роли\n"
                "Какие роли ты играешь для конкретных людей?\n\n"
                "Примеры:\n"
                "· Друг для Серёжи\n"
                "· Отец для Алины\n"
                "· Рабочий для начальника Александра\n\n"
                "📝 Пиши по одной роли за раз (до 20, можно и меньше)\n"
                "💡 Одной роли в день вполне достаточно",
                exercise_keyboard()
            )
        elif phase == 'intrapersonal':
            self.send_message(
                user_id,
                "Часть 3: Внутриличностные роли\n"
                "А какие роли живут внутри тебя самого?\n\n"
                "Примеры:\n"
                "· Злой, Ленивый, Застенчивый\n"
                "· Щедрый, Тревожный, Смелый\n\n"
                "📝 Пиши по одной роли за раз (до 10, можно и меньше)\n"
                "💡 Одной роли в день вполне достаточно",
                exercise_keyboard()
            )
        elif phase == 'analyze':
            self._resume_analyze(user_id, session)

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
                self._show_instruction(user_id, session)
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

        if text_lower in ADVANCE_TEXTS:
            self._handle_phase_complete(user_id, session)
            return

        phase = session.get('phase')
        
        if phase == 'social':
            session['social_roles'].append(text)
            self.save_progress(user_id, session)
            self._send_role_added(user_id, text, len(session['social_roles']))

        elif phase == 'interpersonal':
            session['interpersonal_roles'].append(text)
            self.save_progress(user_id, session)
            self._send_role_added(user_id, text, len(session['interpersonal_roles']))

        elif phase == 'intrapersonal':
            session['intrapersonal_roles'].append(text)
            self.save_progress(user_id, session)
            self._send_role_added(user_id, text, len(session['intrapersonal_roles']), target=10)

        elif phase == 'analyze':
            self._handle_analysis(user_id, text, session)

    def _send_role_added(self, user_id, text, count, target=20):
        if count >= target:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} ролей в этом разделе.\n"
                "Нажми «➡️ Продолжить», чтобы перейти дальше.",
                exercise_keyboard()
            )
        else:
            self.send_message(
                user_id,
                f"✅ Добавлено: {text} ({count}/{target})\n\n"
                "Пиши следующую роль, а когда закончишь раздел — жми «➡️ Продолжить»",
                exercise_keyboard()
            )

    def _handle_phase_complete(self, user_id, session):
        phase = session.get('phase')
        
        if phase == 'social':
            session['phase'] = 'interpersonal'
            self.save_progress(user_id, session)
            self._show_instruction(user_id, session)

        elif phase == 'interpersonal':
            session['phase'] = 'intrapersonal'
            self.save_progress(user_id, session)
            self._show_instruction(user_id, session)

        elif phase == 'intrapersonal':
            session['phase'] = 'analyze'
            session['analysis_index'] = 0
            session['analysis_results'] = []
            self.save_progress(user_id, session)
            self._analyze_roles(user_id, session)

    def _all_roles(self, session):
        return (session.get('social_roles', []) +
                session.get('interpersonal_roles', []) +
                session.get('intrapersonal_roles', []))

    def _analyze_roles(self, user_id, session):
        """Начинает анализ следующей роли (или завершает упражнение, если роли
        закончились) — всегда с шага 1 ('Идеально')."""
        all_roles = self._all_roles(session)
        index = session.get('analysis_index', 0)

        if index >= len(all_roles):
            self._finish(user_id, session)
            return

        role = all_roles[index]
        session['analysis_step'] = 1
        session.pop('current_ideal', None)
        self.save_progress(user_id, session)

        self.send_message(
            user_id,
            f"🎭 АНАЛИЗ РОЛИ {index+1}/{len(all_roles)}\n\n"
            f"📌 Роль: {role}\n\n"
            f"Немного игры: представь, что тебе заплатят $100,000,000 —\n"
            f"но только если сыграешь эту роль просто идеально.\n\n"
            f"✨ Как это будет выглядеть, если сыграть её идеально?",
            cancel_keyboard()
        )

    def _resume_analyze(self, user_id, session):
        """Повторно показывает текущий шаг анализа при возобновлении сессии,
        не сбрасывая уже введённый ответ на 'Идеально' (в отличие от
        _analyze_roles, которая всегда начинает роль заново с шага 1)."""
        all_roles = self._all_roles(session)
        index = session.get('analysis_index', 0)

        if index >= len(all_roles):
            self._finish(user_id, session)
            return

        if session.get('analysis_step') == 2:
            role = all_roles[index]
            self.send_message(
                user_id,
                f"📌 Роль: {role}\n\n"
                f"А теперь наоборот 😄 Как это будет выглядеть, если сыграть роль просто ужасно?",
                cancel_keyboard()
            )
        else:
            self._analyze_roles(user_id, session)

    def _handle_analysis(self, user_id, text, session):
        all_roles = self._all_roles(session)
        index = session.get('analysis_index', 0)
        role = all_roles[index]
        step = session.get('analysis_step', 1)

        if step == 1:
            session['current_ideal'] = text
            session['analysis_step'] = 2
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                f"📌 Роль: {role}\n\n"
                f"А теперь наоборот 😄 Как это будет выглядеть, если сыграть роль просто ужасно?",
                cancel_keyboard()
            )
            return

        session['analysis_results'].append({
            'role': role,
            'ideal': session.get('current_ideal', ''),
            'terrible': text
        })
        session.pop('current_ideal', None)

        session['analysis_index'] = index + 1
        self.save_progress(user_id, session)
        self._analyze_roles(user_id, session)

    def _finish(self, user_id, session):
        result = {
            'social_roles': session.get('social_roles', []),
            'interpersonal_roles': session.get('interpersonal_roles', []),
            'intrapersonal_roles': session.get('intrapersonal_roles', []),
            'analysis': session.get('analysis_results', [])
        }
        
        self.save_result(user_id, result)
        self.delete_progress(user_id)
        self.end_session(user_id)

        message = (
            "✨ ПУТЬ ЗАВЕРШЁН\n\n"
            "🎭 Итог по ролям:\n\n"
            f"Социальных: {len(result['social_roles'])}\n"
            f"Межличностных: {len(result['interpersonal_roles'])}\n"
            f"Внутриличностных: {len(result['intrapersonal_roles'])}\n\n"
            "💡 Важно:\n"
            "· Нет идеальных ролей\n"
            "· Ты стараешься дарить добро\n"
            "· Ты не делаешь зла\n"
            "· Это уже хорошо ✨"
        )
        
        self.send_message(user_id, message, main_menu())

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, session)
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Прогресс сохранён\n"
            "Возвращайся, чтобы продолжить ✨",
            main_menu()
        )