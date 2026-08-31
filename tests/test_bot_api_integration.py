"""
Интеграционные тесты РЕАЛЬНОГО Django-сервера (bot_api) — в отличие от
test_exercises.py/test_handlers.py, здесь ничего не подменяется: настоящие
Django-модели, настоящая база (SQLite в памяти вместо боевого PostgreSQL,
но те же миграции), настоящие DRF-вьюсеты, запросы идут через реальный
HTTP-слой DRF (APIClient). Это то, что test_exercises.py принципиально не
может поймать — баги на стороне сервера (bot_api/views.py, serializers.py,
миграции).

Настройки Django собираются здесь же через settings.configure() — отдельный
файл настроек не нужен, поэтому конфликтов с vk_bot/config.py (одноимённый
модуль в тестах бота) не возникает. Требует Django + djangorestframework —
они уже есть в requirements.txt проекта.

Запуск: python -m pytest tests/test_bot_api_integration.py -v
(входит и в общий прогон `python -m pytest tests/ -v`)
"""
import sys
from pathlib import Path

import django
from django.conf import settings

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret-key-not-for-production",
        DEBUG=True,
        ALLOWED_HOSTS=["testserver", "localhost"],
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "rest_framework",
            "rest_framework.authtoken",
            "bot_api",
        ],
        MIDDLEWARE=[],
        ROOT_URLCONF=__name__,  # urlpatterns определены ниже, в этом же файле
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        USE_TZ=True,
        TIME_ZONE="Europe/Moscow",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication"],
            # Совпадает с боевыми настройками (config/settings.py) — чтение тоже
            # требует токен, иначе тесты не поймают регрессию открытого API.
            "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        },
    )
    django.setup()

from django.urls import path, include  # noqa: E402

urlpatterns = [path("api/", include("bot_api.urls"))]

import pytest  # noqa: E402
from django.test.utils import setup_test_environment, teardown_test_environment  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402
from django.contrib.auth.models import User as AuthUser  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402
from rest_framework import status  # noqa: E402

from bot_api.models import User, Exercise, Notification  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def django_test_db():
    """Поднимает настоящую (in-memory SQLite) тестовую БД на всю сессию
    прогона этого файла — применяет ВСЕ реальные миграции bot_api."""
    setup_test_environment()
    runner = DiscoverRunner()
    old_config = runner.setup_databases()
    yield
    runner.teardown_databases(old_config)
    teardown_test_environment()


