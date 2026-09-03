from keyboards import main_menu, exercises_menu, get_reminder_keyboard, back_keyboard
from api_client import APIClient
from vk_adapter import VkAdapter
from keyboards import main_menu, exercises_menu, get_reminder_keyboard, stress_search_parts_keyboard, results_keyboard, account_link_menu_keyboard
from config import GROUP_ID, TELEGRAM_BOT_USERNAME
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

    def _results_unavailable_notice(self, user_id):
        """Вызывать, когда get_user_results() вернул None — это сбой
        сети/сервера, а НЕ «упражнений действительно нет». Раньше оба
        случая маскировались под [] (см. api_client.py::get_user_results),
        и при временном сбое пользователю показывалось «путь пуст»/«нет
        пройденных упражнений», хотя история могла быть совсем не пустой."""
        self.send_message(
            user_id,
            "⚠️ Не получилось загрузить твою историю — сервис временно "
            "недоступен. Попробуй зайти чуть позже.",
            main_menu()
        )

    def show_review_menu(self, user_id):
        results = self.api.get_user_results(user_id)
        if results is None:
            self._results_unavailable_notice(user_id)
            return
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
        results = self.api.get_user_results(user_id)
        if results is None:
            self._results_unavailable_notice(user_id)
            return
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

        if results is None:
            self._results_unavailable_notice(user_id)
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
        
    def __init__(self, vk_session, api_platform='vk', start_notifications=True):
        """vk_session — как и раньше, обычно настоящий VkApi (для VK-бота,
        vk_bot/main.py). Может быть и любым объектом с интерфейсом
        MessagingAdapter (см. platform_bots/base_adapter.py) — например
        TelegramAdapter из main_telegram.py, шаг 4 плана
        platform_bots/README.md; в этом случае send_message ниже отправляет
        через него напрямую, без обёртки VkAdapter (см. exercises/base.py —
        тот же приём).
        api_platform — 'vk' (по умолчанию) или 'telegram', передаётся в
        APIClient, чтобы сервер искал/создавал пользователя по правильному
        полю (vk_id или telegram_id, см. bot_api/models.py::User).
        start_notifications — фоновый поток NotificationSystem (шлёт
        напоминания и комментарии психолога САМ, не дожидаясь сообщения от
        пользователя) умеет отправлять и через VK, и через Telegram (см.
        notifications.py — platform=api_platform ниже выбирает нужный путь
        отправки и нужное поле ID). Параметр в основном для тестов
        (test_handlers.py — не поднимать фоновый поток на каждый тест)."""
        self.vk = vk_session
        if hasattr(vk_session, 'send_message'):
            self.platform = vk_session
        else:
            self.platform = VkAdapter(lambda: self.vk)
        self.api = APIClient(platform=api_platform)
        self.user_states = {}

        self.stress_search = StressSearchExercise(vk_session, self.api)
        self.happiness_list = HappinessListExercise(vk_session, self.api)
        self.my_roles = MyRolesExercise(vk_session, self.api)
        self.conscious_choice = ConsciousChoiceExercise(vk_session, self.api)
        self.diary = DiaryExercise(vk_session, self.api)
        self.stop_technique = StopTechniqueExercise(vk_session, self.api)

        self.notifications = NotificationSystem(vk_session, self.api, platform=api_platform)
        if start_notifications:
            self.notifications.start()

    def send_message(self, user_id, message, keyboard=None):
        try:
            self.platform.send_message(user_id, message, keyboard)
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

    def _extract_deep_link_code(self, text):
        """Код привязки, доставленный диплинком (см. _link_deep_link_hint):
        в Telegram это payload команды "/start link<код>", в VK — просто
        предзаполненное сообщение из самих цифр (у VK нет диплинков с
        произвольным payload, как у Telegram). Отдельно от ручного «Ввести
        код» (см. _confirm_link_code_and_reply) — там текст ещё прощает
        мусор вокруг цифр (пробелы, дефисы, слова), а тут наоборот — нужно
        ТОЧНОЕ совпадение формата, чтобы случайно не перехватить обычный
        ответ на упражнение как код привязки."""
        text = (text or "").strip()
        match = re.match(r'^/start\s+link(\d{6})$', text)
        if match:
            return match.group(1)
        if text.isdigit() and len(text) == 6:
            return text
        return None

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

        # Автоматическая привязка по диплинку (см. _link_deep_link_hint) —
        # проверяется здесь, ПОСЛЕ активных сессий упражнений (чтобы не
        # перехватить случайный ответ внутри упражнения), но ДО Review и до
        # экрана приветствия — иначе код потеряется в тексте комментария
        # психологу или в тексте "Привет, {имя}!". Формат кода — ровно 6
        # цифр (см. bot_api/models.py::AccountLinkCode) — реальные ответы
        # упражнений в этот формат не попадают, коллизий не бывает.
        link_code = self._extract_deep_link_code(text)
        if link_code:
            if user_id in self.user_states:
                # Уже знакомый человек в живом диалоге — как и при ручном
                # вводе кода, честно показываем и успех, и ошибку.
                self._confirm_link_code_and_reply(user_id, link_code)
                return
            # Совсем новый контакт (первое сообщение — сразу диплинк) —
            # сначала тихо проверяем код, ничего не отправляя: если он не
            # подошёл, это, скорее всего, обычное первое сообщение, которое
            # случайно состояло из 6 цифр, а не попытка привязки. Пугать
            # незнакомца "кодом устарел" не нужно — просто идём по обычной
            # ветке приветствия ниже, как будто распознавания не было.
            self.api.get_or_create_user(user_id, first_name, last_name)
            result = self.api.confirm_link_code(user_id, link_code)
            if result.get('ok'):
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "✅ Готово! Аккаунты объединены — прогресс, напоминания и "
                    "проверки теперь общие, из какого мессенджера ни зайди.",
                    main_menu()
                )
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
                'account_link', 'account_link_enter_code',
            )
            menu_entry_words = ['упражнения', 'мои результаты', 'напоминания', 'проверка', 'вся история', 'мой план на день', 'привязать аккаунт']
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
            elif "привяз" in text_clean:
                self.show_account_link_menu(user_id)
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
                    "🎯 ПОИСК СТРЕССА\n\n"
                    "🌫️ Часть 1: Собрать стресс — записываешь всё, что раздражает, бесит "
                    "и высасывает энергию (до 100 образов), каждому даёшь оценку от 1 до 10. "
                    "Просто фиксируешь то, что видишь в тумане, без разбора.\n\n"
                    "🧠 Часть 2: Разобрать стресс — берёшь уже записанные образы и по очереди "
                    "разбираешь каждый через 4 вопроса, чтобы понять, откуда берётся стресс, "
                    "и снизить его накал.\n\n"
                    "Выбери часть:",
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

        elif state == 'account_link':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            elif "получить код" in text_clean:
                result = self.api.generate_link_code(user_id)
                self.user_states[user_id] = 'main'
                if result.get('ok'):
                    minutes = result.get('expires_in_minutes', 10)
                    code = result.get('code')
                    self.send_message(
                        user_id,
                        f"🔑 Твой код: {code}\n\n"
                        f"{self._link_deep_link_hint(code)}"
                        f"Открой ДРУГОЙ мессенджер (тот, который хочешь объединить с "
                        f"этим) и пришли туда этот код обычным сообщением в течение "
                        f"{minutes} минут.",
                        main_menu()
                    )
                elif result.get('error') == 'already_linked':
                    self.send_message(
                        user_id,
                        "🔗 Твои аккаунты уже объединены — привязывать больше нечего.",
                        main_menu()
                    )
                else:
                    self.send_message(
                        user_id,
                        "⚠️ Не получилось создать код — сервис на секунду недоступен. "
                        "Попробуй ещё раз через минуту.",
                        main_menu()
                    )
            elif "ввести код" in text_clean:
                self.user_states[user_id] = 'account_link_enter_code'
                self.send_message(
                    user_id,
                    "✍️ Пришли код, который тебе показал другой мессенджер:",
                    back_keyboard()
                )
            else:
                self.send_message(user_id, "🔗 Выбери действие из кнопок.", account_link_menu_keyboard())

        elif state == 'account_link_enter_code':
            if "назад" in text_clean:
                self.user_states[user_id] = 'main'
                self.send_message(
                    user_id,
                    "🔦 Возвращаемся на перекрёсток.",
                    main_menu()
                )
            else:
                code = re.sub(r'\D', '', text or '')
                if not code:
                    self.send_message(
                        user_id,
                        "Это не похоже на код — пришли те самые цифры, которые "
                        "показал другой мессенджер.",
                        back_keyboard()
                    )
                else:
                    self._confirm_link_code_and_reply(user_id, code)

    def _link_deep_link_hint(self, code):
        """Ссылка-диплинк, чтобы код можно было доставить в другой
        мессенджер одним тапом, а не перепечатывать цифры руками (запрошено
        пользователем — «максимально удобно, просто и понятно»). VK и
        Telegram сами делают такую ссылку кликабельной в обычном тексте
        сообщения, отдельная кнопка не нужна.

        - Из VK в Telegram — t.me/<username>?start=link<код>: Telegram сам
          обрабатывает /start с параметром, подтверждение происходит без
          единого лишнего нажатия (см. _extract_deep_link_code). Показывается,
          только если в .env задан TELEGRAM_BOT_USERNAME (не секрет, просто
          не настроен по умолчанию).
        - Из Telegram в VK — vk.me/write-<GROUP_ID>?text=<код>: у VK нет
          диплинков с payload как у Telegram, зато можно предзаполнить текст
          сообщения — останется только нажать «Отправить».
        """
        if self.api.platform == 'vk':
            if not TELEGRAM_BOT_USERNAME:
                return ""
            return (
                f"👉 Или на телефоне: https://t.me/{TELEGRAM_BOT_USERNAME}?start=link{code} "
                f"— Telegram сам всё поймёт, печатать код не нужно.\n\n"
            )
        return (
            f"👉 Или на телефоне: https://vk.me/write-{GROUP_ID}?text={code} "
            f"— останется только нажать «Отправить» в VK.\n\n"
        )

    def _confirm_link_code_and_reply(self, user_id, code):
        """Общая часть подтверждения кода привязки — используется и ручным
        вводом (state == 'account_link_enter_code'), и автоматическим
        распознаванием диплинка (_extract_deep_link_code/handle_message)."""
        result = self.api.confirm_link_code(user_id, code)
        self.user_states[user_id] = 'main'
        if result.get('ok'):
            self.send_message(
                user_id,
                "✅ Готово! Аккаунты объединены — прогресс, напоминания и "
                "проверки теперь общие, из какого мессенджера ни зайди.",
                main_menu()
            )
        else:
            error_messages = {
                'invalid_or_expired': (
                    "❌ Код неверный или уже устарел (коды живут 10 минут). "
                    "Получи новый код в другом мессенджере и попробуй снова."
                ),
                'same_account': (
                    "🔗 Это код из этого же аккаунта — привязывать не к чему. "
                    "Получи код в ДРУГОМ мессенджере."
                ),
                'conflict': (
                    "⚠️ Не получилось: второй мессенджер уже привязан к "
                    "другому аккаунту."
                ),
            }
            self.send_message(
                user_id,
                error_messages.get(
                    result.get('error'),
                    "⚠️ Не получилось объединить аккаунты — сервис на секунду "
                    "недоступен. Попробуй ещё раз через минуту."
                ),
                main_menu()
            )
        return result

    def show_account_link_menu(self, user_id):
        self.user_states[user_id] = 'account_link'
        self.send_message(
            user_id,
            "🔗 ПРИВЯЗКА АККАУНТА\n\n"
            "Если пишешь боту и из VK, и из Telegram — можно объединить их в "
            "один аккаунт: прогресс, напоминания и проверки станут общими, из "
            "какого мессенджера ни зайди.\n\n"
            "1️⃣ Жми «Получить код» — покажем код на 10 минут\n"
            "2️⃣ Пришли этот код обычным сообщением в ДРУГОЙ мессенджер\n\n"
            "Или наоборот: если код уже показали в другом мессенджере — жми "
            "«Ввести код».",
            account_link_menu_keyboard()
        )

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
        if results is None:
            self._results_unavailable_notice(user_id)
            return

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

        if results is None:
            self._results_unavailable_notice(user_id)
            return

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