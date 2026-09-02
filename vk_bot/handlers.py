from keyboards import main_menu, exercises_menu, get_reminder_keyboard, back_keyboard
from vk_api.utils import get_random_id
from api_client import APIClient
from keyboards import main_menu, exercises_menu, get_reminder_keyboard, stress_search_parts_keyboard, results_keyboard
from exercises.stress_search import StressSearchExercise
from exercises.happiness_list import HappinessListExercise
from exercises.my_roles import MyRolesExercise
from exercises.conscious_choice import ConsciousChoiceExercise
from exercises.diary import DiaryExercise
from exercises.stop_technique import StopTechniqueExercise
from notifications import NotificationSystem
from workload import format_daily_plan_message
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

# Кризисный протокол: фразы, при которых бот показывает контакты
# бесплатной круглосуточной психологической помощи. Список сознательно
# не исчерпывающий и не заменяет профессиональную помощь — только
# добавляет контакты, не блокирует и не подменяет обычный диалог.
CRISIS_TRIGGER_PHRASES = (
    "не хочу жить", "не хочется жить", "хочу умереть", "лучше бы я умер",
    "лучше бы я умерла", "покончить с собой", "покончить с жизнью",
    "свести счёты с жизнью", "свести счеты с жизнью", "убить себя",
    "не вижу смысла жить", "нет смысла жить", "навредить себе",
    "причинить себе вред", "порезать себя", "самоубийств",
)

CRISIS_RESOURCES_MESSAGE = (
    "Мне важно, что ты это написал(а). Если сейчас тяжело — пожалуйста, "
    "обратись за живой поддержкой прямо сейчас, не откладывая:\n\n"
    "☎️ +7 (495) 989-50-50 — Центр экстренной психологической помощи МЧС "
    "России, бесплатно, круглосуточно\n"
    "☎️ 124 (или 8-800-2000-122) — Единый телефон доверия для детей, "
    "подростков и их родителей, бесплатно, круглосуточно\n\n"
    "Ты не обязан(а) справляться с этим в одиночку."
)


