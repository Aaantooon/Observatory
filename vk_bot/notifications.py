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
        # В реальном проекте здесь будет запрос к API
        # для получения всех активных уведомлений
        pass
    
    def setup_diary_reminder(self, user_id, time_str="08:00"):
        schedule_data = {"time": time_str, "type": "morning"}
        return self.api.create_notification(
            user_id,
            "diary",
            "daily",
            schedule_data
        )
    
    def setup_stop_technique_reminder(self, user_id, times):
        # times: ["10:00", "15:00", "20:00"]
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