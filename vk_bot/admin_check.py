from vk_api.utils import get_random_id
from config import ADMIN_IDS

class AdminCheck:
    def __init__(self, vk_session, api_client):
        self.vk = vk_session
        self.api = api_client
        self.admin_ids = ADMIN_IDS

    def send_message(self, user_id, message, keyboard=None):
        self.vk.method('messages.send', {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
            'keyboard': keyboard
        })

    def submit_for_review(self, user_id, exercise_type, data):
        result = self.api.send_for_review(user_id, exercise_type, data)
        
        if result and result.get('review_id'):
            review_id = result['review_id']
            self.user_sessions[user_id] = {
                'review_id': review_id,
                'phase': 'waiting',
                'exercise_type': exercise_type
            }
            
            for admin_id in self.admin_ids:
                self.send_message(
                    admin_id,
                    f"🔔 **Новая проверка!**\n\n"
                    f"👤 Пользователь: {user_id}\n"
                    f"📋 Упражнение: {exercise_type}\n"
                    f"🆔 ID: {review_id}"
                )
            
            self.send_message(
                user_id,
                "✅ **Отправлено на проверку!**\n\n"
                "Администратор проверит твой путь\n"
                "Ты получишь уведомление с комментариями\n"
                "Можно продолжить диалог с админом\n\n"
                "🕯️ Ожидай..."
            )
            return True
        
        self.send_message(
            user_id,
            "❌ Не удалось отправить на проверку\n"
            "Попробуй позже"
        )
        return False

    def handle_admin_reply(self, admin_id, text):
        # Найти проверку, которую обрабатывает админ
        active_review = None
        review_user_id = None
        
        for user_id, session in self.user_sessions.items():
            if session.get('admin_id') == admin_id and session.get('phase') in ['reviewing', 'commenting']:
                active_review = session
                review_user_id = user_id
                break
        
        if not active_review:
            self.send_message(
                admin_id,
                "❌ Нет активной проверки\n"
                "Используй админ-панель на сайте"
            )
            return
        
        review_id = active_review['review_id']
        
        self.api.add_comment(review_id, text, is_admin=True)
        
        self.user_sessions[review_user_id]['phase'] = 'commenting'
        
        self.send_message(
            review_user_id,
            f"💬 **Комментарий от администратора:**\n\n{text}\n\n"
            "✏️ Можешь ответить или нажать «Завершить проверку»",
            self._get_review_keyboard()
        )
        
        self.send_message(
            admin_id,
            f"✅ Комментарий отправлен пользователю"
        )

    def handle_user_reply(self, user_id, text):
        session = self.user_sessions.get(user_id)
        if not session or session.get('phase') != 'commenting':
            return False
        
        review_id = session['review_id']
        
        self.api.add_comment(review_id, text, is_admin=False)
        
        for admin_id in self.admin_ids:
            self.send_message(
                admin_id,
                f"💬 **Ответ от пользователя:**\n\n{text}\n\n"
                f"🆔 Проверка: {review_id}"
            )
        
        return True

    def finish_review(self, user_id):
        session = self.user_sessions.get(user_id)
        if not session:
            return False
        
        review_id = session['review_id']
        
        self.api.complete_review(review_id, True)
        
        self.send_message(
            user_id,
            "✅ **Проверка завершена!**\n\n"
            "Посмотреть результат можно на сайте\n\n"
            "🕯️ Продолжай путь!"
        )
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        return True

    def _get_review_keyboard(self):
        from keyboards import get_review_keyboard
        return get_review_keyboard()