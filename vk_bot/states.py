# states.py
from enum import Enum

class UserState(Enum):
    MAIN = "main"
    SELECTING_EXERCISE = "selecting_exercise"
    VIEWING_EXERCISE = "viewing_exercise"
    WAITING_RESULT = "waiting_result"  # ждём ответ от пользователя
    VIEWING_RESULTS = "viewing_results"