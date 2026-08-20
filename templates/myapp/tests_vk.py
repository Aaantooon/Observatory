from unittest.mock import patch, Mock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class VKCallbackTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('myapp:vk_callback')

    @patch('myapp.views.requests.get')
    def test_creates_new_user_and_logs_in(self, mock_get):
        # Имитируем ответ VK API users.get
        mock_response = Mock()
        mock_response.json.return_value = {
            'response': [{
                'id': 123456789,
                'first_name': 'Иван',
                'last_name': 'Тестов',
            }]
        }
        mock_get.return_value = mock_response

        response = self.client.post(self.url, {'access_token': 'fake_token_123'})

        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['redirect'], '/')

        # Проверяем, что пользователь создан
        user = User.objects.get(username='vk_123456789')
        self.assertEqual(user.first_name, 'Иван')
        self.assertEqual(user.last_name, 'Тестов')

        # Проверяем, что пользователь залогинен в сессии
        session = self.client.session
        self.assertIn('_auth_user_id', session)
        self.assertEqual(int(session['_auth_user_id']), user.id)

    @patch('myapp.views.requests.get')
    def test_existing_user_reused(self, mock_get):
        # Создаём пользователя заранее — он не должен дублироваться
        existing = User.objects.create(username='vk_555', first_name='Старое')

        mock_response = Mock()
        mock_response.json.return_value = {
            'response': [{
                'id': 555,
                'first_name': 'Новое',
                'last_name': 'Имя',
            }]
        }
        mock_get.return_value = mock_response

        self.client.post(self.url, {'access_token': 'fake_token'})

        self.assertEqual(User.objects.filter(username='vk_555').count(), 1)
        existing.refresh_from_db()
        # get_or_create не обновляет существующего — имя останется старым
        self.assertEqual(existing.first_name, 'Старое')

    def test_missing_token_returns_400(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)

    @patch('myapp.views.requests.get')
    def test_vk_error_returns_400(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {'error': {'error_msg': 'Invalid token'}}
        mock_get.return_value = mock_response

        response = self.client.post(self.url, {'access_token': 'bad_token'})
        self.assertEqual(response.status_code, 400)

    def test_get_request_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)