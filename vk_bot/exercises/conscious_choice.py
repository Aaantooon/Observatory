from .base import BaseExercise
from keyboards import (
    exercise_keyboard, finish_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
)


class ConsciousChoiceExercise(BaseExercise):
    def get_exercise_type(self):
        return "conscious_choice"

    def get_exercise_title(self):
        return "Осознанный выбор"

    def _fresh_session(self):
        return {
            'phase': 'must',
            'must_items': [],
            'current_must': None,
            'step': 1
        }

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_step(user_id, session)

    def _handle_save_and_start_over(self, user_id, session):
        self._finish(user_id, session)
        self._handle_start_over(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and data.get('must_items'))

        if has_saved:
            session = self._fresh_session()
            session.update(data)
            session['_resume_prompt'] = True
            self.user_sessions[user_id] = session

            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║        🧘 ОСОЗНАННЫЙ ВЫБОР     ║\n"
                "╚══════════════════════════════════╝\n\n"
                f"· Ты уже записал: **{len(session.get('must_items', []))}** пунктов\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_step(user_id, session)

    def _show_step(self, user_id, session):
        step = session.get('step', 1)
        
        if step == 1:
            self.send_message(
                user_id,
                "╔══════════════════════════════════╗\n"
                "║        🧘 ОСОЗНАННЫЙ ВЫБОР     ║\n"
                "╚══════════════════════════════════╝\n\n"
                "**Шаг 1: Что я должен?**\n\n"
                "Напиши по пунктам, что ты должен делать.\n"
                "Например:\n"
                "· Кормить детей\n"
                "· Ходить на работу\n"
                "· Заботиться о родителях\n\n"
                "📝 Пиши по одному пункту:",
                exercise_keyboard()
            )
        elif step == 2:
            must = session.get('current_must')
            self.send_message(
                user_id,
                f"**Шаг 2: Я имею право не хотеть**\n\n"
                f"Ты написал: «{must}»\n\n"
                f"Это **ролевые ожидания**.\n"
                f"Ты имеешь право **не хотеть** этого делать.\n\n"
                f"❓ Кто отнял у тебя это право?\n"
                f"· Никто (ты сам отнял)\n"
                f"· Родители запрещают\n"
                f"· Общество требует\n"
                f"· Другое...\n\n"
                f"Напиши свой ответ:",
                finish_keyboard()
            )
        elif step == 3:
            must = session.get('current_must')
            answer = session.get('current_answer')
            
            self.send_message(
                user_id,
                f"**Шаг 3: Я выбираю это делать**\n\n"
                f"Ты должен: «{must}»\n"
                f"Ты ответил: «{answer}»\n\n"
                f"Теперь ответь на вопрос:\n"
                f"❓ **Кто круче Бога?**\n\n"
                f"· Никто\n"
                f"· Родители\n"
                f"· Я сам\n"
                f"· Другое...\n\n"
                f"Напиши свой ответ:",
                finish_keyboard()
            )
        elif step == 4:
            self._show_choice_analysis(user_id, session)
        elif step == 5:
            self._show_alternatives(user_id, session)
        elif step == 6:
            self._finish(user_id, session)

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
                self._show_step(user_id, session)
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
            self._handle_next(user_id, session)
            return

        step = session.get('step', 1)

        if step == 1:
            session['must_items'].append(text)
            session['must_index'] = len(session['must_items']) - 1
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                f"✅ Добавлено: {text}\n\n"
                "Пиши следующий пункт, а когда закончишь — жми «➡️ Продолжить»",
                exercise_keyboard()
            )
        
        elif step == 2:
            session['current_answer'] = text
            session['step'] = 3
            self.save_progress(user_id, session)
            self._show_step(user_id, session)
        
        elif step == 3:
            session['who_greater'] = text
            session['step'] = 4
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 4:
            session['choice_analysis'] = text
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                "✅ Записано!\n\nНажми «Завершить», чтобы перейти дальше",
                finish_keyboard()
            )

        elif step == 5:
            session['alternatives'] = text
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                "✅ Записано!\n\nНажми «Завершить», чтобы закончить упражнение",
                finish_keyboard()
            )

    def _handle_next(self, user_id, session):
        step = session.get('step', 1)
        
        if step == 1:
            if not session.get('must_items'):
                self.send_message(
                    user_id,
                    "❌ Добавь хотя бы один пункт",
                    exercise_keyboard()
                )
                return
            
            must_index = session.get('must_index', 0)
            items = session.get('must_items', [])
            
            if must_index >= len(items):
                self.send_message(
                    user_id,
                    "✅ Все пункты записаны!\n"
                    "Нажми «Завершить» для следующего шага",
                    finish_keyboard()
                )
                return
            
            session['current_must'] = items[must_index]
            session['step'] = 2
            self.save_progress(user_id, session)
            self._show_step(user_id, session)
        
        elif step == 2:
            self.send_message(
                user_id,
                "❌ Напиши свой ответ на вопрос",
                finish_keyboard()
            )
        
        elif step == 3:
            self.send_message(
                user_id,
                "❌ Напиши свой ответ на вопрос",
                finish_keyboard()
            )
        
        elif step == 4:
            if not session.get('choice_analysis'):
                self.send_message(
                    user_id,
                    "❌ Напиши свои минусы и плюсы перед тем, как продолжить",
                    finish_keyboard()
                )
                return
            session['step'] = 5
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 5:
            if not session.get('alternatives'):
                self.send_message(
                    user_id,
                    "❌ Напиши свои минусы и плюсы перед тем, как продолжить",
                    finish_keyboard()
                )
                return
            session['step'] = 6
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

    def _show_choice_analysis(self, user_id, session):
        must = session.get('current_must')
        answer = session.get('current_answer')
        who = session.get('who_greater')
        
        self.send_message(
            user_id,
            f"**Шаг 4: Анализ выбора**\n\n"
            f"📌 **Я выбираю:** «{must}»\n\n"
            f"❓ **Не хочу (опасные минусы):**\n"
            f"· Дети будут голодными\n"
            f"· Будут жаловаться\n"
            f"· Будут ныть\n\n"
            f"❓ **Хочу (полезные плюсы):**\n"
            f"· Увидеть улыбку на лице ребёнка\n"
            f"· Увидеть, как он радуется вкусной еде\n\n"
            f"Напиши свои **минусы** и **плюсы** через запятую:\n"
            f"`Минусы: ..., Плюсы: ...`",
            finish_keyboard()
        )

    def _show_alternatives(self, user_id, session):
        must = session.get('current_must')
        
        self.send_message(
            user_id,
            f"**Шаг 5: Альтернативы**\n\n"
            f"Иногда **«{must}»** можно не делать.\n\n"
            f"❓ **Не хочу (другие минусы):**\n"
            f"· Устал сильно\n"
            f"· Не могу собраться с мыслями\n"
            f"· Мало времени\n"
            f"· Накопить стресс\n\n"
            f"❓ **Хочу (другие плюсы):**\n"
            f"· Набрать энергии и с хорошим настроением\n"
            f"· Заказать что-то из доставки\n"
            f"· Попробовать что-то новое\n\n"
            f"Напиши свои **минусы** и **плюсы** через запятую:\n"
            f"`Минусы: ..., Плюсы: ...`",
            finish_keyboard()
        )

    def _finish(self, user_id, session):
        result = {
            'must_items': session.get('must_items', []),
            'answers': {
                'who_took': session.get('current_answer'),
                'who_greater': session.get('who_greater')
            },
            'choice_analysis': session.get('choice_analysis', ''),
            'alternatives': session.get('alternatives', '')
        }
        
        self.save_result(user_id, result)
        self.delete_progress(user_id)
        self.end_session(user_id)

        self.send_message(
            user_id,
            "╔══════════════════════════════════╗\n"
            "║        ✨ ПУТЬ ЗАВЕРШЁН         ║\n"
            "╚══════════════════════════════════╝\n\n"
            "🧘 **Осознанный выбор — это свобода.**\n\n"
            "· Ты имеешь право выбирать\n"
            "· Ты имеешь право не хотеть\n"
            "· Ты имеешь право делать или не делать\n\n"
            "💡 **Важно:**\n"
            "Пока не заболел — есть возможность.\n"
            "Ребёнок вырос — он сам готовит.\n"
            "Ребёнок не голоден — не надо кормить.\n\n"
            "✨ Береги себя ❤️",
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