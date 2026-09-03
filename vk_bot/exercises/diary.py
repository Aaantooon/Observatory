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
        has_content = bool(
            session.get('dream') or session.get('mood') or session.get('body') or
            session.get('thoughts') or session.get('wants') or session.get('differences')
        )
        if not has_content:
            # Нечего сохранять — ни на один из 6 шагов ещё не ответили.
            # Раньше это всё равно уходило в _finish() и создавало на
            # сервере пустую запись дневника без единого слова.
            self.send_message(
                user_id,
                "🌫️ Пока нечего сохранять — ты ещё не ответил(а) ни на один вопрос. Начинаем заново."
            )
            self._handle_start_over(user_id)
            return

        if not self._finish(user_id, session):
            # _finish() уже сообщил о сбое и сохранил текущие ответы как
            # черновик прогресса (см. _report_save_failure) — раньше сюда
            # заходили безусловно и следующей же строкой удаляли этот самый
            # черновик и открывали пустую сессию, теряя ответы насовсем.
            return

        self._handle_start_over(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        if progress is None:
            self._progress_unavailable_notice(user_id)
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

            block = self.PHASE_BLOCK.get(session.get('phase'))
            next_block_line = f"· Дальше: {self.BLOCK_TITLES[block]}\n" if block in self.BLOCK_TITLES else ""
            self.send_message(
                user_id,
                "📖 ДНЕВНИК\n\n"
                "· У тебя есть незаконченная запись\n"
                f"{next_block_line}\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_phase(user_id, session)

    PHASES_ORDER = ['dream', 'mood', 'body', 'thoughts', 'wants', 'differences']

    # Дневник идёт тремя заходами в течение дня, а не одним линейным
    # разговором: сон — сразу после пробуждения; настроение/тело/мысли/хочу —
    # примерно через час, когда человек уже осмотрелся в дне; отличия дня —
    # вечером. См. _next_phase_forced/_show_block_boundary — между блоками
    # сессия завершается (как при отмене), а не просто показывает следующий
    # вопрос сразу же.
    PHASE_BLOCK = {
        'dream': 'morning',
        'mood': 'day',
        'body': 'day',
        'thoughts': 'day',
        'wants': 'day',
        'differences': 'evening',
    }
    BLOCK_TITLES = {
        'morning': '🌅 Утро',
        'day': '☀️ День',
        'evening': '🌙 Вечер',
    }

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

    def _format_day_recap(self, session):
        """Короткая сводка настроения/тела/мыслей прямо перед вопросом
        «Чего я хочу?» — по просьбе пользователя ответ здесь должен
        опираться на то, что уже написано выше (например, если болит
        спина — решить посидеть на работе, а не рваться делать всё как
        обычно), а не сочиняться с чистого листа без взгляда назад."""
        mood = session.get('mood')
        body = session.get('body')
        thoughts = session.get('thoughts')
        if not (mood or body or thoughts):
            return ""
        lines = ["📝 Коротко о сегодняшнем дне:"]
        if mood:
            lines.append(f"· Настроение: {self._truncate_for_display(mood, 150)}")
        if body:
            lines.append(f"· Тело: {self._truncate_for_display(body, 150)}")
        if thoughts:
            lines.append(f"· Мысли: {self._truncate_for_display(thoughts, 150)}")
        return "\n".join(lines) + "\n\n"

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
                "Что напряжено, а что расслаблено? Болит ли голова — и если да, то как?\n\n"
                "Примеры:\n"
                "· Плечи зажаты, ноги лёгкие, голова не болит\n"
                "· Голова тяжёлая, будто сдавило — остальное расслаблено\n"
                "· В теле лёгкость, ничего не болит и не напряжено\n\n"
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
            recap = self._format_day_recap(session)
            self.send_message(
                user_id,
                "Шаг 5: Чего я хочу?\n"
                f"{progress}\n\n"
                f"{recap}"
                f"{note}"
                "Сейчас. Без ограничений. Всё, что приходит в голову — с опорой на то, "
                "что уже написал(а) выше.\n\n"
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

        if not text_lower:
            # Стикер/фото/голосовое приходят из main.py как text="" — не
            # записывать пустой ответ и не продвигать шаг молча.
            self.send_message(
                user_id,
                "Пожалуйста, напиши текстом — я не могу обработать стикер/фото здесь.",
                step_nav_keyboard()
            )
            return

        if phase == 'dream':
            session['dream'] = text
            self._advance_to(user_id, session, 'mood')

        elif phase == 'mood':
            session['mood'] = text
            self._advance_to(user_id, session, 'body')

        elif phase == 'body':
            session['body'] = text
            self._advance_to(user_id, session, 'thoughts')

        elif phase == 'thoughts':
            session['thoughts'] = text
            self._advance_to(user_id, session, 'wants')

        elif phase == 'wants':
            session['wants'] = text
            self._advance_to(user_id, session, 'differences')

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

    def _advance_to(self, user_id, session, next_phase):
        """Общий переход между шагами дневника, ПОСЛЕ того как ответ уже
        записан в session — общее место и для прямого ввода ответа текстом
        (сразу переходит дальше), и для «Продолжить» на необязательном шаге
        (см. _next_phase_forced). Если новый шаг попадает в другой блок дня
        (Утро/День/Вечер, см. PHASE_BLOCK) — показывает не сам вопрос, а
        прощание до нужного времени суток (_show_block_boundary), а не
        следующий вопрос сразу же."""
        prev_block = self.PHASE_BLOCK.get(session.get('phase'))
        session['phase'] = next_phase
        self._bump_max_phase(session)
        self.save_progress(user_id, session)

        next_block = self.PHASE_BLOCK.get(next_phase)
        if next_block != prev_block:
            self._show_block_boundary(user_id, session, next_block)
        else:
            self._show_phase(user_id, session)

    def _next_phase_forced(self, user_id, session):
        phase = session.get('phase')

        if phase == 'dream':
            self._advance_to(user_id, session, 'mood')
        elif phase == 'mood':
            self._advance_to(user_id, session, 'body')
        elif phase == 'body':
            self._advance_to(user_id, session, 'thoughts')
        elif phase == 'thoughts':
            self._advance_to(user_id, session, 'wants')
        elif phase == 'wants':
            self._advance_to(user_id, session, 'differences')
        elif phase == 'differences':
            session['phase'] = 'complete'
            session['completed'] = True
            self.save_progress(user_id, session)
            self._finish(user_id, session)

    def _show_block_boundary(self, user_id, session, next_block):
        """Экран между блоками дневника — сессия завершается (как при
        отмене), а не ждёт на месте: пользователь свободен заняться другими
        делами (например, стоп-техникой), прогресс уже сохранён и
        подхватится сам, когда он вернётся в «Дневник» — см. start()."""
        self.end_session(user_id)
        if next_block == 'day':
            # Одноразовое напоминание через час — не нужно ждать на месте
            # и не нужно ничего нажимать; best-effort — если API недоступен,
            # человек всё равно ничего не теряет (сон уже сохранён), просто
            # не получит пинг и вернётся сам.
            self.api.create_notification(
                user_id, 'diary_day', 'once', {"delay_hours": 1, "exercise_type": "diary_day"}
            )
            self.send_message(
                user_id,
                "🌅 Утренняя часть готова — сон записан.\n\n"
                "☀️ Дальше — дневная часть: настроение, тело, мысли, чего хочешь. "
                "Загляни сюда примерно через час, когда осмотришься в дне — я напомню.",
                main_menu()
            )
        elif next_block == 'evening':
            self.send_message(
                user_id,
                "☀️ Дневная часть готова.\n\n"
                "🌙 Вечером — последний вопрос: чем этот день отличается от других. "
                "Загляни сюда в конце дня.",
                main_menu()
            )

    def _truncate_for_display(self, text, limit):
        """Обрезает текст для сообщения-эхо, чтобы неограниченный ввод
        пользователя (dream/mood/body/differences/thoughts/wants) не мог
        разово превысить ~4096-символьный лимит сообщения VK и уронить
        отправку ПОСЛЕ того, как save_result()/delete_progress() уже
        отработали. '…' добавляется только если реально что-то обрезано."""
        text = text or ''
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _finish(self, user_id, session):
        result = {
            'dream': session.get('dream') or '',
            'mood': session.get('mood') or '',
            'body': session.get('body') or '',
            'thoughts': session.get('thoughts') or '',
            'wants': session.get('wants') or '',
            'differences': session.get('differences') or ''
        }

        if not self.save_result(user_id, result):
            self._report_save_failure(user_id, session, main_menu())
            return False
        self.delete_progress(user_id)
        self.end_session(user_id)

        self.send_message(
            user_id,
            f"✨ ДНЕВНИК ЗАПИСАН\n\n"
            f"📖 Сон: {self._truncate_for_display(result['dream'], 300)}\n\n"
            f"😊 Настроение: {self._truncate_for_display(result['mood'], 300)}\n\n"
            f"💪 Тело: {self._truncate_for_display(result['body'], 300)}\n\n"
            f"💭 Мысли: {self._truncate_for_display(result['thoughts'], 100)}\n\n"
            f"🎯 Хочу: {self._truncate_for_display(result['wants'], 100)}\n\n"
            f"🌟 Особенность дня: {self._truncate_for_display(result['differences'], 300)}\n\n"
            f"✨ Береги себя ❤️",
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
