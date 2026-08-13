# api_client.py
import requests
from config import API_BASE_URL, API_TOKEN
from models import User, Exercise, Result

class APIClient:
    def __init__(self):
        self.base_url = API_BASE_URL
        self.headers = {
            "Authorization": f"Token {API_TOKEN}",
            "Content-Type": "application/json"
        }

    def get_or_create_user(self, vk_id, first_name, last_name):
        response = requests.post(
            f"{self.base_url}/users/",
            json={
                "vk_id": vk_id,
                "first_name": first_name,
                "last_name": last_name
            },
            headers=self.headers
        )
        return response.json()

    def get_exercises(self):
        response = requests.get(
            f"{self.base_url}/exercises/",
            headers=self.headers
        )
        return response.json()

    def save_result(self, user_vk_id, exercise_id, result_data):
        response = requests.post(
            f"{self.base_url}/results/",
            json={
                "user_vk_id": user_vk_id,
                "exercise_id": exercise_id,
                "result_data": result_data
            },
            headers=self.headers
        )
        return response.json()

    def get_user_results(self, vk_id):
        response = requests.get(
            f"{self.base_url}/results/?vk_id={vk_id}",
            headers=self.headers
        )
        return response.json()