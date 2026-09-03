import threading
import time
from datetime import datetime, timedelta
import logging
from vk_api.exceptions import ApiError
import requests

logger = logging.getLogger(__name__)

# Коды ошибок VK API для флуд-контроля: 6 — "Too many requests per second",
# 9 — "Flood control". При них нет смысла долбить дальше в этом же цикле —
# следующие сообщения только упрутся в ту же стену; следующий цикл (через
# ~60с) сам подхватит оставшиеся due-уведомления/комментарии заново.
FLOOD_CONTROL_CODES = (6, 9)

# HTTP-код флуд-контроля Telegram Bot API (аналог VK-кодов выше) — Telegram
# на превышение лимита отвечает 429 Too Many Requests, TelegramAdapter._call()
# поднимает его как requests.exceptions.HTTPError (через
# response.raise_for_status()), см. platform_bots/telegram_adapter.py::send_text.
TELEGRAM_FLOOD_STATUS = 429


class NotificationSystem:
    def __init__(self, vk_session, api_client, platform='vk'):
        """vk_session — для VK (platform='vk', по умолчанию, поведение не
        меняется ни на бит) настоящий VkApi, self.vk.method(...) вызывается
        напрямую, как и раньше. Для Telegram (platform='telegram') —
        TelegramAdapter (platform_bots/telegram_adapter.py, main_telegram.py,
        шаг 4 плана platform_bots/README.md): используем его send_text(), а
        НЕ send_message() — send_message глотает исключения (это нужно
        упражнениям, чтобы сбой одной отправки не ронял диалог, см.
        exercises/base.py), а этому классу, наоборот, нужно самому знать,
        ушло сообщение или нет — для флуд-контроля и ретраев, точно как с
        VK ApiError. Имя self.vk сохранено для обоих случаев — как и в
        exercises/base.py/handlers.py, это исторически "сессия/адаптер
        текущей платформы", не обязательно именно VK.
        platform — какое поле ID читать из due-уведомлений/комментариев (см.
        _extract_platform_user_id) и какой путь отправки использовать."""
        self.vk = vk_session
        self.api = api_client
        self.platform = platform
        self.running = False
        self.thread = None
        self._last_send_flood_control = False

    def send_message(self, user_id, message):
        """Никогда не бросает исключение наружу — вызывающий код (рассылка
        напоминаний) не должен падать из-за сбоя одной отправки. Возвращает
        True/False; при флуд-контроле (VK ApiError code 6/9 или Telegram
        HTTP 429) дополнительно взводит self._last_send_flood_control, чтобы
        вызывающий код мог отличить его от обычного сбоя и не долбить
        дальше в этом же цикле."""
        self._last_send_flood_control = False
        if self.platform == 'telegram':
            return self._send_telegram(user_id, message)
        return self._send_vk(user_id, message)

    def _send_vk(self, user_id, message):
        from vk_api.utils import get_random_id
        try:
            self.vk.method('messages.send', {
                'user_id': user_id,
                'message': message,
                'random_id': get_random_id()
            })
            return True
        except ApiError as e:
            if getattr(e, 'code', None) in FLOOD_CONTROL_CODES:
                self._last_send_flood_control = True
                logger.error(f"Флуд-контроль VK (code={e.code}) при отправке пользователю {user_id} — придётся подождать: {e}")
            else:
                logger.error(f"Send message error to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Send message error to {user_id}: {e}")
            return False

    def _send_telegram(self, user_id, message):
        try:
            self.vk.send_text(user_id, message)
            return True
        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, 'status_code', None)
            if status == TELEGRAM_FLOOD_STATUS:
                self._last_send_flood_control = True
                logger.error(f"Флуд-контроль Telegram (429) при отправке пользователю {user_id} — придётся подождать: {e}")
            else:
                logger.error(f"Send message error to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Send message error to {user_id}: {e}")
            return False

    def start(self):
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._check_loop, daemon=True)
        self.thread.start()
        logger.info("Notification system started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Notification system stopped")
    
    def _check_loop(self):
        while self.running:
            try:
                self._check_notifications()
            except Exception as e:
                logger.error(f"Notification check error: {e}")
            time.sleep(60)
    
    def _mark_with_retry(self, mark_fn, *args, attempts=3, delay=1.0):
        """mark_notification_sent/mark_comment_sent — вызывается ПОСЛЕ
        успешной отправки сообщения, поэтому сбой здесь означает риск
        повторной отправки того же самого на следующем цикле (~60с). Один
        транзиентный сбой сети не должен сразу приводить к дублю — пробуем
        ещё пару раз с короткой паузой, прежде чем сдаться и залогировать."""
        for attempt in range(1, attempts + 1):
            if mark_fn(*args):
                return True
            if attempt < attempts:
                time.sleep(delay)
        return False

    def _extract_platform_user_id(self, record):
        """due-уведомления и pending-комментарии психолога теперь несут ОБА
        поля — user_vk_id и user_telegram_id (см.
        bot_api/serializers.py::NotificationSerializer,
        bot_api/views.py::pending_admin_comments) — потому что общие
        /notifications/due/ и /admin/review/pending_admin_comments/ НЕ
        фильтруют по платформе на сервере: оба фоновых процесса (VK и
        Telegram, у каждого свой systemd-сервис, свой NotificationSystem)
        видят один и тот же список целиком и должны сами понять, какие
        записи их, а какие — не их.

        Возвращает (id или None, belongs_to_other_platform):
        - есть свой id -> (id, False) — обработать как обычно
        - своего нет, но есть чужой -> (None, True) — запись для другой
          платформы, это ОЖИДАЕМАЯ ситуация при совместной работе VK- и
          Telegram-бота, а не ошибка — пропустить молча, без warning
        - нет вообще ни одного -> (None, False) — битая запись (например
          пользователь был удалён на сервере) — как и раньше, залогировать
          warning"""
        own_key = 'user_telegram_id' if self.platform == 'telegram' else 'user_vk_id'
        other_key = 'user_vk_id' if self.platform == 'telegram' else 'user_telegram_id'
        own_id = record.get(own_key)
        if own_id:
            return own_id, False
        return None, bool(record.get(other_key))

    def _check_notifications(self):
        own_field_name = 'user_telegram_id' if self.platform == 'telegram' else 'user_vk_id'
        due = self.api.get_due_notifications()
        # Защита от повторной отправки ОДНОГО И ТОГО ЖЕ пункта дважды в
        # рамках одного цикла (баг #6), даже если backend вернул его
        # повторно или mark_notification_sent не подтвердится ниже.
        sent_ids_this_cycle = set()

        for notif in due:
            try:
                user_id, other_platform = self._extract_platform_user_id(notif)
                notif_id = notif.get('id')

                if not user_id:
                    if other_platform:
                        continue
                    logger.warning(f"Не найден {own_field_name} в уведомлении: {notif}")
                    continue

                if notif_id in sent_ids_this_cycle:
                    continue

                text = self._get_reminder_text(notif.get('exercise_type'))
                sent = self.send_message(int(user_id), text)
                if not sent:
                    if self._last_send_flood_control:
                        logger.error(
                            "Флуд-контроль — прекращаю рассылку уведомлений в этом цикле, "
                            "остальные попробуем в следующем цикле (~60с)"
                        )
                        return
                    logger.error(f"Send reminder error to {user_id}")
                    continue

                sent_ids_this_cycle.add(notif_id)
                logger.info(f"Отправлено уведомление пользователю {user_id}: {notif.get('exercise_type')}")

                if not self._mark_with_retry(self.api.mark_notification_sent, notif_id):
                    logger.error(
                        f"КОМАНДЕ: возможен повторный показ, mark_sent не подтвердился "
                        f"даже после повторных попыток (уведомление id={notif_id}, "
                        f"пользователь={user_id})"
                    )
            except Exception as e:
                # Одна битая запись (например нечисловой ID) не должна
                # останавливать обработку остальных due-уведомлений и тем
                # более блока комментариев психолога ниже — раньше
                # необработанное исключение здесь прерывало весь цикл,
                # включая ежедневные напоминания на сегодня без окна для
                # повторной попытки.
                logger.error(f"Ошибка обработки уведомления {notif!r}: {e}")

        sent_keys_this_cycle = set()
        pending_comments = self.api.get_pending_admin_comments()
        # Одно сообщение VK/Telegram ограничено ~4096 символами; оставляем
        # запас под префикс с названием упражнения — см. _item_text_for_display
        # в stress_search.py, тот же принцип обрезки длинного текста.
        MAX_COMMENT_LEN = 3500
        for c in pending_comments:
            try:
                review_id = c.get('review_id')
                comment_index = c.get('comment_index')
                user_id, other_platform = self._extract_platform_user_id(c)
                exercise_type = c.get('exercise_type')
                comment_text = c.get('text') or ''
                key = (review_id, comment_index)
                if key in sent_keys_this_cycle:
                    continue
                if not user_id:
                    if other_platform:
                        continue
                    logger.warning(f"Не найден {own_field_name} в комментарии: {c}")
                    continue

                if len(comment_text) > MAX_COMMENT_LEN:
                    comment_text = comment_text[:MAX_COMMENT_LEN].rstrip() + "…"

                sent = self.send_message(
                    int(user_id),
                    f"💬 Комментарий наблюдателя по упражнению «{exercise_type}»:\n\n{comment_text}"
                )
                if not sent:
                    if self._last_send_flood_control:
                        logger.error(
                            "Флуд-контроль — прекращаю рассылку комментариев в этом цикле, "
                            "остальные попробуем в следующем цикле (~60с)"
                        )
                        return
                    logger.error(f"Send admin comment error to {user_id}")
                    continue  # не помечать отправленным — иначе комментарий психолога потеряется навсегда

                sent_keys_this_cycle.add(key)
                if not self._mark_with_retry(self.api.mark_comment_sent, review_id, comment_index):
                    logger.error(
                        f"КОМАНДЕ: возможен повторный показ, mark_sent не подтвердился "
                        f"даже после повторных попыток (комментарий review_id={review_id} "
                        f"comment_index={comment_index})"
                    )
            except Exception as e:
                logger.error(f"Ошибка обработки комментария {c!r}: {e}")

    def _get_reminder_text(self, exercise_type):
        texts = {
            'diary': "📖 Доброе утро! Пора вспомнить сон и записать его в дневник.",
            # Одноразовое напоминание через час после утренней части дневника
            # (см. exercises/diary.py::_show_block_boundary) — отдельный
            # псевдо-тип, а не 'diary', потому что текст здесь другой: сон
            # уже записан, зовём на дневную часть (настроение/тело/мысли/хочу),
            # а не снова спрашиваем про сон.
            'diary_day': "☀️ Прошёл час — загляни в дневник, продолжим дневную часть "
                         "(настроение, тело, мысли, чего хочешь).",
            'stop_technique': "🛑 Пауза. Здесь и сейчас: о чём думаешь, что чувствуешь, чего хочешь?",
            'stress_search': "🎯 Поиск стресса — продолжим искать источники напряжения?",
            'happiness_list': "✨ Список счастья — что приносит тебе радость сегодня?",
            'my_roles': "🎭 Мои роли — какие роли ты играешь сегодня?",
            'conscious_choice': "🧘 Осознанный выбор — время сделать выбор.",
            'general': "🔦 Пора продолжить свой путь наблюдателя.",
        }
        return texts.get(exercise_type, texts['general'])
    
    def setup_diary_reminder(self, user_id, time_str="08:00"):
        schedule_data = {"time": time_str, "type": "morning"}
        return self.api.create_notification(
            user_id,
            "diary",
            "daily",
            schedule_data
        )
    
    def setup_stop_technique_reminder(self, user_id, times):
        results = []
        for t in times:
            schedule_data = {"time": t, "type": "stop_technique"}
            result = self.api.create_notification(
                user_id,
                "stop_technique",
                "daily",
                schedule_data
            )
            results.append(result)
        return results
    
    def setup_reminder_to_continue(self, user_id, exercise_type, hours=24):
        schedule_data = {"delay_hours": hours, "exercise_type": exercise_type}
        return self.api.create_notification(
            user_id,
            exercise_type,
            "once",
            schedule_data
        )
    
    def send_reminder(self, user_id, message):
        self.send_message(user_id, message)