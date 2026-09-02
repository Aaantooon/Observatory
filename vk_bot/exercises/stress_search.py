# vk_bot/exercises/stress_search.py
import random
import logging
from vk_api.utils import get_random_id
from keyboards import (
    main_menu, exercise_keyboard, analysis_keyboard, cancel_keyboard, continue_keyboard,
    confirm_skip_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    CONFIRM_YES_TEXTS, CONFIRM_NO_TEXTS, FINISH_AND_SEND_TEXTS,
)

# Два независимых пути закончить путь досрочно и отправить его наблюдателю
# на проверку, не дожидаясь полных 100 образов / разбора всех записанных:
#   1. Часть 1 (сбор): записано хотя бы столько образов — можно отправить
#      совсем без разбора (analysis будет пустым).
#   2. Часть 2 (разбор): разобрано (все 4 вопроса + переоценка) хотя бы
#      столько образов — можно отправить, не разбирая остальные записанные.
MIN_ITEMS_TO_FINISH_EARLY = 10
MIN_ANALYZED_TO_FINISH_EARLY = 3
# Оценка образа при записи (1-10) — это интенсивность страха/энергозатрат.
# Низкая (0-3) — фонарик уже полностью освещает образ, он не пугает, стресс
# по сути отпущен сам собой. Выше — образ ещё в тумане, заберёт время и
# энергию, с ним стоит поработать в части 2.
RELEASED_RATE_THRESHOLD = 3

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

    def _completed_answers(self, session):
        """Только ПОЛНОСТЬЮ разобранные образы (все 4 вопроса + переоценка
        new_rate). session['answers'] может содержать незавершённую запись
        для образа, который сейчас разбирается (см. _show_current_question —
        она добавляет запись ДО того, как на неё ответили) — её не нужно
        засчитывать как «разобрано» и не нужно отправлять наблюдателю как
        законченный разбор."""
        return [a for a in session.get('answers', []) if 'new_rate' in a]

    def _can_finish_early(self, session):
        """Достаточно ли уже материала, чтобы разрешить досрочное завершение
        и отправку на проверку — не дожидаясь 100 записанных образов и не
        разбирая все из них. Два независимых условия (см. MIN_ITEMS_TO_FINISH_EARLY
        / MIN_ANALYZED_TO_FINISH_EARLY в начале файла) — общая точка, которую
        должны использовать ВСЕ места, откуда можно закончить упражнение
        досрочно, чтобы пороги нельзя было обойти через другую кнопку."""
        return (
            len(session.get('items', [])) >= MIN_ITEMS_TO_FINISH_EARLY
            or len(self._completed_answers(session)) >= MIN_ANALYZED_TO_FINISH_EARLY
        )

    def _items_finish_hint(self, count):
        """Строка-подсказка про условие досрочного завершения в части 1
        (сбор образов) — показывается всегда, чтобы человек видел, сколько
        ещё нужно записать, а не просто внезапно увидел новую кнопку."""
        if count >= MIN_ITEMS_TO_FINISH_EARLY:
            return (
                f"· Записано уже {count} — можно сразу «✅ Завершить и отправить», не разбирая\n"
            )
        remaining = MIN_ITEMS_TO_FINISH_EARLY - count
        return (
            f"🔒 «✅ Завершить и отправить» откроется после {MIN_ITEMS_TO_FINISH_EARLY} "
            f"записанных (сейчас {count}, ещё {remaining})\n"
        )

    def _analyzed_finish_hint(self, analyzed):
        """То же самое, но для части 2 (разбор) — условие считается по
        числу полностью разобранных образов, а не записанных."""
        if analyzed >= MIN_ANALYZED_TO_FINISH_EARLY:
            return (
                f"✅ «Завершить и отправить» — разобрано уже {analyzed}, этого достаточно, "
                f"можно отправить наблюдателю на проверку прямо сейчас, остальное разбирать "
                f"не обязательно\n"
            )
        remaining = MIN_ANALYZED_TO_FINISH_EARLY - analyzed
        return (
            f"🔒 «✅ Завершить и отправить» откроется после разбора "
            f"{MIN_ANALYZED_TO_FINISH_EARLY} образов (сейчас разобрано {analyzed}, ещё "
            f"{remaining})\n"
        )

    def _stress_split_line(self, session):
        """Постоянная строка-счётчик по всей записанной карте (не только по
        показанным в подтверждении пунктам): сколько образов уже сами по
        себе не пугают (оценка 0-{RELEASED_RATE_THRESHOLD}, фонарик их уже
        осветил), а сколько ещё в тумане и потребуют разбора в части 2.
        Ничего из написанного не теряется — это просто карта того, что уже
        нанесено."""
        items = session.get('items', [])
        if not items:
            return ""
        released = sum(1 for i in items if i.get('rate', 0) <= RELEASED_RATE_THRESHOLD)
        scary = len(items) - released
        return f"🟢 {released} уже отпущено · 🔴 {scary} ещё пугают и заберут время на разбор\n"

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

    def _format_answers_so_far(self, current_answer):
        """Собирает уже данные пользователем ответы по текущему образу в
        компактный блок — показывается перед следующим вопросом того же
        образа, чтобы не приходилось листать переписку выше."""
        lines = []
        if current_answer.get('ideal'):
            lines.append(f"· Как, по-твоему, должно быть: {self._item_text_for_display(current_answer['ideal'])}")
        if 'percent' in current_answer:
            lines.append(f"· Реалистичность: {current_answer['percent']}%")
        if current_answer.get('why'):
            lines.append(f"· Почему: {self._item_text_for_display(current_answer['why'])}")
        if current_answer.get('reflection'):
            lines.append(f"· Размышления: {self._item_text_for_display(current_answer['reflection'])}")
        if not lines:
            return ""
        return "📝 Твои ответы:\n" + "\n".join(lines) + "\n\n"

    def _build_narrative_summary(self, current_answer, item_text, item_rate, index, total):
        """После вопроса 4/4 — вместо сухого списка «Твои ответы» собирает
        те же данные в связный разбор (по формулировке психолога) и сразу
        спрашивает новую оценку 1-10, вместо старого/новую разницу — так
        человек сам видит, изменилось ли что-то после разбора."""
        ideal = self._item_text_for_display(current_answer.get('ideal', ''))
        percent = current_answer.get('percent', 0)
        why = self._item_text_for_display(current_answer.get('why', ''))
        reflection = self._item_text_for_display(current_answer.get('reflection', ''))
        return (
            f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
            f"😖 Не нравится: «{self._item_text_for_display(item_text)}» — {item_rate}/10.\n\n"
            f"🧠 В подсознании записано: должно быть «{ideal}».\n"
            f"📊 В реальности жизни так происходит {percent}% случаев.\n"
            f"❓ Почему реальность должна поменяться: {why}\n\n"
            f"💭 {reflection}\n\n"
            f"{self._get_separator()}\n"
            f"Пока мы не поняли явление — оно целиком и полностью управляет нами. "
            f"Как только поняли — появилась возможность взять его под контроль.\n\n"
            f"Твой образ, который тебя раздражает, — это попытка взять его под контроль. "
            f"Насколько успешно получилось — тебе делать вывод.\n\n"
            f"❓ Была оценка {item_rate}/10 — какая она теперь?\n"
            f"· Напиши число от 1 до 10: понизилась, повысилась или осталась такой же"
        )

    def _build_congrats_message(self, old_rate, new_rate, index, total):
        if new_rate < old_rate:
            change_line = f"📉 Было {old_rate}/10 → стало {new_rate}/10 — стало полегче."
        elif new_rate > old_rate:
            change_line = f"📈 Было {old_rate}/10 → стало {new_rate}/10."
        else:
            change_line = f"➖ Было {old_rate}/10 → осталось {new_rate}/10."
        return (
            f"🎉 Поздравляю! Образ {index + 1}/{total} — ещё один шаг в свой страх.\n\n"
            f"{change_line}\n\n"
            f"Ты молодец, и я рад, что ты это сделал."
        )

    def _get_question1_hint(self):
        return (
            "· Какая противоположность у этого пункта?\n\n"
            "✍️ Пиши честно то, что первым приходит в голову — не думай, что "
            "это обязательно \"твои\" мысли. Многое из этого вложили родители, "
            "а им — их родители, а так вкладывало общество для управления и подчинения. "
            "Так нас и воспитали. Поэтому пиши без стеснения "
            "и зазрения совести.\n\n"
            "📌 Примеры:\n"
            "«Мне не нравится ложь» → противоположность: правда.\n"
            "«Опоздание на встречу» → противоположность: пунктуальность.\n"
            "«Медленный интернет» → противоположность: быстрый интернет."
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
        if self._can_finish_early(session):
            self._finish_exercise(user_id, session)
        elif session.get('items') or session.get('answers'):
            # Есть что-то записанное, но недостаточно, чтобы это имело смысл
            # отправлять наблюдателю — не отправляем «пустышку», честно
            # говорим об этом и просто начинаем заново.
            self.send_message(
                user_id,
                f"🌫️ Пока рано отправлять на проверку — маловато записано "
                f"(нужно хотя бы {MIN_ITEMS_TO_FINISH_EARLY} образов, либо разобрать "
                f"{MIN_ANALYZED_TO_FINISH_EARLY}). Наблюдателю ничего не отправляю, "
                f"начинаю путь заново."
            )
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
            "🎯 ОХОТА НА СТРЕСС\n\n"
            "Туман. Фонарик. Карта. Дорога.\n\n"
            "Ты идёшь сквозь туман. В руке — фонарик. Он выхватывает из темноты только то, что "
            "прямо перед тобой. Всё остальное — скрыто. Прямо как твой стресс: ты его не видишь, "
            "пока не направишь свет.\n\n"
            "🎯 Задача: выгрузи 100 триггеров — всё, что раздражает, бесит, высасывает энергию. "
            "Каждый пункт — шаг по дороге. Оцени от 1 (ерунда) до 10 (атомный взрыв).\n\n"
            "📖 Формула: Стресс = Прогноз ⚡ Реальность. Чем больше разрыв — тем ярче свет, тем "
            "виднее препятствие.\n\n"
            "🧠 Цель: после 100 пунктов туман рассеется. Ты начнёшь замечать стресс автоматически "
            "— ещё до того, как он ударит. Это и есть твоя карта.\n\n"
            "📌 Формат (на выбор):\n"
            "· списком: «Работа 8»\n"
            "· строкой: «работа 8 пробки 6 шум 7»\n\n"
            f"🩺 Отправить на проверку можно раньше 100:\n"
            f"✅ Часть 1. {MIN_ITEMS_TO_FINISH_EARLY} пунктов — отправляй без разбора "
            f"(фонарик только зажёгся).\n"
            f"✅ Часть 2. Разобрал {MIN_ANALYZED_TO_FINISH_EARLY} пункта — глубокая проработка "
            f"(осветил путь).\n\n"
            f"{self._get_separator()}\n"
            "➡️ «Продолжить» — к разбору, когда наберёшь все образы\n"
            "💾 «Сохранить и начать заново» — сохранить карту и начать путь заново\n"
            "🏆 Достижение засчитывается только после полного прохождения пути — всех 100 пунктов.\n\n"
            "Зажги фонарик. Пиши первый пункт. Дорога ждёт.",
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

        if session.get('_between_items'):
            analyzed = len(self._completed_answers(session))
            can_finish = analyzed >= MIN_ANALYZED_TO_FINISH_EARLY
            if text_lower in CONTINUE_TEXTS:
                session.pop('_between_items', None)
                self._show_current_question(user_id, session)
                return
            if can_finish and text_lower in FINISH_AND_SEND_TEXTS:
                session.pop('_between_items', None)
                self._finish_exercise(user_id, session)
                return
            if text_lower in CANCEL_TEXTS:
                self._handle_cancel(user_id, session)
                return
            if text_lower in RESTART_TEXTS:
                self._handle_start_over(user_id)
                return
            hint = (
                "🕯️ Нажми «➡️ Продолжить», «✅ Завершить и отправить», "
                "«💾 Сохранить и начать заново» или «💾 Сохранить и выйти»."
                if can_finish else
                "🕯️ Нажми «➡️ Продолжить», «💾 Сохранить и начать заново» или «💾 Сохранить и выйти»."
            )
            self.send_message(user_id, hint, exercise_keyboard(can_finish))
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
            can_finish = count >= MIN_ITEMS_TO_FINISH_EARLY
            self.send_message(
                user_id,
                "🔦 ПРОДОЛЖАЕМ ПУТЬ\n\n"
                f"· Уже записано: {count} образов\n"
                f"· {progress}\n"
                f"{self._stress_split_line(session)}\n"
                "🕯️ Пиши следующий образ, а когда закончишь — жми «Продолжить».\n"
                f"{self._items_finish_hint(count)}",
                exercise_keyboard(can_finish)
            )
        elif phase == 'analysis':
            self._start_analysis(user_id, session)
        elif phase == 'question':
            self._resume_current_question(user_id, session)

    def handle_collect(self, user_id, text, session):
        self._save_progress(user_id, session)

        t = text.lower().strip()
        if t in FINISH_AND_SEND_TEXTS:
            count = len(session['items'])
            if count >= MIN_ITEMS_TO_FINISH_EARLY:
                self._finish_exercise(user_id, session)
                return
            self.send_message(
                user_id,
                f"🌫️ Пока рано — нужно хотя бы {MIN_ITEMS_TO_FINISH_EARLY} записанных образов "
                f"(сейчас {count}). Пиши ещё — дальше уже можно будет закончить и отправить, "
                f"не разбирая их в части 2.",
                exercise_keyboard()
            )
            return

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

        if count >= 100:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ #{count}\n\n"
                f"📌 {self._score_emoji(rate)} «{item}» — {rate}/10\n\n"
                f"· {progress}\n\n"
                f"{reply}\n\n"
                f"🎉 100 пунктов набрано! Часть 1 завершена — переходим к разбору.",
                analysis_keyboard()
            )
            self._try_auto_advance(user_id, session, count)
            return

        can_finish = count >= MIN_ITEMS_TO_FINISH_EARLY
        self.send_message(
            user_id,
            f"🔦 ОБРАЗ #{count}\n\n"
            f"📌 {self._score_emoji(rate)} «{item}» — {rate}/10\n\n"
            f"· {progress}\n"
            f"{milestone_text}\n"
            f"{reply}\n\n"
            f"{self._get_separator()}\n"
            f"{self._stress_split_line(session)}"
            f"· Пиши следующий образ, а когда закончишь — жми «Продолжить»\n"
            f"{self._items_finish_hint(count)}",
            exercise_keyboard(can_finish)
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
        # десятки строк всё равно легко перевалят за лимит VK. Заодно и
        # само сообщение не превращается в простыню — свет фонарика
        # выхватывает только первые шаги. Остальные при этом НЕ потеряны —
        # они уже нанесены на карту (в session['items']), просто здесь не
        # показаны построчно; общий счёт ниже (см. _stress_split_line)
        # честно учитывает вообще все записанные образы.
        MAX_LISTED = 10
        shown_items = parsed_items[:MAX_LISTED]
        listed = "\n".join(
            f"{i + 1}. {self._score_emoji(rate)} «{self._item_text_for_display(item_text)}» — {rate}/10"
            for i, (item_text, rate) in enumerate(shown_items)
        )
        if len(parsed_items) > MAX_LISTED:
            listed += f"\n🌫️ …и ещё {len(parsed_items) - MAX_LISTED} — уже на карте, ниже общий счёт"

        message = (
            f"✅ Добавлено образов: {len(parsed_items)}\n"
            f"{listed}\n\n"
            f"· {progress}\n"
            f"{self._stress_split_line(session)}"
            f"Всего: {count}/100\n"
        )
        if note:
            message += f"\n⚠️ {note}\n"

        if count >= 100:
            message += "\n🎉 100 пунктов набрано! Часть 1 завершена — переходим к разбору."
            self.send_message(user_id, message, analysis_keyboard())
            self._try_auto_advance(user_id, session, count)
            return

        if milestone:
            message += f"{milestone}\n"

        can_finish = count >= MIN_ITEMS_TO_FINISH_EARLY
        message += (
            f"\n{self._get_separator()}\n"
            "· Пиши следующий образ (можно сразу списком) — а когда закончишь, жми «Продолжить»\n"
            f"{self._items_finish_hint(count)}"
        )

        self.send_message(user_id, message, exercise_keyboard(can_finish))
        self._save_progress(user_id, session)

    def _try_auto_advance(self, user_id, session, count, target=100):
        """Как только по итогам добавления пунктов набрано 100 (или больше) —
        сразу переводит сессию в Часть 2 (разбор), не дожидаясь, пока
        пользователь сам нажмёт «Продолжить». Так переход из Части 1 в
        Часть 2 происходит без обрыва потока, автоматически."""
        if count < target:
            return False
        session['phase'] = 'analysis'
        self._save_progress(user_id, session)
        self._start_analysis(user_id, session)
        return True

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
            if not self._can_finish_early(session):
                count = len(session.get('items', []))
                self.send_message(
                    user_id,
                    f"🌫️ Пока рано — на этом экране разбора ещё не было, а записано "
                    f"только {count} (нужно хотя бы {MIN_ITEMS_TO_FINISH_EARLY}, чтобы "
                    f"отправить без разбора). Жми «Далее», чтобы начать разбор — после "
                    f"{MIN_ANALYZED_TO_FINISH_EARLY} разобранных отправить можно будет "
                    f"в любом случае.",
                    analysis_keyboard()
                )
                return
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

    def _send_question1(self, user_id, item_text, item_rate, index, total, retry=False):
        retry_line = (
            "🔄 Может, попробуешь ещё подумать? Можешь написать разные варианты, "
            "которые приходят в голову — чем больше, тем лучше.\n\n"
            if retry else ""
        )
        self.send_message(
            user_id,
            f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
            f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
            f"❓ Вопрос 1/4:\n"
            f"{retry_line}"
            f"{self._get_question1_hint()}\n\n"
            f"{self._get_separator()}\n"
            f"💾 «Сохранить и выйти»",
            cancel_keyboard()
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

        self._send_question1(user_id, item['text'], item['rate'], index, len(items))

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
            self._send_question1(user_id, item_text, item_rate, index, total)
        elif step == 2:
            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"{self._format_answers_so_far(current_answer)}"
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
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"{self._format_answers_so_far(current_answer)}"
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
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"{self._format_answers_so_far(current_answer)}"
                f"❓ Вопрос 4/4:\n\n"
                f"· «Ты — пуп земли и пуп вселенной.\n"
                f"· И всё должно быть по-твоему?»\n\n"
                f"· Это нормально так думать 😊\n\n"
                f"· Напиши свои размышления\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )
        elif step == 5:
            self.send_message(
                user_id,
                self._build_narrative_summary(current_answer, item_text, item_rate, index, total),
                cancel_keyboard()
            )
        else:
            self._show_current_question(user_id, session)

    def handle_question(self, user_id, text, session):
        text_lower = text.lower().strip()

        # CANCEL_TEXTS уже перехвачен раньше, безусловно, в handle_message —
        # до дispatch по фазам, так что здесь его проверять не нужно.

        step = session.get('question_step', 1)
        answers = session.get('answers', [])
        current_answer = answers[-1] if answers else {}

        current_item = session.get('current_item', {})
        item_text = current_item.get('text', '')
        item_rate = current_item.get('rate', '')
        total = len(session.get('items', []))
        index = session.get('question_index', 0)

        if session.get('_confirm_ideal'):
            if text_lower in CONFIRM_YES_TEXTS:
                session.pop('_confirm_ideal', None)
                current_answer['ideal'] = session.pop('_pending_ideal', text)
                session['question_step'] = 2
                self._save_progress(user_id, session)

                self.send_message(
                    user_id,
                    f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                    f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                    f"{self._format_answers_so_far(current_answer)}"
                    f"❓ Вопрос 2/4:\n"
                    f"· На сколько процентов это реально?\n"
                    f"· Это твой прогноз — насколько ты сам считаешь и думаешь, "
                    f"что так на самом деле есть в мире.\n"
                    f"· Напиши число от 0 до 100\n\n"
                    f"💾 «Сохранить и выйти»",
                    cancel_keyboard()
                )
                return

            if text_lower in CONFIRM_NO_TEXTS:
                session.pop('_confirm_ideal', None)
                session.pop('_pending_ideal', None)
                self._send_question1(user_id, item_text, item_rate, index, total, retry=True)
                return

            self.send_message(
                user_id,
                "🕯️ Нажми «✅ Да, дальше» или «✏️ Нет, буду писать».",
                confirm_skip_keyboard()
            )
            return

        if step == 1:
            session['_pending_ideal'] = text
            session['_confirm_ideal'] = True

            self.send_message(
                user_id,
                f"🔦 ОБРАЗ {index + 1}/{total}\n\n"
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"Ты написал: «{text}»\n\n"
                f"❓ Уверен, что это противоположность — и именно так должно быть?",
                confirm_skip_keyboard()
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
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"{self._format_answers_so_far(current_answer)}"
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
                f"📌 {self._score_emoji(item_rate)} «{item_text}» — {item_rate}/10\n\n"
                f"{self._format_answers_so_far(current_answer)}"
                f"❓ Вопрос 4/4:\n\n"
                f"· «Ты — пуп земли и пуп вселенной.\n"
                f"· И всё должно быть по-твоему?»\n\n"
                f"· Это нормально так думать 😊\n\n"
                f"· Напиши свои размышления\n\n"
                f"💾 «Сохранить и выйти»",
                cancel_keyboard()
            )

        elif step == 4:
            current_answer['reflection'] = text
            session['question_step'] = 5
            self._save_progress(user_id, session)

            self.send_message(
                user_id,
                self._build_narrative_summary(current_answer, item_text, item_rate, index, total),
                cancel_keyboard()
            )

        elif step == 5:
            if not text.isdigit():
                self.send_message(
                    user_id,
                    "❌ Напиши число от 1 до 10 (только цифры)",
                    cancel_keyboard()
                )
                return

            new_rate = int(text)
            if not (1 <= new_rate <= 10):
                self.send_message(
                    user_id,
                    "❌ Число должно быть от 1 до 10",
                    cancel_keyboard()
                )
                return

            current_answer['new_rate'] = new_rate
            session['question_step'] = 0
            self._save_progress(user_id, session)

            self.send_message(
                user_id,
                self._build_congrats_message(item_rate, new_rate, index, total)
            )

            session['question_index'] += 1

            if session['question_index'] >= len(session.get('items', [])):
                self._finish_exercise(user_id, session)
            else:
                session['_between_items'] = True
                self._save_progress(user_id, session)
                analyzed = len(self._completed_answers(session))
                can_finish = analyzed >= MIN_ANALYZED_TO_FINISH_EARLY
                self.send_message(
                    user_id,
                    f"{self._get_separator()}\n"
                    f"➡️ «Продолжить» — к следующему образу\n"
                    f"{self._analyzed_finish_hint(analyzed)}"
                    f"💾 «Сохранить и начать заново» — сохранить как есть и начать с нуля\n"
                    f"💾 «Сохранить и выйти» — сохранить и вернуться позже",
                    exercise_keyboard(can_finish)
                )

    def _finish_exercise(self, user_id, session):
        result_data = {
            'type': 'stress_search',
            'items': session.get('items', []),
            'analysis': self._completed_answers(session),
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

        completed = self._completed_answers(session)
        analyzed = len(completed)
        avg_percent = 0
        if analyzed > 0:
            avg_percent = sum(a.get('percent', 0) for a in completed) // analyzed

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