@pytest.fixture
def api():
    """Авторизованный DRF-клиент — как ходит настоящий api_client.py бота."""
    from django.test import TestCase
    tc = TestCase()
    tc._pre_setup()
    auth_user = AuthUser.objects.create_user(username="bot", password="x")
    token = Token.objects.create(user=auth_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    yield client
    tc._post_teardown()


# ---------------------------------------------------------------------------
# Безопасность — регрессия на закрытую 30.08.2026 публичную утечку
# (см. СВОДКА_ПРОЕКТА.md: DEFAULT_PERMISSION_CLASSES -> IsAuthenticated)
# ---------------------------------------------------------------------------

def test_results_endpoint_requires_token(django_test_db):
    client = APIClient()  # без токена
    resp = client.get("/api/results/")
    assert resp.status_code in (401, 403), (
        f"/api/results/ должен требовать авторизацию, получено {resp.status_code} — "
        f"регрессия публичной утечки данных, закрытой 30.08.2026"
    )


def test_review_endpoint_requires_token(django_test_db):
    client = APIClient()
    resp = client.get("/api/admin/review/active_for_user/?vk_id=1")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Пользователь — создание/поиск по vk_id (api_client.get_or_create_user)
# ---------------------------------------------------------------------------

def test_create_then_find_user_by_vk_id(api):
    resp = api.post("/api/users/", {
        "vk_id": "12345", "first_name": "Аня", "last_name": "Иванова",
    }, format="json")
    assert resp.status_code == status.HTTP_201_CREATED, resp.data

    # POST повторно с тем же vk_id должен вернуть существующего, не создать дубль
    resp2 = api.post("/api/users/", {
        "vk_id": "12345", "first_name": "Аня", "last_name": "Иванова",
    }, format="json")
    assert resp2.status_code == 200
    assert User.objects.filter(vk_id="12345").count() == 1


# ---------------------------------------------------------------------------
# Прогресс упражнения — полный цикл save/get/delete
# (эмулирует ровно то, что делает vk_bot/exercises/base.py)
# ---------------------------------------------------------------------------

def test_save_get_delete_progress_roundtrip(api):
    User.objects.create(vk_id="777", first_name="Т", last_name="Т")

    resp = api.post("/api/progress/save/", {
        "vk_id": "777", "exercise_type": "my_roles",
        "data": {"phase": "social", "social_roles": ["Продавец"]},
    }, format="json")
    assert resp.status_code == 200, resp.data

    resp = api.get("/api/progress/get/?vk_id=777&exercise_type=my_roles")
    assert resp.status_code == 200
    assert resp.data["exists"] is True
    assert resp.data["data"]["social_roles"] == ["Продавец"]

    # для другого exercise_type прогресса быть не должно
    resp = api.get("/api/progress/get/?vk_id=777&exercise_type=diary")
    assert resp.data["exists"] is False

    resp = api.delete("/api/progress/delete/", {
        "vk_id": "777", "exercise_type": "my_roles",
    }, format="json")
    assert resp.status_code == 200

    resp = api.get("/api/progress/get/?vk_id=777&exercise_type=my_roles")
    assert resp.data["exists"] is False


# ---------------------------------------------------------------------------
# Результат — именно тот баг, что нашли автотесты 31.08.2026 (exercise_type),
# но теперь проверенный через настоящий сервер, а не заглушку
# ---------------------------------------------------------------------------

def test_save_result_creates_exercise_by_type_string(api):
    User.objects.create(vk_id="888", first_name="Т", last_name="Т")

    resp = api.post("/api/results/", {
        "user_vk_id": "888",
        "exercise_type": "stress_search",
        "result_data": {"items": [{"text": "Работа", "rate": 8}]},
    }, format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["exercise_type"] == "stress_search"
    assert Exercise.objects.filter(type="stress_search").count() == 1

    # второй результат для того же типа не должен плодить дубль Exercise
    api.post("/api/results/", {
        "user_vk_id": "888", "exercise_type": "stress_search", "result_data": {},
    }, format="json")
    assert Exercise.objects.filter(type="stress_search").count() == 1


def test_save_result_with_numeric_exercise_type_is_a_client_bug_not_server_bug(api):
    """Регрессия для найденного 31.08.2026 бага в stress_search.py: если
    клиент (по ошибке) передаёт число вместо строки exercise_type, сервер
    его молча примет и создаст Exercise(type='1') — сервер НЕ защищает от
    этой ошибки, ответственность на клиенте (всегда передавать
    get_exercise_type(), не число — см. «Известные грабли» №29)."""
    User.objects.create(vk_id="888", first_name="Т", last_name="Т")

    resp = api.post("/api/results/", {
        "user_vk_id": "888", "exercise_type": 1, "result_data": {},
    }, format="json")
    assert resp.status_code == 201
    assert str(resp.data["exercise_type"]) == "1", (
        "Подтверждает: сервер создаёт левый Exercise(type='1') без единой "
        "ошибки — именно поэтому баг в клиенте был незаметен без тестов"
    )
    assert Exercise.objects.filter(type="1").exists()


def test_results_filtered_by_vk_id(api):
    user = User.objects.create(vk_id="888", first_name="Т", last_name="Т")
    User.objects.create(vk_id="999", first_name="Д", last_name="Д")

    api.post("/api/results/", {
        "user_vk_id": "888", "exercise_type": "diary", "result_data": {},
    }, format="json")
    api.post("/api/results/", {
        "user_vk_id": "999", "exercise_type": "diary", "result_data": {},
    }, format="json")

    resp = api.get("/api/results/?vk_id=888")
    assert len(resp.data) == 1
    assert resp.data[0]["user"] == user.id


# ---------------------------------------------------------------------------
# Review (система проверки психологом) — полный цикл
# ---------------------------------------------------------------------------

def test_full_review_lifecycle(api):
    User.objects.create(vk_id="555", first_name="Т", last_name="Т")

    # 1. Клиент отправляет упражнение на проверку
    resp = api.post("/api/admin/review/", {
        "vk_id": "555", "exercise_type": "my_roles", "data": {"social_roles": ["Продавец"]},
    }, format="json")
    assert resp.status_code == 201, resp.data
    review_id = resp.data["id"]
    assert resp.data["status"] == "pending"

    # 2. У пользователя появляется активная проверка
    resp = api.get("/api/admin/review/active_for_user/?vk_id=555")
    assert resp.data["id"] == review_id
    assert resp.data["status"] == "pending"

    # 3. Психолог комментирует (is_admin=True) -> статус меняется на in_review
    resp = api.post(f"/api/admin/review/{review_id}/comment/", {
        "comment": "Хорошая работа, добавь ещё пару ролей", "is_admin": True,
    }, format="json")
    assert resp.status_code == 200
    assert resp.data["status"] == "in_review"

    # 4. Комментарий психолога виден в очереди на отправку боту
    resp = api.get("/api/admin/review/pending_admin_comments/")
    assert len(resp.data) == 1
    assert resp.data[0]["user_vk_id"] == "555"
    assert resp.data[0]["text"] == "Хорошая работа, добавь ещё пару ролей"

    # 5. Бот подтверждает отправку комментария пользователю
    resp = api.post(f"/api/admin/review/{review_id}/mark_comment_sent/", {
        "comment_index": 0,
    }, format="json")
    assert resp.status_code == 200

    resp = api.get("/api/admin/review/pending_admin_comments/")
    assert len(resp.data) == 0, "После mark_comment_sent комментарий не должен снова попадать в очередь"

    # 6. Клиент отвечает (is_admin=False) — статус остаётся in_review
    resp = api.post(f"/api/admin/review/{review_id}/comment/", {
        "comment": "Хорошо, добавлю", "is_admin": False,
    }, format="json")
    assert resp.data["status"] == "in_review"

    # 7. Психолог завершает проверку
    resp = api.post(f"/api/admin/review/{review_id}/complete/", {
        "approved": True,
    }, format="json")
    assert resp.data["status"] == "closed"

    # 8. После закрытия — активной проверки у пользователя больше нет
    resp = api.get("/api/admin/review/active_for_user/?vk_id=555")
    assert resp.data.get("exists") is False


# ---------------------------------------------------------------------------
# Уведомления — логика "пора ли слать" (due)
# ---------------------------------------------------------------------------

def test_once_notification_not_due_before_delay(api):
    User.objects.create(vk_id="333", first_name="Т", last_name="Т")

    resp = api.post("/api/notifications/", {
        "vk_id": "333", "exercise_type": "general",
        "schedule_type": "once", "schedule_data": {"delay_hours": 3},
    }, format="json")
    assert resp.status_code == 201

    resp = api.get("/api/notifications/due/")
    assert resp.data == [], "Уведомление с задержкой 3 часа не должно быть 'due' сразу после создания"


def test_once_notification_due_after_delay_elapsed(api):
    from django.utils import timezone
    from datetime import timedelta

    user = User.objects.create(vk_id="333", first_name="Т", last_name="Т")
    notif = Notification.objects.create(
        user=user, exercise_type="general",
        schedule_type="once", schedule_data={"delay_hours": 1},
    )
    # искусственно "состариваем" уведомление на 2 часа назад
    Notification.objects.filter(id=notif.id).update(
        created_at=timezone.now() - timedelta(hours=2)
    )

    resp = api.get("/api/notifications/due/")
    assert len(resp.data) == 1
    assert resp.data[0]["id"] == notif.id

    # отмечаем отправленным -> для 'once' должно деактивироваться и больше не попадать в due
    resp = api.post(f"/api/notifications/{notif.id}/mark_sent/")
    assert resp.status_code == 200

    resp = api.get("/api/notifications/due/")
    assert resp.data == [], "'once'-уведомление после отправки не должно снова попадать в due"

    notif.refresh_from_db()
    assert notif.is_active is False
