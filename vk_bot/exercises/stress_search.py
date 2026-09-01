# vk_bot/exercises/stress_search.py
import random
import logging
from vk_api.utils import get_random_id
from keyboards import (
    main_menu, exercise_keyboard, analysis_keyboard, cancel_keyboard, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
)

logger = logging.getLogger(__name__)


class StressSearchExercise:
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.user_sessions = {}

    def send_message(self, user_id, message, keyboard=None):
        try:
            self.vk.method('messages.send', {
                'user_id': user_id,
                'message': message,
                'random_id': get_random_id(),
                'keyboard': keyboard
            })
        except Exception as e:
            logger.error(f"Send message error to {user_id}: {e}")

    def _get_progress_bar(self, count, target=100):
        percent = min(100, int((count / target) * 100))
        filled = "▰" * (percent // 5)
        empty = "▱" * (20 - len(filled))
        return f"▰{filled}{empty}▱ {percent}%"

    def _get_separator(self):
        return "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

    def _score_emoji(self, score):
        """Цветовой индикатор оценки 1-10: 🔴 низкая, 🟡 средняя, 🟢 высокая."""
        if not isinstance(score, (int, float)):
            return "⚪"
        if score <= 3:
            return "🔴"
        elif score <= 6:
            return "🟡"
        return "🟢"

    def _milestone_line(self, count, target):
        """Поздравление на четверти/половине/трёх четвертях пути к target —
        None, если count не попадает ни на одну из этих отметок."""
        if not target:
            return None
        checkpoints = sorted(set(x for x in (target // 4, target // 2, target * 3 // 4) if x))
        if count not in checkpoints:
            return None
        idx = checkpoints.index(count)
        phrases = [
            "🌟 Четверть пути позади!",
            "🔥 Уже половина пути!",
            "🚀 Три четверти позади — почти у цели!",
        ]
        return phrases[idx] if idx < len(phrases) else f"🌟 {count}/{target} позади!"

    def _get_question1_hint(self):
        return (
            "· Как должно быть? Это противоположность тому, что раздражает.\n\n"
            "✍️ Пиши честно то, что первым приходит в голову — не думай, что "
            "это обязательно \"твои\" мысли. Многое из этого вложили родители, "
            "а им — их родители. Так нас и воспитали. Поэтому пиши без стеснения "
            "и зазрения совести.\n\n"
            "📌 Пример:\n"
            "«Мне не нравится ложь»\n"
            "Как должно быть? Противоположность — правда?\n"
            "Все должны говорить правду?\n"
            "Правду в моём присутствии?\n"
            "Когда я хочу?"
        )

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

    def _progress_unavailable_notice(self, user_id):
        """Вызывать, когда get_progress() вернул None — это сбой сети/сервера,
        а НЕ «прогресса действительно не было». См. base.py — тот же хелпер,
        продублирован здесь, потому что этот класс не наследует BaseExercise."""
        self.send_message(
            user_id,
            "⚠️ Не получилось загрузить твой сохранённый прогресс — сервис "
            "временно недоступен. Продолжаю с чистого листа; если прогресс "
            "был, попробуй зайти чуть позже."
        )

    def _load_progress(self, user_id):
        progress = self.api.get_progress(user_id, 'stress_search')
        if progress is None:
            self._progress_unavailable_notice(user_id)
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
            "🌫️ Туман сгущается...\n\n"
            "· Ты сохранил свой путь\n"
            "· Фонарик ждёт тебя, чтобы продолжить\n\n"
            "✨ Возвращайся, когда будешь готов",
            main_menu()
        )
        return True

    def _handle_save_and_start_over(self, user_id, session):
        self._finish_exercise(user_id, session)
        self._handle_start_over(user_id)

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
            saved['_resume_prompt'] = True
            self.user_sessions[user_id] = saved
            self.send_message(
                user_id,
                "🔦 СВЕТ В ТУМАНЕ\n\n"
                f"· Ты уже записал: {len(saved['items'])} образов\n"
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

    def start_part2(self, user_id):
        """Отдельный вход в Часть 2 (разбор стресса) — можно зайти сразу,
        не дожидаясь, пока в Части 1 нажата «Продолжить». Разбирает те
        образы, что уже записаны; если их пока нет — отправляет в Часть 1."""
        saved = self._load_progress(user_id) or self.user_sessions.get(user_id)

        if not saved or not saved.get('items'):
            self.send_message(
                user_id,
                "🌫️ У тебя пока нет ни одного образа стресса.\n"
                "Сначала пройди «🌫️ Часть 1: Собрать стресс».",
                main_menu()
            )
            return

        session = saved
        if session.get('phase') == 'collecting':
            session['phase'] = 'analysis'

        self.user_sessions[user_id] = session
        self._save_progress(user_id, session)

        if session['phase'] == 'question':
            self._resume_current_question(user_id, session)
        else:
            self._start_analysis(user_id, session)

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
            "🎯 ПОИСК СТРЕССА\n\n"
            "🌫️ Пиши источники стресса, пока не наберётся 100 пунктов: что раздражает, что выводит "
            "из себя и забирает энергию. Оценивай каждый от 1 до 10.\n\n"
            "🧠 После 100 пунктов ты начнёшь замечать стресс автоматически, ещё до того как он "
            "успеет накопиться — в этом и цель.\n\n"
            "📖 Стресс = Прогноз ⚡ Реальность\n\n"
            "📌 Формат: причина + оценка, например «Работа 8».\n"
            "💡 Можно списком — по пункту на строке, или всё в одну строку (тогда каждая оценка "
            "закрывает фразу перед собой):\n"
            "«Рецепт не выходит 8 вода не фильтруется 7 шум мешает думать 6»\n\n"
            f"{self._get_separator()}\n"
            "➡️ «Продолжить» — к разбору, когда наберёшь все образы\n"
            "💾 «Сохранить и начать заново» — сохранить как есть и начать с нуля",
            exercise_keyboard()
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
                self._restore_progress(user_id, session)
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
                "🔦 ПРОДОЛЖАЕМ ПУТЬ\n\n"
                f"· Уже записано: {count} образов\n"
                f"· {progress}\n\n"
                "🕯️ Пиши следующий образ, а когда закончишь — жми «Продолжить».",
                exercise_keyboard()
            )
        elif phase == 'analysis':
            self._start_analysis(user_id, session)
        elif phase == 'question':
            self._resume_current_question(user_id, session)

    def handle_collect(self, user_id, text, session):
        self._save_progress(user_id, session)

        t = text.lower().strip()
        if t in ADVANCE_TEXTS:
            if len(session['items']) == 0:
                self.send_message(
                    user_id,
                    "🌫️ ТУМАН ПУСТ\n\n"
                    "· Запиши хотя бы один образ\n"
                    "· 📌 Формат: Причина 9\n\n"
                    "💾 «Сохранить и выйти»",
                    cancel_keyboard()
                )
                return

            session['phase'] = 'analysis'
            self._save_progress(user_id, session)
            self._start_analysis(user_id, session)
            return

        if '\n' in text.strip():
            self._handle_multiline_collect(user_id, text, session)
            return

        tokenized_items, leftover = self._tokenize_stress_items(text)
        if len(tokenized_items) >= 2:
            note = None
            if leftover:
                note = f"Не смог разобрать хвост «{leftover}» — пришли отдельно в формате «Причина 9»."
            self._add_stress_items(user_id, session, tokenized_items, note=note)
            return

        parts = text.rsplit(' ', 1)
        if len(parts) != 2:
            self.send_message(
                user_id,
                "🌫️ ОБРАЗ НЕ ПРОЯВИЛСЯ\n\n"
                "· Нужно: Причина 9 (слово + пробел + оценка)\n"
                "· 📌 Пример: Работа 8\n\n"
                "💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
            return

        if not parts[1].isdigit():
            self.send_message(
                user_id,
                f"🌫️ НЕВЕРНАЯ ОЦЕНКА\n\n"
                f"· Оценка должна быть числом от 1 до 10\n"
                f"· Ты написал: {parts[1]}\n\n"
                f"· 📌 Пример: Работа 8\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
            return

        rate = int(parts[1])
        if not (1 <= rate <= 10):
            self.send_message(
                user_id,
                f"🌫️ ОЦЕНКА ВНЕ ДИАПАЗОНА\n\n"
                f"· Оценка должна быть от 1 до 10\n"
                f"· Ты поставил: {rate}\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
            return

        item = parts[0].strip().rstrip('-—–').strip()
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
        milestone = self._milestone_line(count, target=100)
        milestone_text = f"{milestone}\n" if milestone else ""

        self.send_message(
            user_id,
            f"🔦 ОБРАЗ #{count}\n\n"
            f"📌 {self._score_emoji(rate)} «{item}» — {rate}/10\n\n"
            f"· {progress}\n"
            f"{milestone_text}\n"
            f"{reply}\n\n"
            f"{self._get_separator()}\n"
            f"· Пиши следующий образ, а когда закончишь — жми «Продолжить»",
            exercise_keyboard()
        )

        self._save_progress(user_id, session)

    def _parse_stress_line(self, line):
        """Разбирает одну строку вида «Текст — 8» или «Текст 8» в (текст, оценка).
        Возвращает None, если строка не подходит под формат."""
        cleaned = line.strip(' \t;,.-—•·')
        if not cleaned:
            return None

        parts = cleaned.rsplit(' ', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return None

        rate = int(parts[1])
        if not (1 <= rate <= 10):
            return None

        item_text = parts[0].strip().rstrip('-—–').strip()
        if not item_text:
            return None

        return item_text, rate

    def _split_stress_items(self, text):
        """Разбивает вставленный текст на отдельные образы стресса — по
        переносам строк (частый случай: человек вставляет сразу целый
        список одним сообщением, каждый образ на своей строке)."""
        items = []
        invalid = []
        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            parsed = self._parse_stress_line(line)
            if parsed:
                items.append(parsed)
            else:
                invalid.append(line)
        return items, invalid

    def _tokenize_stress_items(self, text):
        """Разбирает ОДНУ строку вида «Фраза N Фраза N Фраза N …» без
        переносов и разделителей — каждая оценка 1-10 закрывает фразу перед
        собой и открывает следующую. Так распознаётся список, вставленный
        сплошным текстом в одну строку. Возвращает (список пар (текст,
        оценка), остаток текста после последней найденной оценки, если он
        не пуст)."""
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

    def _item_text_for_display(self, text, limit=150):
        """Обрезает текст образа для показа в списке/сводке — сам текст не
        ограничен по длине при вводе, а вставленный список может содержать
        много строк сразу, так что без этого одно сообщение может легко
        перевалить за ~4096-символьный лимит VK."""
        text = text or ''
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _add_stress_items(self, user_id, session, parsed_items, note=None):
        """Добавляет распознанные (текст, оценка) пары в сессию и одним
        сообщением подтверждает добавление — используется и для
        многострочной вставки, и для строки-вперемешку без переносов."""
        for item_text, rate in parsed_items:
            session['items'].append({'text': item_text, 'rate': rate})

        count = len(session['items'])
        progress = self._get_progress_bar(count, target=100)
        milestone = self._milestone_line(count, target=100)
        # Помимо обрезки текста каждого образа — ограничиваем и число строк,
        # реально показанных в подтверждении: одним сообщением можно
        # вставить очень длинный список, и даже при обрезке каждой строки
        # десятки строк всё равно легко перевалят за лимит VK.
        MAX_LISTED = 30
        shown_items = parsed_items[:MAX_LISTED]
        listed = "\n".join(
            f"{i + 1}. {self._score_emoji(rate)} «{self._item_text_for_display(item_text)}» — {rate}/10"
            for i, (item_text, rate) in enumerate(shown_items)
        )
        if len(parsed_items) > MAX_LISTED:
            listed += f"\n… и ещё {len(parsed_items) - MAX_LISTED}"

        message = (
            f"✅ Добавлено образов: {len(parsed_items)}\n"
            f"{listed}\n\n"
            f"· {progress}\n"
            f"Всего: {count}/100\n"
        )
        if milestone:
            message += f"{milestone}\n"
        if note:
            message += f"\n⚠️ {note}\n"
        message += (
            f"\n{self._get_separator()}\n"
            "· Пиши следующий образ (можно сразу списком) — а когда закончишь, жми «Продолжить»"
        )

        self.send_message(user_id, message, exercise_keyboard())
        self._save_progress(user_id, session)

    def _handle_multiline_collect(self, user_id, text, session):
        parsed_items, invalid_lines = self._split_stress_items(text)

        if not parsed_items:
            self.send_message(
                user_id,
                "🌫️ Не смог распознать ни одной строки.\n"
                "· Нужно на каждой строке: Причина 9 (слово + пробел + оценка)\n"
                "· 📌 Пример: Работа 8\n\n"
                "💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
            return

        note = None
        if invalid_lines:
            note = f"Не распознал {len(invalid_lines)} строк(и) — пришли их отдельно в формате «Причина 9»."

        self._add_stress_items(user_id, session, parsed_items, note=note)

    def _start_analysis(self, user_id, session):
        items = session.get('items', [])
        
        if len(items) == 0:
            self.send_message(
                user_id,
                "🌫️ Туман пуст...\n"
                "· Запиши хотя бы один образ",
                exercise_keyboard()
            )
            return

        self.send_message(
            user_id,
            "🧠 РАЗБОР ПУТИ\n\n"
            f"· У тебя {len(items)} образов\n\n"
            "· Теперь будем разбирать каждый\n"
            "· Ты увидишь, где твоя карта расходится с реальностью\n\n"
            "🎯 Цель Части 2 — научиться решать эти ситуации, чтобы потом они решались сами, "
            "автоматически, в мыслях и подсознании. Чем больше практики — тем спокойнее ты остаёшься.\n\n"
            f"{self._get_separator()}\n"
            "➡️ Нажми «Далее», чтобы начать",
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
                "➡️ Нажми «Далее»\n"
                "✅ «Завершить» — завершить путь",
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
            f"🔦 ОБРАЗ {index + 1}/{len(items)}\n\n"
            f"📌 {self._score_emoji(item['rate'])} «{item['text']}» — {item['rate']}/10\n\n"
            f"❓ Вопрос 1/4:\n"
            f"{self._get_question1_hint()}\n\n"
            f"{self._get_separator()}\n"
            f"💾 «Сохранить и выйти»",
            cancel_keyboard()
        )
        
        session['phase'] = 'question'
        self._save_progress(user_id, session)

    def _resume_current_question(self, user_id, session):
        """Повторно показывает текущий под-вопрос при возобновлении сессии,
        НЕ добавляя новую запись в session['answers'] (в отличие от
        _show_current_question, которая используется для перехода к
        следующему образу)."""
        current_item = session.get('current_item', {})
        item_text = current_item.get('text', '')
        item_rate = current_item.get('rate', '')
        total = len(session.get('items', []))
        index = session.get('question_index', 0)
        step = session.get('question_step', 1)
        answers = session.get('answers', [])
        current_answer = answers[-1] if answers else {}

        if step == 1:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"❓ Вопрос 1/4:\n"
                f"· Как должно быть?\n\n"
                f"{self._get_separator()}\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
        elif step == 2:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"❓ Вопрос 2/4:\n"
                f"· На сколько процентов это реально?\n"
                f"· Напиши число от 0 до 100\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
        elif step == 3:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n"
                f"· 📊 Реалистичность: {current_answer.get('percent', '?')}%\n\n"
                f"❓ Вопрос 3/4:\n"
                f"· Почему так должно быть?\n"
                f"· Объясни\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
        elif step == 4:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n"
                f"· 📊 Реалистичность: {current_answer.get('percent', '?')}%\n\n"
                f"❓ Вопрос 4/4:\n\n"
                f"· «Ты — пуп земли и пуп вселенной.\n"
                f"· И всё должно быть по-твоему?»\n\n"
                f"· Это нормально так думать 😊\n\n"
                f"· Важно сформулировать:\n"
                f"  · Как должно быть?\n"
                f"  · Почему?\n"
                f"  · На сколько % это реально?\n\n"
                f"· Напиши свои размышления\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
        else:
            self._show_current_question(user_id, session)

    def handle_question(self, user_id, text, session):
        text_lower = text.lower().strip()

        if text_lower in CANCEL_TEXTS:
            self._handle_cancel(user_id, session)
            return

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
            self._save_progress(user_id, session)

            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"❓ Вопрос 2/4:\n"
                f"· На сколько процентов это реально?\n"
                f"· Напиши число от 0 до 100\n\n"
                f"💾 «Сохранить и выйти»",
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
            self._save_progress(user_id, session)

            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n"
                f"· 📊 Реалистичность: {percent}%\n\n"
                f"❓ Вопрос 3/4:\n"
                f"· Почему так должно быть?\n"
                f"· Объясни\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )

        elif step == 3:
            current_answer['why'] = text
            session['question_step'] = 4
            self._save_progress(user_id, session)

            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n"
                f"· 📊 Реалистичность: {current_answer.get('percent', '?')}%\n\n"
                f"❓ Вопрос 4/4:\n\n"
                f"· «Ты — пуп земли и пуп вселенной.\n"
                f"· И всё должно быть по-твоему?»\n\n"
                f"· Это нормально так думать 😊\n\n"
                f"· Важно сформулировать:\n"
                f"  · Как должно быть?\n"
                f"  · Почему?\n"
                f"  · На сколько % это реально?\n\n"
                f"· Напиши свои размышления\n\n"
                f"💾 «Сохранить и выйти»",
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

        if not self.api.save_result(user_id, 'stress_search', result_data):
            self._save_progress(user_id, session)
            self.send_message(
                user_id,
                "⚠️ Не получилось сохранить результат — сервис на секунду недоступен.\n"
                "Ничего не потеряно, твои ответы сохранены как черновик. "
                "Попробуй завершить ещё раз через минуту.",
                main_menu()
            )
            return

        self._delete_progress(user_id)

        streak_info = self.api.update_streak(user_id)
        streak_text = ""
        if streak_info:
            streak = streak_info.get('streak', 0)
            if streak >= 365:
                streak_text = f"\n· 👑 Серия: {streak} дней! Ты легенда!"
            elif streak >= 100:
                streak_text = f"\n· 🔥 Серия: {streak} дней! Ты монстр!"
            elif streak >= 30:
                streak_text = f"\n· 🔥 Серия: {streak} дней! Круто!"
            elif streak >= 7:
                streak_text = f"\n· 🔥 Серия: {streak} дней! Отличная привычка!"
            elif streak >= 3:
                streak_text = f"\n· 🔥 Серия: {streak} дней! Так держать!"
            else:
                streak_text = f"\n· 🔥 Серия: {streak} день! Начинаем!"

        total = len(session.get('items', []))
        top = sorted(session.get('items', []), key=lambda x: x['rate'], reverse=True)[:3]
        top_text = "\n".join([
            f"  · {self._score_emoji(b['rate'])} {self._item_text_for_display(b['text'])} ({b['rate']}/10)"
            for b in top
        ])

        analyzed = len(session.get('answers', []))
        avg_percent = 0
        if analyzed > 0:
            avg_percent = sum(a.get('percent', 0) for a in session.get('answers', [])) // analyzed

        self.send_message(
            user_id,
            "✨ ПУТЬ ЗАВЕРШЁН\n\n"
            f"· 🔦 Ты осветил {total} образов в тумане\n"
            f"· 🧠 Разобрано: {analyzed}\n"
            f"· 📊 Реалистичность твоей карты: {avg_percent}%"
            f"{streak_text}\n\n"
            f"{self._get_separator()}\n"
            f"🔥 Топ-3 образа:\n{top_text}\n\n"
            f"{self._get_separator()}\n"
            f"📖 Формула стресса:\n"
            f"Стресс = Прогноз ⚡ Реальность\n\n"
            f"🌫️ Ты сделал шаг к ясности\n"
            f"· Карта становится точнее\n"
            f"· Туман рассеивается\n\n"
            f"✨ Береги себя ❤️",
            main_menu()
        )

        if user_id in self.user_sessions:
            del self.user_sessions[user_id]