class BotHandlers:

    def show_review_menu(self, user_id):
        results = self.api.get_user_results(user_id)
        if not results:
            self.send_message(user_id, "🌫️ У тебя пока нет пройденных упражнений.", main_menu())
            return

        self.user_states[user_id] = 'sending_review'
        exercises_map = {
            'stress_search': '1. Поиск стресса',
            'happiness_list': '2. Список счастья',
            'my_roles': '3. Мои роли',
            'conscious_choice': '4. Осознанный выбор',
            'diary': '5. Дневник',
            'stop_technique': '6. Стоп-техника'
        }
        done = set(r.get('exercise_type') for r in results)
        message = "📨 Отправить на проверку:\n\n"
        for ex_type, name in exercises_map.items():
            if ex_type in done:
                message += f"{name}\n"
        message += "\nНапиши номер упражнения, чтобы отправить."
        self.send_message(user_id, message, back_keyboard())

    def show_daily_plan(self, user_id):
        results = self.api.get_user_results(user_id) or []
        self.send_message(user_id, format_daily_plan_message(results), main_menu())

    def handle_send_review(self, user_id, text_clean):
        results = self.api.get_user_results(user_id)
        exercises_map = {
            '1': 'stress_search', '2': 'happiness_list', '3': 'my_roles',
            '4': 'conscious_choice', '5': 'diary', '6': 'stop_technique'
        }
        if "назад" in text_clean:
            self.user_states[user_id] = 'main'
            self.send_message(user_id, "🔦 Возвращаемся.", main_menu())
            return

        ex_type = exercises_map.get(text_clean[0]) if text_clean and text_clean[0].isdigit() else None
        if not ex_type:
            self.send_message(user_id, "Напиши номер упражнения из списка.", back_keyboard())
            return

        result = next((r for r in results if r.get('exercise_type') == ex_type), None)
        if not result:
            self.send_message(user_id, "Это упражнение ещё не пройдено.", back_keyboard())
            return

        sent = self.api.send_for_review(user_id, ex_type, result.get('result_data', {}))
        self.user_states[user_id] = 'main'
        if sent:
            self.send_message(
                user_id,
                "✅ Отправлено на проверку! Ожидай комментарий от наблюдателя.",
                main_menu()
            )
        else:
            # Раньше это сообщение отправлялось безусловно — если запрос
            # к серверу падал, клиент считал, что психолог уже видит
            # упражнение, и ждал комментарий, который никогда не придёт.
            self.send_message(
                user_id,
                "⚠️ Не получилось отправить — сервис на секунду недоступен. "
                "Попробуй ещё раз через минуту (пункт «Проверка» в меню).",
                main_menu()
            )
        
    def __init__(self, vk_session):
        self.vk = vk_session
        self.api = APIClient()
        self.user_states = {}
        
        self.stress_search = StressSearchExercise(vk_session, self.api)
        self.happiness_list = HappinessListExercise(vk_session, self.api)
        self.my_roles = MyRolesExercise(vk_session, self.api)
        self.conscious_choice = ConsciousChoiceExercise(vk_session, self.api)
        self.diary = DiaryExercise(vk_session, self.api)
        self.stop_technique = StopTechniqueExercise(vk_session, self.api)
        
        self.notifications = NotificationSystem(vk_session, self.api)
        self.notifications.start()

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

    def _normalize_text(self, text):
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F700-\U0001F77F"
            u"\U0001F780-\U0001F7FF"
            u"\U0001F800-\U0001F8FF"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA00-\U0001FA6F"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text).strip().lower()

    def _exit_to_main_menu(self, user_id):
        """Глобальный выход в главное меню словом «меню»/«помощь».
        Если пользователь был посреди упражнения — сохраняет прогресс
        перед выходом (не молча теряет ответы); при следующем выборе
        того же упражнения оно само предложит продолжить с этого места."""
        for exercise in (
            self.stress_search, self.happiness_list, self.my_roles,
            self.conscious_choice, self.diary, self.stop_technique,
        ):
            session = exercise.user_sessions.get(user_id)
            if session is not None:
                if hasattr(exercise, '_save_progress'):
                    exercise._save_progress(user_id, session)
                elif hasattr(exercise, 'save_progress'):
                    exercise.save_progress(user_id, session)
                del exercise.user_sessions[user_id]

        self.user_states[user_id] = 'main'
        self.send_message(
            user_id,
            "🔦 Возвращаемся на перекрёсток. Если было незакончено упражнение — прогресс сохранён.",
            main_menu()
        )

    def handle_message(self, user_id, text, first_name, last_name):
        # Кризисный протокол — проверяется первым делом, для ЛЮБОГО
        # сообщения независимо от того, в каком экране/упражнении сейчас
        # пользователь. Не прерывает обычную обработку — только добавляет
        # сообщение с контактами поддержки.
        text_for_crisis_check = (text or "").lower()
        if any(phrase in text_for_crisis_check for phrase in CRISIS_TRIGGER_PHRASES):
            self.send_message(user_id, CRISIS_RESOURCES_MESSAGE)

        # Глобальный выход в меню — работает с ЛЮБОГО экрана, даже посреди
        # упражнения (точное совпадение слова, не подстрока — см. грабля
        # №26 в документации проекта: подстрочная проверка теряет данные,
        # если слово встретится внутри обычного ответа пользователя).
        if user_id in self.user_states and self._normalize_text(text) in ('меню', 'помощь'):
            self._exit_to_main_menu(user_id)
            return

        # Проверка сессий упражнений — идёт ПЕРЕД перехватом Review: если
        # клиент уже в середине упражнения, его ответ должен продолжить
        # упражнение, а не улететь комментарием психологу (раньше открытый
        # Review глушил вообще всё, включая уже начатое упражнение).
        if user_id in self.stress_search.user_sessions:
            self.stress_search.handle_message(user_id, text)
            return
        if user_id in self.happiness_list.user_sessions:
            self.happiness_list.handle_message(user_id, text)
            return
        if user_id in self.my_roles.user_sessions:
            self.my_roles.handle_message(user_id, text)
            return
        if user_id in self.conscious_choice.user_sessions:
            self.conscious_choice.handle_message(user_id, text)
            return
        if user_id in self.diary.user_sessions:
            self.diary.handle_message(user_id, text)
            return
        if user_id in self.stop_technique.user_sessions:
            self.stop_technique.handle_message(user_id, text)
            return

        active_review = self.api.get_active_review(user_id)
        if active_review and active_review.get('status') == 'in_review':
            text_lower = self._normalize_text(text)
            # Пока клиент выбирает/запускает упражнение, настраивает
            # напоминания или выбирает, что отправить на проверку (ещё нет
            # активной сессии упражнения — она проверяется выше), тоже не
            # перехватываем: иначе открытый Review не даёт вообще
            # пользоваться остальным меню. Раньше сюда попадали только
            # первые клики ('напоминания'/'проверка' в главном меню) — а
            # любое дальнейшее нажатие ВНУТРИ этих разделов ('1 час',
            # 'отключить', номер упражнения, 'назад' и т.д.) не входило ни
            # в белый список, ни в in_exercise_selection, и улетало
            # психологу как комментарий вместо того, чтобы отработать —
            # разделы «Напоминания» и «Отправить на проверку» были
            # фактически недоступны при открытой проверке.
            current_state = self.user_states.get(user_id)
            in_menu_flow = current_state in (
                'selecting_exercise', 'selecting_stress_part',
                'reminders', 'sending_review',
            )
            menu_entry_words = ['упражнения', 'мои результаты', 'напоминания', 'проверка', 'вся история', 'план']
            if text_lower not in menu_entry_words and not in_menu_flow:
                comment_sent = self.api.add_comment(active_review['id'], text, is_admin=False)
                if comment_sent:
                    self.send_message(user_id, "✅ Ответ отправлен наблюдателю.", main_menu())
                else:
                    # Это ответ клиента психологу В РАМКАХ ЖИВОЙ ПРОВЕРКИ —
                    # самое чувствительное место в боте: раньше при сбое
                    # запроса сообщение всё равно считалось "отправленным",
                    # и ответ клиента терялся навсегда, а он был уверен,
                    # что психолог его видел.
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось отправить ответ — сервис на секунду недоступен. "
                        "Попробуй написать ещё раз через минуту.",
                        main_menu()
                    )
                return

        if user_id not in self.user_states:
            self.api.get_or_create_user(user_id, first_name, last_name)
            self.user_states[user_id] = 'main'
            self.send_message(
                user_id,
                "🔦 ПУТЬ НАБЛЮДАТЕЛЯ\n\n"
                f"· Привет, {first_name}!\n"
                "· Я провожу тебя через туман\n"
                "· Выбери, куда направим свет фонарика:",
                main_menu()
            )
            return

        state = self.user_states.get(user_id, 'main')
        text_clean = self._normalize_text(text)

        if state == 'main':
            if "упражнен" in text_clean:
                self.show_exercises(user_id)
            elif "истори" in text_clean:
                self.show_full_history(user_id)
            elif "результат" in text_clean or ("мои" in text_clean and "роли" not in text_clean):
                # "мои" сам по себе слишком широкий — ловит и "мои роли"
                # (название упражнения «Мои роли», набранное текстом), уводя
                # его на экран результатов вместо старта упражнения. Кнопка
                # «📊 Мои результаты» (и просто "мои результаты") всё равно
                # матчится через "результат" выше — эта ветка нужна только
                # для голого "мои" без слова "результат".
                self.show_results(user_id)
            elif "проверк" in text_clean:
                self.show_review_menu(user_id)
            elif "напомина" in text_clean:
                self.show_reminders(user_id)
            elif "план" in text_clean:
                self.show_daily_plan(user_id)
            else:
                self.send_message(
                    user_id,
                    "🔦 Используй кнопки меню, чтобы выбрать путь.",
                    main_menu()
                )

        elif state == 'selecting_exercise':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "поиск стресса" in text_clean or "стресс" in text_clean or text_clean == "1":
                self.user_states[user_id] = 'selecting_stress_part'
                self.send_message(
                    user_id,
                    "🎯 ПОИСК СТРЕССА\n\nВыбери часть:",
                    stress_search_parts_keyboard()
                )
            elif "список счастья" in text_clean or "счасть" in text_clean or text_clean == "2":
                self.user_states[user_id] = 'main'
                self.happiness_list.start(user_id)
            elif "роли" in text_clean or text_clean == "3":
                self.user_states[user_id] = 'main'
                self.my_roles.start(user_id)
            elif "осознанный выбор" in text_clean or "выбор" in text_clean or text_clean == "4":
                self.user_states[user_id] = 'main'
                self.conscious_choice.start(user_id)
            elif "дневник" in text_clean or text_clean == "5":
                self.user_states[user_id] = 'main'
                self.diary.start(user_id)
            elif "стоп" in text_clean or text_clean == "6":
                self.user_states[user_id] = 'main'
                self.stop_technique.start(user_id)
            else:
                self.send_message(
                    user_id,
                    "🔦 Выбери упражнение из списка кнопок.",
                    exercises_menu()
                )

        elif state == 'selecting_stress_part':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "часть 1" in text_clean or "собрать" in text_clean or text_clean == "1":
                self.user_states[user_id] = 'main'
                self.stress_search.start(user_id)
            elif "часть 2" in text_clean or "разобрать" in text_clean or text_clean == "2":
                self.user_states[user_id] = 'main'
                self.stress_search.start_part2(user_id)
            else:
                self.send_message(
                    user_id,
                    "🔦 Выбери часть из списка кнопок.",
                    stress_search_parts_keyboard()
                )

        elif state == 'sending_review':
            self.handle_send_review(user_id, text_clean)

        elif state == 'reminders':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "1 час" in text_clean:
                result = self.notifications.setup_reminder_to_continue(user_id, 'general', hours=1)
                if result:
                    self.send_message(user_id, "✅ Напомню через 1 час.", get_reminder_keyboard())
                else:
                    # create_notification возвращает None при сбое запроса —
                    # раньше это игнорировалось, и пользователь думал, что
                    # напоминание настроено, хотя оно не сохранилось.
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось настроить напоминание — сервис на секунду недоступен. "
                        "Попробуй ещё раз через минуту.",
                        get_reminder_keyboard()
                    )
            elif "3 часа" in text_clean:
                result = self.notifications.setup_reminder_to_continue(user_id, 'general', hours=3)
                if result:
                    self.send_message(user_id, "✅ Напомню через 3 часа.", get_reminder_keyboard())
                else:
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось настроить напоминание — сервис на секунду недоступен. "
                        "Попробуй ещё раз через минуту.",
                        get_reminder_keyboard()
                    )
            elif "завтра утром" in text_clean:
                result = self.notifications.setup_diary_reminder(user_id, "08:00")
                if result:
                    self.send_message(user_id, "✅ Напомню завтра утром в 08:00.", get_reminder_keyboard())
                else:
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось настроить напоминание — сервис на секунду недоступен. "
                        "Попробуй ещё раз через минуту.",
                        get_reminder_keyboard()
                    )
            elif "отключить" in text_clean:
                # get_notifications теперь возвращает None при сбое запроса и
                # [] только когда напоминаний правда нет (см. api_client.py) —
                # раньше оба случая маскировались под [], и сбой сети молча
                # выглядел как «отключил», хотя ничего не удалялось.
                notifications = self.api.get_notifications(user_id)
                if notifications is None:
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось получить список напоминаний — сервис на секунду недоступен. "
                        "Попробуй ещё раз через минуту.",
                        get_reminder_keyboard()
                    )
                elif not notifications:
                    self.send_message(user_id, "🔕 Активных напоминаний не найдено.", get_reminder_keyboard())
                else:
                    failed = 0
                    for n in notifications:
                        if not self.api.delete_notification(n.get('id')):
                            failed += 1
                    if failed == 0:
                        self.send_message(user_id, "🔕 Напоминания отключены.", get_reminder_keyboard())
                    else:
                        self.send_message(
                            user_id,
                            f"⚠️ Не все напоминания удалось отключить ({failed} из "
                            f"{len(notifications)} не получилось). Попробуй ещё раз через минуту.",
                            get_reminder_keyboard()
                        )
            else:
                self.send_message(user_id, "⏰ Выбери настройку из кнопок.", get_reminder_keyboard())
    def show_exercises(self, user_id):
        self.user_states[user_id] = 'selecting_exercise'

        message = (
            "🌫️ ДОРОГА К СЕБЕ\n\n"
            "1️⃣ ЛОВУШКИ ТУМАНА 🎯 — найди источники напряжения\n"
            "2️⃣ ИСКРЫ СВЕТА ✨ — вспомни, что радует\n"
            "3️⃣ ЛИЦА В ОТРАЖЕНИИ 🎭 — кто ты в этом мире\n"
            "4️⃣ РАЗВИЛКА БЕЗ СТРАХА 🧘 — научись выбирать\n"
            "5️⃣ ЗАПИСИ ПУТНИКА 📖 — запиши свои мысли\n"
            "6️⃣ МИГ ТИШИНЫ 🛑 — останови момент\n\n"
            "➡️ «Продолжить» — к разбору\n"
            "💾 «Сохранить и начать заново» — сохранить путь\n\n"
            "Зажги фонарик. Дорога ждёт."
        )

        self.send_message(user_id, message, exercises_menu())

    def show_results(self, user_id):
        results = self.api.get_user_results(user_id)
        
        streak_info = self.api.update_streak(user_id)
        streak_text = ""
        if streak_info:
            streak = streak_info.get('streak', 0)
            if streak >= 365:
                streak_text = f"👑 {streak} дней! Ты легенда!"
            elif streak >= 100:
                streak_text = f"🔥 {streak} дней! Ты монстр!"
            elif streak >= 30:
                streak_text = f"🔥 {streak} дней! Круто!"
            elif streak >= 7:
                streak_text = f"🔥 {streak} дней! Отличная привычка!"
            elif streak >= 3:
                streak_text = f"🔥 {streak} дней! Так держать!"
            elif streak == 1:
                streak_text = f"🔥 {streak} день! Начинаем!"

        if not results:
            self.send_message(
                user_id,
                "🌫️ ПУТЬ ПУСТ\n\n"
                "· Твой путь ещё пуст\n"
                "· Начни с любого упражнения\n"
                "· Свет фонарика уже ждёт тебя 🔥",
                main_menu()
            )
            return

        message = "📊 МОЙ ПУТЬ\n\n"
        
        if streak_text:
            message += f"{streak_text}\n\n"

        message += "📋 Пройденные упражнения:\n\n"

        exercises_map = {
            'stress_search': '1️⃣ Поиск стресса',
            'happiness_list': '2️⃣ Список счастья',
            'my_roles': '3️⃣ Мои роли',
            'conscious_choice': '4️⃣ Осознанный выбор',
            'diary': '5️⃣ Дневник',
            'stop_technique': '6️⃣ Стоп-техника'
        }

        completed = set()
        for res in results:
            ex_type = res.get('exercise_type')
            if ex_type in exercises_map:
                completed.add(ex_type)

        for ex_type, name in exercises_map.items():
            if ex_type in completed:
                message += f"{name} ✅ Пройдено\n"
            else:
                message += f"{name} 🔘 Не начат\n"

        message += "\n📝 Последние записи:\n\n"
        
        for res in results[:5]:
            ex_type = res.get('exercise_type')
            name = exercises_map.get(ex_type, ex_type)
            data = res.get('result_data', {})
            
            if ex_type == 'stress_search':
                count = len(data.get('items', []))
                message += f"· {name}: {count} образов\n"
            elif ex_type == 'happiness_list':
                count = len(data.get('items', []))
                message += f"· {name}: {count} пунктов\n"
            elif ex_type == 'diary':
                if data.get('mood'):
                    message += f"· {name}: {data.get('mood')[:30]}\n"
            elif ex_type == 'stop_technique':
                message += f"· {name}: #{data.get('count', 1)}\n"
            else:
                message += f"· {name}: ✅\n"

        self.send_message(user_id, message, results_keyboard(has_more=len(results) > 5))

    def show_full_history(self, user_id):
        results = self.api.get_user_results(user_id)

        if not results:
            self.send_message(
                user_id,
                "🌫️ ПУТЬ ПУСТ\n\n"
                "· Твой путь ещё пуст\n"
                "· Начни с любого упражнения",
                main_menu()
            )
            return

        exercises_map = {
            'stress_search': '1️⃣ Поиск стресса',
            'happiness_list': '2️⃣ Список счастья',
            'my_roles': '3️⃣ Мои роли',
            'conscious_choice': '4️⃣ Осознанный выбор',
            'diary': '5️⃣ Дневник',
            'stop_technique': '6️⃣ Стоп-техника'
        }

        # Ограничиваем список, чтобы не упереться в лимит длины сообщения VK (~4096 символов)
        HISTORY_LIMIT = 30
        shown = results[:HISTORY_LIMIT]

        message = f"📜 ВСЯ ИСТОРИЯ (последние {len(shown)} из {len(results)})\n\n"

        for res in shown:
            ex_type = res.get('exercise_type')
            name = exercises_map.get(ex_type, ex_type)
            data = res.get('result_data', {})
            completed_at = res.get('completed_at', '')
            date_part = completed_at[:10] if completed_at else ''

            if ex_type == 'stress_search':
                count = len(data.get('items', []))
                message += f"· {date_part} {name}: {count} образов\n"
            elif ex_type == 'happiness_list':
                count = len(data.get('items', []))
                message += f"· {date_part} {name}: {count} пунктов\n"
            elif ex_type == 'diary':
                if data.get('mood'):
                    message += f"· {date_part} {name}: {data.get('mood')[:30]}\n"
                else:
                    message += f"· {date_part} {name}: ✅\n"
            elif ex_type == 'stop_technique':
                message += f"· {date_part} {name}: #{data.get('count', 1)}\n"
            else:
                message += f"· {date_part} {name}: ✅\n"

        if len(results) > HISTORY_LIMIT:
            message += f"\n… показаны только последние {HISTORY_LIMIT} записей."

        self.send_message(user_id, message, main_menu())

    def show_reminders(self, user_id):
        self.user_states[user_id] = 'reminders'
        self.send_message(
            user_id,
            "⏰ НАПОМИНАНИЯ\n\n"
            "Ты можешь настроить напоминания:\n\n"
            "📖 Дневник — утреннее напоминание\n"
            "🛑 Стоп-техника — в течение дня\n"
            "📋 Любое упражнение — продолжить позже\n\n"
            "Выбери настройку:",
            get_reminder_keyboard()
        )