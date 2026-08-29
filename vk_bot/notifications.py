import threading
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class NotificationSystem:
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.running = False
        self.thread = None
    
    def send_message(self, user_id, message):
        from vk_api.utils import get_random_id
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id()
        })
    
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
    
    def _check_notifications(self):
        due = self.api.get_due_notifications()
        for notif in due:
            # Используем user_vk_id из сериализатора
            user_vk_id = notif.get('user_vk_id')
            
            if not user_vk_id:
                logger.warning(f"Не найден user_vk_id в уведомлении: {notif}")
                continue
            
            text = self._get_reminder_text(notif.get('exercise_type'))
            try:
                self.send_message(int(user_vk_id), text)
                logger.info(f"Отправлено уведомление пользователю {user_vk_id}: {notif.get('exercise_type')}")
            except Exception as e:
                logger.error(f"Send reminder error to {user_vk_id}: {e}")
                continue
            
            self.api.mark_notification_sent(notif.get('id'))

        pending_comments = self.api.get_pending_admin_comments()
        for c in pending_comments:
            try:
                self.send_message(
                    int(c['user_vk_id']),
                    f"💬 Комментарий наблюдателя по упражнению «{c['exercise_type']}»:\n\n{c['text']}"
                )
            except Exception as e:
                logger.error(f"Send admin comment error: {e}")
            self.api.mark_comment_sent(c['review_id'], c['comment_index'])

    def _get_reminder_text(self, exercise_type):
        texts = {
            'diary': "📖 Доброе утро! Пора вспомнить сон и записать его в дневник.",
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