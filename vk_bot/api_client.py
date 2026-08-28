import requests
import logging
from config import API_BASE_URL, API_TOKEN

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.base_url = API_BASE_URL
        self.headers = {
            "Authorization": f"Token {API_TOKEN}",
            "Content-Type": "application/json"
        }

    def get_or_create_user(self, vk_id, first_name, last_name):
        try:
            response = requests.get(
                f"{self.base_url}/users/?vk_id={vk_id}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                users = response.json()
                if users and len(users) > 0:
                    return users
            
            response = requests.post(
                f"{self.base_url}/users/",
                json={
                    "vk_id": str(vk_id),
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
                return {"id": vk_id, "vk_id": vk_id, "first_name": first_name, "last_name": last_name}
                
        except Exception as e:
            logger.error(f"Network error: {e}")
            return {"id": vk_id, "vk_id": vk_id, "first_name": first_name, "last_name": last_name}

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
                    "user_vk_id": str(user_vk_id),
                    "exercise_type": exercise_type,
                    "result_data": result_data
                },
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 201:
                return response.json()
            logger.warning(f"API Error saving result: {response.status_code}")
            return {"status": "saved_local"}
        except Exception as e:
            logger.error(f"API save error: {e}")
            return {"status": "saved_local"}

    def get_user_results(self, vk_id):
        try:
            response = requests.get(f"{self.base_url}/results/?vk_id={vk_id}", headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []

    def update_streak(self, user_vk_id):
        try:
            response = requests.post(
                f"{self.base_url}/users/update_streak/",
                json={"vk_id": str(user_vk_id)},
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
                    "vk_id": str(user_vk_id),
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
                f"{self.base_url}/progress/get/?vk_id={user_vk_id}&exercise_type={exercise_type}",
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
                    "vk_id": str(user_vk_id),
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
                    "vk_id": str(user_vk_id),
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

    def get_review_status(self, user_vk_id, exercise_type):
        try:
            response = requests.get(
                f"{self.base_url}/admin/review/status/?vk_id={user_vk_id}&exercise_type={exercise_type}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Get review status error: {e}")
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

    def complete_review(self, review_id, approved):
        try:
            response = requests.post(
                f"{self.base_url}/admin/review/{review_id}/complete/",
                json={"approved": approved},
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Complete review error: {e}")
        return None

    def create_notification(self, user_vk_id, exercise_type, schedule_type, schedule_data):
        try:
            response = requests.post(
                f"{self.base_url}/notifications/",
                json={
                    "vk_id": str(user_vk_id),
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
        try:
            response = requests.get(
                f"{self.base_url}/notifications/?vk_id={user_vk_id}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Get notifications error: {e}")
        return []

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

    def get_user_stats(self, user_vk_id):
        try:
            response = requests.get(
                f"{self.base_url}/users/stats/?vk_id={user_vk_id}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Get stats error: {e}")
        return None