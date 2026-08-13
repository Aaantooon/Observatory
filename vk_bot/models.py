# models.py - упрощённая версия без pydantic
# Все данные берутся из API сайта

class User:
    def __init__(self, vk_id, first_name, last_name):
        self.vk_id = vk_id
        self.first_name = first_name
        self.last_name = last_name

class Exercise:
    def __init__(self, id, title, description, type):
        self.id = id
        self.title = title
        self.description = description
        self.type = type

class Result:
    def __init__(self, user_vk_id, exercise_id, result_data,
                 completed_at=None, is_approved=False,
                 corrected_data=None, correction_comment=None):
        self.id = None
        self.user_vk_id = user_vk_id
        self.exercise_id = exercise_id
        self.result_data = result_data
        self.completed_at = completed_at
        self.is_approved = is_approved
        self.corrected_data = corrected_data
        self.correction_comment = correction_comment