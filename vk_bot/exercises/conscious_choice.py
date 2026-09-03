from .base import BaseExercise
from keyboards import (
    conscious_choice_keyboard, back_keyboard, main_menu, continue_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    BACK_TEXTS, TO_START_TEXTS, TO_END_TEXTS,
)
from config import MAX_EXERCISE_ITEMS


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
            'analysis_index': 0,
            'analysis_results': [],
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

    def _existing_items_note(self, items):
        """Как _existing_answer_note, но для экранов "Не хочу"/"Хочу"
        (choice_minus_items и т.п., см. _collect_items) — там ответ не один,
        а список пунктов, накопленных за несколько сообщений."""
        if not items:
            return ""
        listed = "\n".join(f"· {item}" for item in items)
        return f"📝 Уже добавил(а):\n{listed}\n(можно дописать ещё)\n\n"

    def _handle_start_over(self, user_id):
        self.delete_progress(user_id)
        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_step(user_id, session)

    def _handle_save_and_start_over(self, user_id, session):
        if not session.get('must_items'):
            # Нечего сохранять — ни одного пункта ещё не записано. Раньше
            # это всё равно уходило в _finish() и создавало на сервере
            # пустой результат без единого пункта.
            self.send_message(
                user_id,
                "🌫️ Пока нечего сохранять — ты ещё не добавил(а) ни одного пункта. Начинаем заново."
            )
            self._handle_start_over(user_id)
            return

        if not self._finish(user_id, session):
            # _finish() уже сообщил о сбое и сохранил текущие ответы как
            # черновик прогресса (см. _report_save_failure) — раньше сюда
            # заходили безусловно и следующей же строкой удаляли этот самый
            # черновик и открывали пустую сессию, теряя всё насовсем.
            return

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
                "🔦 ОСОЗНАННЫЙ ВЫБОР\n\n"
                f"· Ты уже записал: {len(session.get('must_items', []))} пунктов\n\n"
                "🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_step(user_id, session)

    def _format_pros_cons(self, minus_items, plus_items):
        """minus_items/plus_items — списки пунктов (см. _collect_items),
        а не единая строка, как было раньше: экраны "Не хочу"/"Хочу"
        теперь копят сколько угодно пунктов за несколько сообщений вместо
        одного ответа, который просто перезаписывался при повторном вводе."""
        minus_text = "; ".join(minus_items) if minus_items else '—'
        plus_text = "; ".join(plus_items) if plus_items else '—'
        return f"Минусы: {minus_text}, Плюсы: {plus_text}"

    def _show_step(self, user_id, session, error=None):
        step = session.get('step', 1)
        prefix = f"❌ {error}\n\n" if error else ""

        if step == 1:
            self.send_message(
                user_id,
                f"{prefix}"
                "🔦 ОСОЗНАННЫЙ ВЫБОР\n\n"
                "Туман \"надо\" прячет то, что на самом деле всегда было твоим выбором. "
                "Возьми фонарик — сейчас пройдём через него по одному пункту.\n\n"
                "Шаг 1: Что я должен?\n\n"
                "Напиши по пунктам, что ты должен делать — можно по одному, "
                "можно сразу несколько (каждый с новой строки или через «;»).\n"
                "Например:\n"
                "· Кормить детей\n"
                "· Ходить на работу\n"
                "· Заботиться о родителях\n\n"
                f"🎯 Нужно набрать {MAX_EXERCISE_ITEMS} пунктов.\n"
                "Можешь нажать «➡️ Продолжить» и раньше — прогресс сохранится.\n\n"
                "📝 Пиши пункты:",
                conscious_choice_keyboard()
            )
        elif step == 2:
            must = session.get('current_must')
            item_num = session.get('analysis_index', 0) + 1
            total = len(session.get('must_items', []))

            if session.get('_awaiting_own_affirmation'):
                # Сначала отдельным экраном — пример фразы, а следующим
                # сообщением пользователь пишет СВОЙ вариант (или жмёт
                # «Продолжить», чтобы бот сформулировал её сам) — раньше
                # пример сразу шёл в тело вопроса, и человек мог просто
                # списать его, ничего не сформулировав сам. Пример нарочно
                # строится на ДРУГОМ пункте (не на {must}) — иначе фраза
                # получалась один в один с тем, что нужно написать, и
                # списать её не требовало вообще никаких усилий.
                self.send_message(
                    user_id,
                    f"{prefix}"
                    f"🔦 Освещаем пункт {item_num}/{total}\n\n"
                    f"Шаг 2: Я имею право не хотеть.\n\n"
                    f"Написал: «{must}»\n\n"
                    f"Получается ролевые ожидания.\n"
                    f"Я должен «{must}»\n\n"
                    f"Например, если бы ты написал «Убирать за всеми», "
                    f"фраза звучала бы так:\n"
                    f"«Я имею право не хотеть убирать за всеми»\n\n"
                    f"✍️ Сформулируй сам похожую фразу — про «{must}» — своими словами. "
                    f"Или жми «➡️ Продолжить», чтобы бот сформулировал её сам.",
                    conscious_choice_keyboard()
                )
                return

            right_phrase = session.get('right_phrase') or f"Я имею право не хотеть «{must}»"
            note = self._existing_answer_note(session.get('current_answer'))
            self.send_message(
                user_id,
                f"{prefix}"
                f"Разбираем пункт {item_num}/{total}\n\n"
                f"Шаг 2: Я имею право не хотеть.\n\n"
                f"{right_phrase}\n\n"
                f"❓ Кто отнял у тебя это право не хотеть?\n"
                f"· Никто\n"
                f"· Сам отнял право\n"
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
                f"Шаг 3: Кто круче?\n\n"
                f"Ты должен: «{must}»\n"
                f"Кто запрещает тебе?: «{answer}»\n\n"
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
        elif step in (4, 5):
            # Оба номера ведут на один и тот же объединённый экран (см.
            # _show_choice_minus) — номер 5 сохранён только ради
            # back/forward-арифметики (_handle_back и т.п.) и старого
            # сохранённого прогресса.
            self._show_choice_minus(user_id, session)
        elif step == 6:
            self._show_choice_plus(user_id, session)
        elif step in (7, 8):
            # Та же логика, что и для (4, 5) — см. _show_alt_minus.
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

        # Стикер/фото/голосовое приходят из main.py как text="" — не
        # записывать пустой ответ и не продвигать шаг молча. Все шаги
        # 1-9 теперь так или иначе принимают текст (после слияния 4+5 и
        # 7+8, см. _show_choice_minus/_show_alt_minus) — только "Продолжить"
        # двигает шаг дальше, обычным текстом тут дальше не пройти.
        if not text_lower and step in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            self.send_message(
                user_id,
                "Пожалуйста, напиши текстом — я не могу обработать стикер/фото здесь.",
                conscious_choice_keyboard()
            )
            return

        if step == 1:
            items = self._split_items_text(text)
            session['must_items'].extend(items)
            self.save_progress(user_id, session)
            self._send_must_items_added(user_id, items, len(session['must_items']))

        elif step == 2:
            if session.get('_awaiting_own_affirmation'):
                session['right_phrase'] = text
                session.pop('_awaiting_own_affirmation', None)
            else:
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

        elif step in (4, 5):
            self._collect_items(user_id, session, text, 'choice_minus_items')

        elif step == 6:
            self._collect_items(user_id, session, text, 'choice_plus_items')

        elif step in (7, 8):
            self._collect_items(user_id, session, text, 'alt_minus_items')

        elif step == 9:
            self._collect_items(user_id, session, text, 'alt_plus_items')

    def _split_items_text(self, text):
        """Разбивает вставленный текст на отдельные пункты — по переносам
        строк, а внутри каждой строки ещё и по ';' (частый случай: человек
        вставляет сразу целый список одним сообщением, каждый пункт на
        своей строке и/или через точку с запятой). Пустые куски и висящие
        знаки препинания по краям убираются. Используется и для сбора
        must_items (шаг 1), и для "Не хочу"/"Хочу" (см. _collect_items) —
        по просьбе пользователя те экраны теперь копят пункты точно так же,
        как шаг 1. См. _split_roles в my_roles.py — тот же приём."""
        items = []
        for line in text.split('\n'):
            for part in line.split(';'):
                cleaned = part.strip(' \t;,.-—•·')
                if cleaned:
                    items.append(cleaned)
        return items

    def _collect_items(self, user_id, session, text, items_key):
        """Общий обработчик для экранов "Не хочу"/"Хочу" (choice_minus_items,
        choice_plus_items, alt_minus_items, alt_plus_items) — по просьбе
        пользователя они ведут себя как сбор пунктов на шаге 1: можно писать
        сколько угодно раз, по одному пункту или сразу списком, а шаг НЕ
        продвигается сам по себе — только когда человек явно нажимает
        «Продолжить» (см. _handle_next). Раньше эти четыре экрана принимали
        только один ответ и сразу переходили дальше, случайно перезаписывая
        предыдущий ввод при повторном сообщении."""
        items = self._split_items_text(text)
        if not items:
            self.send_message(
                user_id,
                "🤔 Не нашёл в этом сообщении ни одного пункта — попробуй ещё раз, "
                "или жми «Продолжить», если пунктов больше нет.",
                conscious_choice_keyboard()
            )
            return
        session.setdefault(items_key, []).extend(items)
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _send_must_items_added(self, user_id, items, count, target=MAX_EXERCISE_ITEMS):
        if not items:
            self.send_message(
                user_id,
                "🤔 Не нашёл в этом сообщении ни одного пункта — попробуй ещё раз.",
                conscious_choice_keyboard()
            )
            return

        progress = self._get_progress_bar(count, target)
        milestone = self._milestone_line(count, target)
        milestone_text = f"{milestone}\n" if milestone else ""

        if count >= target:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} пунктов.\n"
                f"{progress}\n\n"
                "Нажми «➡️ Продолжить», чтобы перейти дальше.",
                conscious_choice_keyboard()
            )
            return

        if len(items) == 1:
            self.send_message(
                user_id,
                f"✅ Добавлено: {items[0]} ({count}/{target})\n"
                f"{progress}\n"
                f"{milestone_text}\n"
                "Пиши следующий пункт, а когда закончишь — жми «➡️ Продолжить»",
                conscious_choice_keyboard()
            )
        else:
            listed = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
            self.send_message(
                user_id,
                f"✅ Добавлено пунктов: {len(items)}\n"
                f"{listed}\n\n"
                f"Всего: {count}/{target}\n"
                f"{progress}\n"
                f"{milestone_text}\n"
                "Можешь писать по одному пункту или сразу списком (каждый — с новой строки) — "
                "а когда закончишь, жми «➡️ Продолжить»",
                conscious_choice_keyboard()
            )

    def _complete_current_item(self, session):
        """Пакует разбор текущего пункта (шаги 2-9) в analysis_results и
        решает, что дальше: перейти к разбору СЛЕДУЮЩЕГО пункта (сброс на
        шаг 2 — как в stress_search) или, если пункты закончились, на шаг
        10 (финиш). Раньше единственный разбор просто шёл в _finish
        напрямую — остальные пункты списка молча оставались без анализа."""
        must = session.get('current_must')
        session.setdefault('analysis_results', []).append({
            'must': must,
            'right_phrase': session.get('right_phrase') or f"Я имею право не хотеть «{must}»",
            'who_took': session.get('current_answer'),
            'who_greater': session.get('who_greater'),
            'choice_analysis': session.get('choice_analysis', ''),
            'alternatives': session.get('alternatives', ''),
        })
        for key in ('current_answer', 'who_greater', 'choice_minus_items', 'choice_plus_items',
                    'choice_analysis', 'alt_minus_items', 'alt_plus_items', 'alternatives', 'right_phrase'):
            session.pop(key, None)

        session['analysis_index'] = session.get('analysis_index', 0) + 1
        items = session.get('must_items', [])
        if session['analysis_index'] < len(items):
            session['current_must'] = items[session['analysis_index']]
            session['step'] = 2
            session['_max_step'] = 2
            session['_awaiting_own_affirmation'] = True
        else:
            session['step'] = 10

    def _handle_back(self, user_id, session):
        step = session.get('step', 1)
        # Пол — 2, а не 1: с началом разбора (шаг 1 -> сбор пунктов уже
        # завершён и заморожен, см. _handle_next) возврата в фазу сбора
        # больше нет — там нечего редактировать, а "Назад" с первого
        # вопроса разбора раньше уводил обратно на экран сбора пунктов.
        if step <= 2:
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
        # На экране сбора (шаг 1) — некуда идти, там всего один шаг. В
        # разборе — "в начало" означает начало разбора ТЕКУЩЕГО пункта
        # (шаг 2), а не откат к уже законченному сбору пунктов.
        step = session.get('step', 1)
        session['step'] = 1 if step <= 1 else 2
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _handle_to_end(self, user_id, session):
        session['step'] = session.get('_max_step', 1)
        self.save_progress(user_id, session)
        self._show_step(user_id, session)

    def _handle_next(self, user_id, session):
        step = session.get('step', 1)

        if step == 1:
            items = session.get('must_items', [])
            if not items:
                self.send_message(
                    user_id,
                    "❌ Добавь хотя бы один пункт",
                    conscious_choice_keyboard()
                )
                return

            # Разбор идёт по КАЖДОМУ записанному пункту по очереди (см.
            # _complete_current_item) — раньше тут был индекс, который на
            # практике всегда указывал на последний добавленный пункт, и
            # разбор (шаги 2-9) проходил только для него одного, а
            # остальные до 19 пунктов оставались собраны, но не разобраны.
            session['analysis_index'] = 0
            session['analysis_results'] = []
            session['current_must'] = items[0]
            session['step'] = 2
            session['_max_step'] = 2
            session['_awaiting_own_affirmation'] = True
            session.pop('right_phrase', None)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 2:
            if session.get('_awaiting_own_affirmation'):
                # На экране примера «Продолжить» разрешён без ответа —
                # значит пользователь согласен оставить фразу как в
                # примере, а не сформулировал свою.
                session.pop('_awaiting_own_affirmation', None)
                self.save_progress(user_id, session)
                self._show_step(user_id, session)
                return
            self._show_step(user_id, session, error="Напиши свой ответ на вопрос")

        elif step == 3:
            self._show_step(user_id, session, error="Напиши свой ответ на вопрос")

        elif step in (4, 5):
            session.setdefault('choice_minus_items', [])
            session['step'] = 6
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 6:
            session.setdefault('choice_plus_items', [])
            session['choice_analysis'] = self._format_pros_cons(
                session.get('choice_minus_items', []), session.get('choice_plus_items', [])
            )
            session['step'] = 7
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step in (7, 8):
            session.setdefault('alt_minus_items', [])
            session['step'] = 9
            self._bump_max_step(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

        elif step == 9:
            session.setdefault('alt_plus_items', [])
            session['alternatives'] = self._format_pros_cons(
                session.get('alt_minus_items', []), session.get('alt_plus_items', [])
            )
            self._complete_current_item(session)
            self.save_progress(user_id, session)
            self._show_step(user_id, session)

    def _show_choice_minus(self, user_id, session):
        # Раньше это были два отдельных сообщения ("Я выбираю" с кнопкой
        # "Продолжить", и только потом отдельно "Не хочу") — слиты в одно
        # по просьбе пользователя. Экран копит пункты (choice_minus_items)
        # за сколько угодно сообщений, шаг двигает только "Продолжить" —
        # тот же приём, что и на шаге 1 (см. _collect_items).
        must = session.get('current_must')
        note = self._existing_items_note(session.get('choice_minus_items', []))
        self.send_message(
            user_id,
            f"Шаг 4: Анализ выбора\n\n"
            f"📌 Я выбираю: «{must}»\n\n"
            f"❓ Не хочу\n"
            f"Каждый раз разные примеры\n"
            f"· Дети будут голодными\n"
            f"· Будут жаловаться\n"
            f"· Будут ныть\n\n"
            f"{note}"
            f"✍️ Пиши свои минусы — по одному или сразу списком. Когда закончишь "
            f"(или если минусов нет), жми «Продолжить».",
            conscious_choice_keyboard()
        )

    def _show_choice_plus(self, user_id, session):
        # Пункт, который сейчас разбирается, нужно показывать на КАЖДОМ
        # экране анализа, а не только на первом (шаг 4) — иначе после
        # нескольких сообщений с минусами/плюсами легко потерять, о каком
        # именно "должен" идёт речь, особенно если пунктов несколько.
        must = session.get('current_must')
        note = self._existing_items_note(session.get('choice_plus_items', []))
        self.send_message(
            user_id,
            f"📌 Я выбираю: «{must}»\n\n"
            f"❓ Хочу (полезные плюсы):\n"
            f"· Увидеть улыбку на лице ребёнка\n"
            f"· Увидеть, как он радуется вкусной еде\n\n"
            f"{note}"
            f"✍️ Пиши свои плюсы — по одному или сразу списком. Когда закончишь "
            f"(или если плюсов нет), жми «Продолжить».",
            conscious_choice_keyboard()
        )

    def _show_alt_minus(self, user_id, session):
        # Та же логика слияния, что и в _show_choice_minus: раньше "Шаг 5:
        # Альтернативы" (просто "Иногда можно не делать" + кнопка
        # "Продолжить") и "Не хочу (другие минусы)" были двумя отдельными
        # сообщениями без какого-либо ввода между ними.
        must = session.get('current_must')
        note = self._existing_items_note(session.get('alt_minus_items', []))
        self.send_message(
            user_id,
            f"Шаг 5: Альтернативы\n\n"
            f"Иногда выбираю не делать это «{must}»\n\n"
            f"❓ Не хочу\n"
            f"Когда\n"
            f"· Устал сильно\n"
            f"· Не могу собраться с мыслями\n"
            f"· Мало времени\n"
            f"· Накопить стресс\n\n"
            f"{note}"
            f"✍️ Пиши свои минусы — по одному или сразу списком. Когда закончишь "
            f"(или если минусов нет), жми «Продолжить».",
            conscious_choice_keyboard()
        )

    def _show_alt_plus(self, user_id, session):
        # Та же причина, что и в _show_choice_plus — показывать разбираемый
        # пункт на каждом экране, включая последний.
        must = session.get('current_must')
        note = self._existing_items_note(session.get('alt_plus_items', []))
        self.send_message(
            user_id,
            f"Иногда выбираю не делать это «{must}»\n\n"
            f"❓ Каких плюсов хочу?\n"
            f"· Набрать энергии и с хорошим настроением\n"
            f"· Заказать что-то из доставки\n"
            f"· Попробовать что-то новое\n\n"
            f"{note}"
            f"✍️ Пиши свои плюсы — по одному или сразу списком. Когда закончишь "
            f"(или если плюсов нет), жми «Продолжить».",
            conscious_choice_keyboard()
        )

    def _finish(self, user_id, session):
        # analysis — по одной записи на КАЖДЫЙ пункт из must_items (см.
        # _complete_current_item). Раньше здесь брались current_answer/
        # who_greater/choice_analysis/alternatives напрямую из сессии —
        # это всегда были данные только ПОСЛЕДНЕГО разобранного пункта,
        # остальные до 19 пунктов терялись из итогового результата.
        result = {
            'must_items': session.get('must_items', []),
            'analysis': session.get('analysis_results', []),
        }

        if not self.save_result(user_id, result):
            self._report_save_failure(user_id, session, main_menu())
            return False
        self.delete_progress(user_id)
        self.end_session(user_id)

        analyzed = len(result['analysis'])
        self.send_message(
            user_id,
            "✨ ПУТЬ ЗАВЕРШЁН\n\n"
            f"🔦 Разобрано пунктов: {analyzed}\n\n"
            "Осознанный выбор — это свобода.\n\n"
            "· Ты имеешь право выбирать\n"
            "· Ты имеешь право не хотеть\n"
            "· Ты имеешь право делать или не делать\n\n"
            "💡 Важно:\n"
            "Пока не заболел — есть возможность.\n"
            "Ребёнок вырос — он сам готовит.\n"
            "Ребёнок не голоден — не надо кормить.\n\n"
            "🔦 Каждый раз, доставая фонарик для пункта из списка \"надо\", ты находишь "
            "дорогу, которую выбрал сам.\n\n"
            "✨ Береги себя ❤️",
            main_menu()
        )
        return True

    def _handle_cancel(self, user_id, session):
        self.save_progress(user_id, session)
        self.end_session(user_id)
        self.send_message(
            user_id,
            "🌫️ Путь подождёт в тумане\n"
            "· Прогресс сохранён\n"
            "· Фонарик ждёт тебя, чтобы продолжить\n\n"
            "✨ Возвращайся, когда будешь готов",
            main_menu()
        )
