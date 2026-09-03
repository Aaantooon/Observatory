import requests
import logging
from config import API_BASE_URL, API_TOKEN

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, platform='vk'):
        """platform — 'vk' (по умолчанию, как было всегда) или 'telegram'
        (см. bot_api/models.py::User.telegram_id, шаг 4 плана
        platform_bots/README.md). Определяет, какое поле сервер использует,
        чтобы найти пользователя — 'vk_id'/'user_vk_id' или
        'telegram_id'/'user_telegram_id'. Существующий код (APIClient() без
        аргумента, как в vk_bot/handlers.py) продолжает слать vk_id, как и
        раньше, ни один VK-запрос не меняется."""
        self.platform = platform
        self.base_url = API_BASE_URL
        self.headers = {
            "Authorization": f"Token {API_TOKEN}",
            "Content-Type": "application/json"
        }

    def _id_field(self, prefix=''):
        """Имя параметра с ID пользователя для текущей платформы — 'vk_id'
        (или 'user_vk_id' для эндпоинтов вроде /results/, где сервер
        исторически называет поле с префиксом user_) для VK, 'telegram_id'/
        'user_telegram_id' для Telegram."""
        return f"{prefix}{'telegram_id' if self.platform == 'telegram' else 'vk_id'}"

    def get_or_create_user(self, user_id, first_name, last_name):
        try:
            response = requests.get(
                f"{self.base_url}/users/?{self._id_field()}={user_id}",
                headers=self.headers,
                timeout=5
            )

            if response.status_code == 200:
                users = response.json()
                if users and len(users) > 0:
                    # GET-найден отдаёт список (queryset), POST-создание
                    # ниже — единственный dict. Раньше это расхождение было
                    # безобидным только потому, что вызывающий код
                    # (handlers.py) не читал возврат — но любой будущий
                    # caller словил бы код, работающий только "иногда".
                    return users[0]

            response = requests.post(
                f"{self.base_url}/users/",
                json={
                    self._id_field(): str(user_id),
                    "first_name": first_name,
                    "last_name": last_name
                },
                headers=self.headers,
                timeout=5
            )

            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.warning(f"API Error creating user: {response.status_code}")
                return {"id": user_id, self._id_field(): user_id, "first_name": first_name, "last_name": last_name}

        except Exception as e:
            logger.error(f"Network error: {e}")
            return {"id": user_id, self._id_field(): user_id, "first_name": first_name, "last_name": last_name}

    def get_exercises(self):
        try:
            response = requests.get(f"{self.base_url}/exercises/", headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []

    def save_result(self, user_vk_id, exercise_type, result_data):
        try:
            response = requests.post(
                f"{self.base_url}/results/",
                json={
                    self._id_field('user_'): str(user_vk_id),
                    "exercise_type": exercise_type,
                    "result_data": result_data
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 201:
                return response.json()
            logger.warning(f"API Error saving result: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"API save error: {e}")
            return None

    def get_user_results(self, vk_id):
        # Возвращает None при сбое запроса и [] только когда результатов
        # действительно нет — раньше оба случая маскировались под [], и
        # вызывающий код показывал "у тебя пока пусто" даже при временном
        # сбое сети/сервера, хотя история на самом деле могла быть непустой
        # (см. get_notifications — тот же исправленный паттерн).
        try:
            response = requests.get(f"{self.base_url}/results/?{self._id_field()}={vk_id}", headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"API Error getting user results: {response.status_code}")
        except Exception as e:
            logger.error(f"Get user results error: {e}")
        return None

    def update_streak(self, user_vk_id):
        try:
            response = requests.post(
                f"{self.base_url}/users/update_streak/",
                json={self._id_field(): str(user_vk_id)},
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"API Error updating streak: {response.status_code}")
        except Exception as e:
            logger.error(f"Streak update error: {e}")
        return None

    def save_progress(self, user_vk_id, exercise_type, data):
        try:
            response = requests.post(
                f"{self.base_url}/progress/save/",
                json={
                    self._id_field(): str(user_vk_id),
                    "exercise_type": exercise_type,
                    "data": data
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"API Error saving progress: {response.status_code}")
        except Exception as e:
            logger.error(f"Progress save error: {e}")
        return None

    def get_progress(self, user_vk_id, exercise_type):
        try:
            response = requests.get(
                f"{self.base_url}/progress/get/?{self._id_field()}={user_vk_id}&exercise_type={exercise_type}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Progress get error: {e}")
        return None

    def delete_progress(self, user_vk_id, exercise_type):
        try:
            response = requests.delete(
                f"{self.base_url}/progress/delete/",
                json={
                    self._id_field(): str(user_vk_id),
                    "exercise_type": exercise_type
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return True
        except Exception as e:
            logger.error(f"Progress delete error: {e}")
        return False

    def send_for_review(self, user_vk_id, exercise_type, data):
        try:
            response = requests.post(
                f"{self.base_url}/admin/review/",
                json={
                    self._id_field(): str(user_vk_id),
                    "exercise_type": exercise_type,
                    "data": data
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code in [200, 201]:
                return response.json()
        except Exception as e:
            logger.error(f"Send review error: {e}")
        return None

    def add_comment(self, review_id, comment, is_admin=False):
        try:
            response = requests.post(
                f"{self.base_url}/admin/review/{review_id}/comment/",
                json={
                    "comment": comment,
                    "is_admin": is_admin
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Add comment error: {e}")
        return None

    def create_notification(self, user_vk_id, exercise_type, schedule_type, schedule_data):
        try:
            response = requests.post(
                f"{self.base_url}/notifications/",
                json={
                    self._id_field(): str(user_vk_id),
                    "exercise_type": exercise_type,
                    "schedule_type": schedule_type,
                    "schedule_data": schedule_data
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 201:
                return response.json()
        except Exception as e:
            logger.error(f"Create notification error: {e}")
        return None

    def get_notifications(self, user_vk_id):
        # Возвращает None при сбое запроса и [] только когда напоминаний
        # действительно нет — раньше оба случая маскировались под [], и
        # вызывающий код (handlers.py, "Отключить напоминания") не мог
        # отличить "нечего отключать" от "не смогли узнать".
        try:
            response = requests.get(
                f"{self.base_url}/notifications/?{self._id_field()}={user_vk_id}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"API Error getting notifications: {response.status_code}")
        except Exception as e:
            logger.error(f"Get notifications error: {e}")
        return None

    def delete_notification(self, notification_id):
        try:
            response = requests.delete(
                f"{self.base_url}/notifications/{notification_id}/",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 204:
                return True
        except Exception as e:
            logger.error(f"Delete notification error: {e}")
        return False

    def get_due_notifications(self):
        try:
            response = requests.get(
                f"{self.base_url}/notifications/due/",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Get due notifications error: {e}")
        return []

    def mark_notification_sent(self, notification_id):
        try:
            response = requests.post(
                f"{self.base_url}/notifications/{notification_id}/mark_sent/",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return True
        except Exception as e:
            logger.error(f"Mark notification sent error: {e}")
        return False

    def get_pending_admin_comments(self):
        try:
            response = requests.get(f"{self.base_url}/admin/review/pending_admin_comments/", headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Get pending comments error: {e}")
        return []

    def mark_comment_sent(self, review_id, comment_index):
        try:
            response = requests.post(
                f"{self.base_url}/admin/review/{review_id}/mark_comment_sent/",
                json={"comment_index": comment_index},
                headers=self.headers, timeout=5
            )
            if response.status_code == 200:
                return True
            logger.warning(f"API Error marking comment sent: {response.status_code}")
        except Exception as e:
            logger.error(f"Mark comment sent error: {e}")
        return False

    def get_active_review(self, vk_id):
        try:
            response = requests.get(f"{self.base_url}/admin/review/active_for_user/?{self._id_field()}={vk_id}", headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('exists') is False:
                    return None
                return data
        except Exception as e:
            logger.error(f"Get active review error: {e}")
        return None

    # -- Привязка одного человека к нескольким платформам (шаг из
    # platform_bots/README.md, «Модель пользователя») — оба метода всегда
    # возвращают dict с ключом "ok" (никогда None), чтобы handlers.py мог
    # различить конкретную причину сбоя (например 'already_linked' от
    # обычного сетевого сбоя) — см. bot_api/views.py::AccountLinkViewSet.

    def generate_link_code(self, user_id):
        try:
            response = requests.post(
                f"{self.base_url}/link/generate/",
                json={self._id_field(): str(user_id)},
                headers=self.headers, timeout=5
            )
            return {"ok": response.status_code == 200, **(response.json() or {})}
        except Exception as e:
            logger.error(f"Generate link code error: {e}")
            return {"ok": False, "error": "network"}

    def confirm_link_code(self, user_id, code):
        try:
            response = requests.post(
                f"{self.base_url}/link/confirm/",
                json={self._id_field(): str(user_id), "code": code},
                headers=self.headers, timeout=5
            )
            return {"ok": response.status_code == 200, **(response.json() or {})}
        except Exception as e:
            logger.error(f"Confirm link code error: {e}")
            return {"ok": False, "error": "network"}
    