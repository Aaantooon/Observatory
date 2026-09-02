from .base import BaseExercise
from keyboards import (
    exercise_keyboard, finish_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
)
from config import MAX_EXERCISE_ITEMS


class HappinessListExercise(BaseExercise):
    def get_exercise_type(self):
        return "happiness_list"

    def get_exercise_title(self):
        return "Список счастья"

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        self._start_new(user_id)

    def _handle_save_and_start_over(self, user_id, session):
        items = session.get('items', [])
        if not items:
            self.delete_progress(user_id)
            self.end_session(user_id)
            self._start_new(user_id)
            return

        if not self._finish(user_id, session):
            # _finish() уже сообщил о сбое и сохранил items как черновик
            # прогресса (см. _report_save_failure) — раньше отсюда всё
            # равно безусловно уходили в _start_new(), которая тут же
            # подменяла текущую сессию пустой ({'items': []}). Пользователю
            # говорили "ничего не потеряно", а его список пунктов в тот же
            # момент пропадал из вида — восстановить его можно было, только
            # выйдя из упражнения и зайдя заново.
            return

        self._start_new(user_id)

    def start(self, user_id):
        progress = self.get_progress(user_id)
        if progress is None:
            self._progress_unavailable_notice(user_id)

        items = []
        if progress and progress.get('data'):
            items = progress.get('data', {}).get('items', [])

        if items:
            self.user_sessions[user_id] = {'phase': 'collecting', 'items': items, '_resume_prompt': True}
            self.send_message(
                user_id,
                "✨ СПИСОК СЧАСТЬЯ\n\n"
                f"· Ты уже записал: {len(items)} пунктов\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        self._start_new(user_id)

    def _start_new(self, user_id):
        self.user_sessions[user_id] = {'phase': 'collecting', 'items': []}
        
        self.send_message(
            user_id,
            "✨ СПИСОК СЧАСТЬЯ\n\n"
            "Давай вспомним, что приносит тебе радость.\n\n"
            "📝 Пиши, что тебя радует, и ставь оценку от 1 до 10 — можно по одному пункту, "
            "можно сразу несколько (каждый с новой строки или все в одну — как удобнее), "
            "всё запомнится.\n"
            "Например:\n"
            "· Кофе утром 8\n"
            "· Прогулка в парке 9\n"
            "· Общение с друзьями 10\n\n"
            f"Нужно набрать до {MAX_EXERCISE_ITEMS} пунктов.\n"
            "Ты можешь завершить в любой момент — я сохраню прогресс.\n\n"
            "✏️ Напиши первый пункт и оценку:",
            exercise_keyboard()
        )

    def _item_text_for_display(self, text, limit=150):
        """Обрезает текст пункта для показа в списке — сам пункт не
        ограничен по длине при вводе, а список может содержать до 20
        пунктов, так что без этого одно сообщение может легко перевалить
        за ~4096-символьный лимит VK."""
        text = text or ''
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _show_items(self, user_id, items):
        message = "📋 Твой список счастья:\n\n"
        for i, item in enumerate(items, 1):
            item_text = self._item_text_for_display(item.get('text'))
            message += f"{i}. {self._score_emoji(item.get('score', 0))} {item_text} — {item.get('score')}/10\n"

        message += f"\nВсего: {len(items)}/{MAX_EXERCISE_ITEMS} пунктов\n"
        message += f"{self._get_progress_bar(len(items), target=MAX_EXERCISE_ITEMS)}\n\n"
        message += "✏️ Пиши следующий пункт, а когда закончишь — жми «➡️ Продолжить»."
        
        self.send_message(user_id, message, exercise_keyboard())

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
                self._show_items(user_id, session.get('items', []))
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
            self._finish(user_id, session)
            return

        if session.get('phase') == 'collecting':
            self._handle_item(user_id, text, session)

    def _parse_happiness_line(self, line):
        """Разбирает одну строку вида «Текст — 8» или «Текст 8» в (текст,
        оценка). Возвращает None, если строка не подходит под формат."""
        cleaned = line.strip(' \t;,.-—•·')
        if not cleaned:
            return None

        parts = cleaned.rsplit(' ', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return None

        score = int(parts[1])
        if not (1 <= score <= 10):
            return None

        item_text = parts[0].strip().rstrip('-—–').strip()
        if not item_text:
            return None

        return item_text, score

    def _split_happiness_lines(self, text):
        """Разбивает вставленный текст на отдельные пункты — по переносам
        строк (человек присылает сразу список, каждый пункт со своей
        строки, «по пунктам»)."""
        items = []
        invalid = []
        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            parsed = self._parse_happiness_line(line)
            if parsed:
                items.append(parsed)
            else:
                invalid.append(line)
        return items, invalid

    def _tokenize_happiness_items(self, text):
        """Разбирает ОДНУ строку вида «Фраза N Фраза N Фраза N …» без
        переносов — каждая оценка 1-10 закрывает фразу перед собой и
        открывает следующую. Так распознаётся список, вставленный сплошным
        текстом «в строчку», а не по пунктам. Возвращает (список пар
        (текст, оценка), остаток текста после последней найденной оценки,
        если он не пуст)."""
        buffer = []
        items = []
        for tok in text.split():
            cleaned = tok.strip(' \t;,.-—•·')
            if cleaned.isdigit() and 1 <= int(cleaned) <= 10 and buffer:
                phrase = ' '.join(buffer).strip(' \t;,.-—•·')
                if phrase:
                    items.append((phrase, int(cleaned)))
                buffer = []
            else:
                buffer.append(tok)
        leftover = ' '.join(buffer).strip()
        return items, leftover

    def _handle_item(self, user_id, text, session):
        # Можно писать и по пунктам (каждый на своей строке), и в строчку
        # (все подряд, оценка закрывает предыдущую фразу) — оба варианта
        # добавляют сразу несколько пунктов, ничего не теряя.
        if '\n' in text.strip():
            self._handle_multiline_items(user_id, text, session)
            return

        tokenized_items, leftover = self._tokenize_happiness_items(text)
        if len(tokenized_items) >= 2:
            note = None
            if leftover:
                note = f"Не смог разобрать хвост «{leftover}» — пришли отдельно в формате «Что радует 9»."
            self._add_happiness_items(user_id, session, tokenized_items, note=note)
            return

        self._handle_single_item(user_id, text, session)

    def _handle_multiline_items(self, user_id, text, session):
        parsed_items, invalid_lines = self._split_happiness_lines(text)

        if not parsed_items:
            self.send_message(
                user_id,
                "❌ Не смог распознать ни одной строки.\n"
                "· Нужно на каждой строке: Что радует 9 (слово + пробел + оценка)\n"
                "· Пример: Кофе утром 8",
                exercise_keyboard()
            )
            return

        note = None
        if invalid_lines:
            note = f"Не распознал {len(invalid_lines)} строк(и) — пришли их отдельно в формате «Что радует 9»."

        self._add_happiness_items(user_id, session, parsed_items, note=note)

    def _add_happiness_items(self, user_id, session, parsed_items, note=None):
        """Добавляет несколько распознанных (текст, оценка) пар сразу —
        используется и для списка по пунктам, и для строки-вперемешку без
        переносов. Одним сообщением подтверждает все добавленные пункты."""
        for item_text, score in parsed_items:
            session['items'].append({'text': item_text, 'score': score})

        self.save_progress(user_id, {'items': session['items']})

        count = len(session['items'])
        progress = self._get_progress_bar(count, target=MAX_EXERCISE_ITEMS)
        milestone = self._milestone_line(count, target=MAX_EXERCISE_ITEMS)
        milestone_text = f"{milestone}\n" if milestone else ""

        MAX_LISTED = 10
        shown_items = parsed_items[:MAX_LISTED]
        listed = "\n".join(
            f"{i + 1}. {self._score_emoji(score)} «{self._item_text_for_display(item_text)}» — {score}/10"
            for i, (item_text, score) in enumerate(shown_items)
        )
        if len(parsed_items) > MAX_LISTED:
            listed += f"\n…и ещё {len(parsed_items) - MAX_LISTED} — уже в списке, ниже общий счёт"

        note_text = f"\n\n⚠️ {note}" if note else ""

        if count >= MAX_EXERCISE_ITEMS:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} пунктов счастья!\n"
                f"{listed}\n"
                f"{progress}{note_text}\n\n"
                "Нажми «➡️ Продолжить», чтобы сохранить результат.",
                exercise_keyboard()
            )
            return

        self.send_message(
            user_id,
            f"✅ Добавлено пунктов: {len(parsed_items)}\n"
            f"{listed}\n\n"
            f"{progress}\n"
            f"{milestone_text}"
            f"Всего: {count}/{MAX_EXERCISE_ITEMS}{note_text}\n\n"
            "Пиши следующий пункт (можно сразу списком), а когда закончишь — жми «➡️ Продолжить»",
            exercise_keyboard()
        )

    def _handle_single_item(self, user_id, text, session):
        parts = text.rsplit(' ', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            self.send_message(
                user_id,
                "❌ Формат: Что радует 9 (число от 1 до 10)\n"
                "Пример: Кофе утром 8",
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

        # Пользователь обычно пишет "Текст — 8" — rsplit оставляет тире в
        # конце item_text ("Текст —"), а дальше при показе добавляется ещё
        # одно " — {score}/10" — получалось двойное тире ("Текст — — 8/10").
        # Убираем висящее тире/дефис на конце, чтобы не дублировалось.
        item_text = parts[0].strip().rstrip('-—–').strip()
        session['items'].append({'text': item_text, 'score': score})

        self.save_progress(user_id, {'items': session['items']})

        count = len(session['items'])
        progress = self._get_progress_bar(count, target=MAX_EXERCISE_ITEMS)
        milestone = self._milestone_line(count, target=MAX_EXERCISE_ITEMS)
        milestone_text = f"{milestone}\n" if milestone else ""

        if count >= MAX_EXERCISE_ITEMS:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} пунктов счастья!\n"
                f"{progress}\n\n"
                "Нажми «➡️ Продолжить», чтобы сохранить результат.",
                exercise_keyboard()
            )
        else:
            self.send_message(
                user_id,
                f"✅ Добавлено! {count}/{MAX_EXERCISE_ITEMS}\n"
                f"{progress}\n"
                f"{milestone_text}\n"
                f"📌 {self._score_emoji(score)} {item_text} — {score}/10\n\n"
                "Пиши следующий пункт (можно сразу списком), а когда закончишь — жми «➡️ Продолжить»",
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

        if not self.save_result(user_id, {'items': items, 'total': len(items)}):
            self._report_save_failure(user_id, session, main_menu())
            return False
        self.delete_progress(user_id)
        self.end_session(user_id)

        avg_score = sum(i['score'] for i in items) / len(items)

        self.send_message(
            user_id,
            f"✨ ПУТЬ ЗАВЕРШЁН\n\n"
            f"📋 Собрано: {len(items)} пунктов счастья\n"
            f"📊 Средняя оценка: {avg_score:.1f}/10\n\n"
            f"Топ-3:\n" + "\n".join(
                f"  · {self._score_emoji(i['score'])} {self._item_text_for_display(i['text'])} ({i['score']}/10)"
                for i in sorted(items, key=lambda x: x['score'], reverse=True)[:3]
            ) + "\n\n✨ Сохраняй этот список и дополняй!",
            main_menu()
        )
        return True

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, {'items': session.get('items', [])})
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Прогресс сохранён\n"
            "Возвращайся, чтобы продолжить ✨",
            main_menu()
        )