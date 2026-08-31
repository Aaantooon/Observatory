from datetime import date
from .base import BaseExercise
from keyboards import (
    exercise_keyboard, finish_keyboard, back_keyboard, main_menu, cancel_keyboard, continue_keyboard,
    confirm_skip_keyboard,
    CONTINUE_TEXTS, RESTART_TEXTS, SAVE_AND_RESTART_TEXTS, CANCEL_TEXTS, ADVANCE_TEXTS,
    CONFIRM_YES_TEXTS, CONFIRM_NO_TEXTS,
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

            self.send_message(
                user_id,
                "🎭 МОИ РОЛИ\n\n" +
                self._progress_summary(session) +
                "\n\n🕯️ Продолжим с того места, где остановился?",
                continue_keyboard()
            )
            return

        session = self._fresh_session()
        self.user_sessions[user_id] = session
        self._show_instruction(user_id, session)

    PHASE_LABELS = {
        'social': 'Часть 1: Социальные роли',
        'interpersonal': 'Часть 2: Межличностные роли',
        'intrapersonal': 'Часть 3: Внутриличностные роли',
        'analyze': 'Разбор ролей',
    }

    def _progress_summary(self, session):
        """Подробная сводка для экрана 'Продолжим с того места?' — сколько
        ролей записано по каждой части, на каком этапе сейчас пользователь,
        и (для этапа разбора) сколько ролей разобрано и разобрана ли уже
        сегодняшняя."""
        social = self._count_roles(session.get('social_roles', []))
        interpersonal = self._count_roles(session.get('interpersonal_roles', []))
        intrapersonal = self._count_roles(session.get('intrapersonal_roles', []))
        total = social + interpersonal + intrapersonal

        phase = session.get('phase', 'social')
        phase_label = self.PHASE_LABELS.get(phase, phase)

        lines = [
            f"· Всего записано: {total} ролей",
            f"  — Социальных: {social}",
            f"  — Межличностных: {interpersonal}",
            f"  — Внутриличностных: {intrapersonal}",
            f"· Сейчас: {phase_label}",
        ]

        if phase == 'analyze':
            all_roles_count = social + interpersonal + intrapersonal
            analyzed = len(session.get('analysis_results', []))
            lines.append(f"· Разобрано ролей: {analyzed} из {all_roles_count}")
            if self._used_analysis_today(session):
                lines.append("· Сегодняшняя роль уже разобрана ✅")
            else:
                lines.append("· Сегодня ещё не разбирал(а) роль")

        return "\n".join(lines)

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
                "Или вставь сразу список — каждая роль с новой строки, я разложу по пунктам\n"
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
                "Или вставь сразу список — каждая роль с новой строки, я разложу по пунктам\n"
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
                "Или вставь сразу список — каждая роль с новой строки, я разложу по пунктам\n"
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

        if session.get('_confirm_empty_phase'):
            if text_lower in CONFIRM_YES_TEXTS:
                session.pop('_confirm_empty_phase', None)
                self._advance_phase(user_id, session)
                return
            if text_lower in CONFIRM_NO_TEXTS:
                session.pop('_confirm_empty_phase', None)
                self._show_instruction(user_id, session)
                return
            self.send_message(
                user_id,
                "🕯️ Нажми «✅ Да, дальше» или «✏️ Нет, буду писать».",
                confirm_skip_keyboard()
            )
            return

        if text_lower in ADVANCE_TEXTS:
            self._handle_phase_complete(user_id, session)
            return

        phase = session.get('phase')

        if phase == 'social':
            items = self._split_roles(text)
            session['social_roles'].extend(items)
            self.save_progress(user_id, session)
            self._send_roles_added(user_id, items, self._count_roles(session['social_roles']))

        elif phase == 'interpersonal':
            items = self._split_roles(text)
            session['interpersonal_roles'].extend(items)
            self.save_progress(user_id, session)
            self._send_roles_added(user_id, items, self._count_roles(session['interpersonal_roles']))

        elif phase == 'intrapersonal':
            items = self._split_roles(text)
            session['intrapersonal_roles'].extend(items)
            self.save_progress(user_id, session)
            self._send_roles_added(user_id, items, self._count_roles(session['intrapersonal_roles']), target=10)

        elif phase == 'analyze':
            self._handle_analysis(user_id, text, session)

    def _split_roles(self, text):
        """Разбивает вставленный текст на отдельные роли — по переносам
        строк, а внутри каждой строки ещё и по ';' (частый случай: человек
        вставляет сразу целый список одним сообщением, каждая роль на
        своей строке и/или через точку с запятой). Пустые куски и висящие
        знаки препинания по краям убираются."""
        items = []
        for line in text.split('\n'):
            for part in line.split(';'):
                cleaned = part.strip(' \t;,.-—•·')
                if cleaned:
                    items.append(cleaned)
        return items

    def _send_roles_added(self, user_id, items, count, target=20):
        if not items:
            self.send_message(
                user_id,
                "🤔 Не нашёл в этом сообщении ни одной роли — попробуй ещё раз.",
                exercise_keyboard()
            )
            return

        if count >= target:
            self.send_message(
                user_id,
                f"🎉 Отлично! Ты собрал {count} ролей в этом разделе.\n"
                "Нажми «➡️ Продолжить», чтобы перейти дальше.",
                exercise_keyboard()
            )
            return

        if len(items) == 1:
            self.send_message(
                user_id,
                f"✅ Добавлено: {items[0]} ({count}/{target})\n\n"
                "Пиши следующую роль, а когда закончишь раздел — жми «➡️ Продолжить»",
                exercise_keyboard()
            )
        else:
            listed = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
            self.send_message(
                user_id,
                f"✅ Добавлено ролей: {len(items)}\n"
                f"{listed}\n\n"
                f"Всего в этом разделе: {count}/{target}\n\n"
                "Можешь писать по одной роли или сразу списком (каждая — с новой строки) — "
                "а когда закончишь раздел, жми «➡️ Продолжить»",
                exercise_keyboard()
            )

    PHASE_ROLE_KEY = {
        'social': 'social_roles',
        'interpersonal': 'interpersonal_roles',
        'intrapersonal': 'intrapersonal_roles',
    }

    def _handle_phase_complete(self, user_id, session):
        phase = session.get('phase')
        role_key = self.PHASE_ROLE_KEY.get(phase)

        if role_key is not None and len(session.get(role_key, [])) == 0:
            # Пользователь жмёт "Продолжить", ничего не записав в этом
            # разделе — переспрашиваем перед тем, как оставить раздел
            # пустым, вместо того чтобы молча пропускать его.
            session['_confirm_empty_phase'] = True
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                "🤔 Ты пока ничего не написал(а) в этом разделе.\n"
                "Точно хочешь оставить его пустым и пойти дальше?",
                confirm_skip_keyboard()
            )
            return

        self._advance_phase(user_id, session)

    def _advance_phase(self, user_id, session):
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
        """Собирает роли из всех 3 частей в один список для анализа.

        Каждый элемент дополнительно прогоняется через _split_roles — это
        самовосстановление для старых записей, сохранённых ДО того, как
        появилась разбивка вставленного списка на пункты (если пользователь
        когда-то вставил сразу несколько ролей одним сообщением, и это
        сохранилось как одна строка-'простыня' с ';' и переносами строк).
        Для уже нормальных (атомарных) ролей это no-op — _split_roles
        вернёт список из одного того же элемента."""
        roles = []
        for key in ('social_roles', 'interpersonal_roles', 'intrapersonal_roles'):
            for item in session.get(key, []):
                roles.extend(self._split_roles(item))
        return roles

    def _count_roles(self, roles):
        """Число атомарных ролей в списке — так же самовосстанавливается
        для старых 'простынёй' (см. _all_roles)."""
        return sum(len(self._split_roles(item)) for item in roles)

    def _today_str(self):
        return date.today().isoformat()

    def _used_analysis_today(self, session):
        return session.get('last_analysis_date') == self._today_str()

    def _mark_analysis_today(self, session):
        session['last_analysis_date'] = self._today_str()

    def _send_daily_limit_message(self, user_id, session):
        self.send_message(
            user_id,
            "✅ Сегодняшняя роль уже разобрана — большего за день и не нужно.\n"
            "🌙 Возвращайся завтра, чтобы продолжить разбор следующей роли.\n\n"
            "Хочешь остановиться здесь — жми «💾 Сохранить и выйти».",
            cancel_keyboard()
        )

    def _analyze_roles(self, user_id, session):
        """Начинает анализ следующей роли (или завершает упражнение, если роли
        закончились) — всегда с шага 1 ('Идеально'). Не больше одной роли
        (Идеально + Ужасно) в день — если сегодня уже разобрана роль,
        показывает статус вместо новой роли."""
        all_roles = self._all_roles(session)
        index = session.get('analysis_index', 0)

        if index >= len(all_roles):
            self._finish(user_id, session)
            return

        if self._used_analysis_today(session):
            self._send_daily_limit_message(user_id, session)
            return

        role = all_roles[index]
        session['analysis_step'] = 1
        session.pop('current_ideal', None)
        self.save_progress(user_id, session)

        self.send_message(
            user_id,
            f"🎭 АНАЛИЗ РОЛИ {index+1}/{len(all_roles)}\n\n"
            f"📅 Роль на сегодня\n"
            f"📌 Роль: {role}\n\n"
            f"Немного игры: представь, что тебе заплатят $100,000,000 —\n"
            f"но только если сыграешь эту роль просто идеально.\n\n"
            f"✨ Как это будет выглядеть, если сыграть её идеально?\n\n"
            f"💬 Напиши свой ответ обычным сообщением — кнопка ниже нужна, только если хочешь сохранить и выйти",
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
                f"А теперь наоборот 😄 Как это будет выглядеть, если сыграть роль просто ужасно?\n\n"
                f"💬 Напиши свой ответ обычным сообщением — кнопка ниже нужна, только если хочешь сохранить и выйти",
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
            if self._used_analysis_today(session):
                # подстраховка: пользователь всё же написал текст, пока
                # заблокировано (например, не заметил статус) — не даём
                # начать новую роль сегодня
                self._send_daily_limit_message(user_id, session)
                return
            session['current_ideal'] = text
            session['analysis_step'] = 2
            self._mark_analysis_today(session)
            self.save_progress(user_id, session)
            self.send_message(
                user_id,
                f"📌 Роль: {role}\n\n"
                f"А теперь наоборот 😄 Как это будет выглядеть, если сыграть роль просто ужасно?\n\n"
                f"💬 Напиши свой ответ обычным сообщением — кнопка ниже нужна, только если хочешь сохранить и выйти",
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
        # Сбрасываем шаг сразу, а не только внутри _analyze_roles — иначе,
        # если следующая роль заблокирована дневным лимитом, session
        # останется со старым analysis_step == 2 от только что завершённой
        # роли, и _resume_analyze ошибочно решит, что это "недописанный
        # шаг 2" новой роли, и пропустит проверку лимита.
        session['analysis_step'] = 1
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