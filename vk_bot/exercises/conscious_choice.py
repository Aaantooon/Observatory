from .base import BaseExercise
from keyboards import (
    conscious_choice_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    BACK_TEXTS, TO_START_TEXTS, TO_END_TEXTS,
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
            'step': 1,
            '_max_step': 1,
        }

    def _bump_max_step(self, session):
        step = session.get('step', 1)
        if step > session.get('_max_step', 1):
            session['_max_step'] = step

    def _existing_answer_note(self, value):
        if not value:
            return ""
        return f"📝 Текущий ответ: «{value}»\n(напиши новый, чтобы заменить)\n\n"

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
        if progress is None:
            self._progress_unavailable_notice(user_id)
        data = progress.get('data') if progress else None

        has_saved = bool(data and data.get('must_items'))

        if has_saved:
            session = self._fresh_session()
            session.update(data)
            session['_max_step'] = max(session.get('_max_step', 1), session.get('step', 1))
            session['_resume_prompt'] = True
            self.user_sessions[user_id] = session

            self.send_message(
                user_id,
                "🧘 ОСОЗНАННЫЙ ВЫБОР\n\n"
                f"· Ты уже записал: {len(session.get('must_items', []))} пунктов\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_step(user_id, session)

    def _format_pros_cons(self, minus_text, plus_text):
        minus_text = minus_text.strip() if minus_text else '—'
        plus_text = plus_text.strip() if plus_text else '—'
        return f"Минусы: {minus_text}, Плюсы: {plus_text}"

    def _show_step(self, user_id, session, error=None):
        step = session.get('step', 1)
        prefix = f"❌ {error}\n\n" if error else ""

        if step == 1:
            self.send_message(
                user_id,
                f"{prefix}"
                "🧘 ОСОЗНАННЫЙ ВЫБОР\n\n"
                "Шаг 1: Что я должен?\n\n"
                "Напиши по пунктам, что ты должен делать.\n"
                "Например:\n"
                "· Кормить детей\n"
                "· Ходить на работу\n"
                "· Заботиться о родителях\n\n"
                "🎯 Нужно набрать 20 пунктов.\n"
                "Можешь нажать «➡️ Продолжить» и раньше — прогресс сохранится.\n\n"
                "📝 Пиши по одному пункту:",
                conscious_choice_keyboard()
            )
        elif step == 2:
            must = session.get('current_must')
            note = self._existing_answer_note(session.get('current_answer'))
            self.send_message(
                user_id,
                f"{prefix}"
                f"Шаг 2: Я имею право не хотеть\n\n"
                f"Ты написал: «{must}»\n\n"
                f"Это ролевые ожидания.\n"
                f"Ты имеешь право не хотеть этого делать.\n\n"
                f"❓ Кто отнял у тебя это право?\n"
                f"· Никто (ты сам отнял)\n"
                f"· Родители запрещают\n"
                f"· Общество требует\n"
                f"· Другое...\n\n"
                f"{note}"
                f"Напиши свой ответ:",
                conscious_choice_keyboard()
            )
        elif step == 3:
            must = session.get('current_must')
            answer = session.get('current_answer')
            note = self._existing_answer_note(session.get('who_greater'))

            self.send_message(
                user_id,
                f"{prefix}"
                f"Шаг 3: Я выбираю это делать\n\n"
                f"Ты должен: «{must}»\n"
                f"Ты ответил: «{answer}»\n\n"
                f"Теперь ответь на вопрос:\n"
                f"❓ Кто круче Бога?\n\n"
                f"💭 Вселенная (или Бог — кто во что верит) дала право выбора всему живому.\n"
                f"Если кто-то забирает у тебя этот выбор — получается, он круче Бога?\n"
                f"Тогда кто же он?\n\n"
                f"· Никто\n"
                f"· Родители\n"
                f"· Я сам\n"
                f"· Другое...\n\n"
                f"{note}"
                f"Напиши свой ответ:",
                conscious_choice_keyboard()
            )
        elif step == 4:
            self._show_choice_ack(user_id, session)
        elif step == 5:
            self._show_choice_minus(user_id, session)
        elif step == 6:
            self._show_choice_plus(user_id, session)
        elif step == 7:
            self._show_alt_ack(user_id, session)
        elif step == 8:
            self._show_alt_minus(user_id, session)
        elif step == 9:
            self._show_alt_plus(user_id, session)
        elif step == 10:
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
            self._handle_next(user_id, session)
            return

        step = session.get('step', 1)

        if step == 1:
            session['must_items'].append(text)
            session['must_index'] = len(session['must_items']) - 1
            self.save_progress(user_id, session)
            count = len(session['must_items'])
            progress = self._get_progress_bar(count, target=20)
            milestone = self._milestone_line(count, target=20)
            milestone_text = f"{milestone}\n" if milestone else ""

            if count >= 20:
                self.send_message(
                    user_id,
                    f"🎉 Отлично! Ты собрал {count} пунктов.\n"
                    f"{progress}\n\n"
                    "Нажми «➡️ Продолжить», чтобы перейти дальше.",
                    conscious_choice_keyboard()
                )
            else:
                self.send_message(
                    user_id,
                    f"✅ Добавлено: {text} ({count}/20)\n"
                    f"{progress}\n"
                    f"{milestone_text}\n"
                    "Пиши следующий пункт, а когда закончишь — жми «➡️ Продолжить»",
                    conscious_choice_keyboard()
                )

        elif step == 2:
            session['current_answer'] = text
            session['step'] = 3
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 3:
            session['who_greater'] = text
            session['step'] = 4
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 4:
            # Шаг-подтверждение — тут нечего вводить, ждём «Продолжить»
            self.send_message(
                user_id,
                "➡️ Жми «Продолжить», чтобы двигаться дальше",
                conscious_choice_keyboard()
            )

        elif step == 5:
            session['choice_minus'] = text
            session['step'] = 6
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 6:
            session['choice_plus'] = text
            session['choice_analysis'] = self._format_pros_cons(
                session.get('choice_minus', ''), text
            )
            session['step'] = 7
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 7:
            self.send_message(
                user_id,
                "➡️ Жми «Продолжить», чтобы двигаться дальше",
                conscious_choice_keyboard()
            )

        elif step == 8:
            session['alt_minus'] = text
            session['step'] = 9
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 9:
            session['alt_plus'] = text
            session['alternatives'] = self._format_pros_cons(
                session.get('alt_minus', ''), text
            )
            session['step'] = 10
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

    def _handle_back(self, user_id, session):
        step = session.get('step', 1)
        if step <= 1:
            self.send_message(
                user_id,
                "🔙 Это первый шаг — дальше назад некуда.",
                conscious_choice_keyboard()
            )
            return
        session['step'] = step - 1
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _handle_to_start(self, user_id, session):
        session['step'] = 1
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _handle_to_end(self, user_id, session):
        session['step'] = session.get('_max_step', 1)
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _handle_next(self, user_id, session):
        step = session.get('step', 1)

        if step == 1:
            if not session.get('must_items'):
                self.send_message(
                    user_id,
                    "❌ Добавь хотя бы один пункт",
                    conscious_choice_keyboard()
                )
                return

            must_index = session.get('must_index', 0)
            items = session.get('must_items', [])

            if must_index >= len(items):
                self.send_message(
                    user_id,
                    "✅ Все пункты записаны!\n"
                    "Нажми «➡️ Продолжить» для следующего шага",
                    conscious_choice_keyboard()
                )
                return

            session['current_must'] = items[must_index]
            session['step'] = 2
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 2:
            self._show_step(user_id, session, error="Напиши свой ответ на вопрос")

        elif step == 3:
            self._show_step(user_id, session, error="Напиши свой ответ на вопрос")

        elif step == 4:
            session['step'] = 5
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 5:
            session.setdefault('choice_minus', '')
            session['step'] = 6
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 6:
            session.setdefault('choice_plus', '')
            session['choice_analysis'] = self._format_pros_cons(
                session.get('choice_minus', ''), session.get('choice_plus', '')
            )
            session['step'] = 7
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 7:
            session['step'] = 8
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 8:
            session.setdefault('alt_minus', '')
            session['step'] = 9
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 9:
            session.setdefault('alt_plus', '')
            session['alternatives'] = self._format_pros_cons(
                session.get('alt_minus', ''), session.get('alt_plus', '')
            )
            session['step'] = 10
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

    def _show_choice_ack(self, user_id, session):
        must = session.get('current_must')
        self.send_message(
            user_id,
            f"Шаг 4: Анализ выбора\n\n"
            f"📌 Я выбираю: «{must}»\n\n"
            f"➡️ Жми «Продолжить», чтобы посмотреть на минусы и плюсы этого выбора.",
            conscious_choice_keyboard()
        )

    def _show_choice_minus(self, user_id, session):
        note = self._existing_answer_note(session.get('choice_minus'))
        self.send_message(
            user_id,
            f"❓ Не хочу (опасные минусы):\n"
            f"· Дети будут голодными\n"
            f"· Будут жаловаться\n"
            f"· Будут ныть\n\n"
            f"{note}"
            f"✍️ Напиши свои минусы или жми «Продолжить», чтобы пропустить.",
            conscious_choice_keyboard()
        )

    def _show_choice_plus(self, user_id, session):
        note = self._existing_answer_note(session.get('choice_plus'))
        self.send_message(
            user_id,
            f"❓ Хочу (полезные плюсы):\n"
            f"· Увидеть улыбку на лице ребёнка\n"
            f"· Увидеть, как он радуется вкусной еде\n\n"
            f"{note}"
            f"✍️ Напиши свои плюсы или жми «Продолжить», чтобы пропустить.",
            conscious_choice_keyboard()
        )

    def _show_alt_ack(self, user_id, session):
        must = session.get('current_must')
        self.send_message(
            user_id,
            f"Шаг 5: Альтернативы\n\n"
            f"Иногда «{must}» можно не делать.\n\n"
            f"➡️ Жми «Продолжить», чтобы посмотреть на другие минусы и плюсы.",
            conscious_choice_keyboard()
        )

    def _show_alt_minus(self, user_id, session):
        note = self._existing_answer_note(session.get('alt_minus'))
        self.send_message(
            user_id,
            f"❓ Не хочу (другие минусы):\n"
            f"· Устал сильно\n"
            f"· Не могу собраться с мыслями\n"
            f"· Мало времени\n"
            f"· Накопить стресс\n\n"
            f"{note}"
            f"✍️ Напиши свои минусы или жми «Продолжить», чтобы пропустить.",
            conscious_choice_keyboard()
        )

    def _show_alt_plus(self, user_id, session):
        note = self._existing_answer_note(session.get('alt_plus'))
        self.send_message(
            user_id,
            f"❓ Хочу (другие плюсы):\n"
            f"· Набрать энергии и с хорошим настроением\n"
            f"· Заказать что-то из доставки\n"
            f"· Попробовать что-то новое\n\n"
            f"{note}"
            f"✍️ Напиши свои плюсы или жми «Продолжить», чтобы пропустить.",
            conscious_choice_keyboard()
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

        if not self.save_result(user_id, result):
            self._report_save_failure(user_id, session, main_menu())
            return
        self.delete_progress(user_id)
        self.end_session(user_id)

        self.send_message(
            user_id,
            "✨ ПУТЬ ЗАВЕРШЁН\n\n"
            "🧘 Осознанный выбор — это свобода.\n\n"
            "· Ты имеешь право выбирать\n"
            "· Ты имеешь право не хотеть\n"
            "· Ты имеешь право делать или не делать\n\n"
            "💡 Важно:\n"
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
