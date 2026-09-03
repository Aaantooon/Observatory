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

from bot_api.models import User, Exercise, Notification, Result, Review, ExerciseProgress, AccountLinkCode  # noqa: E402


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


# ---------------------------------------------------------------------------
# Telegram — шаг 4 плана platform_bots/README.md: User.telegram_id рядом с
# vk_id, эндпоинты принимают ЛЮБОЙ из двух id пользователя.
# ---------------------------------------------------------------------------

def test_create_then_find_user_by_telegram_id(api):
    """Тот же сценарий, что test_create_then_find_user_by_vk_id, но по
    telegram_id — regular vk_id-запросы (тест выше) не должны сломаться от
    появления этого поля, а telegram_id-запросы должны работать так же."""
    resp = api.post("/api/users/", {
        "telegram_id": "555000111", "first_name": "Игорь", "last_name": "П",
    }, format="json")
    assert resp.status_code == status.HTTP_201_CREATED, resp.data
    assert resp.data["vk_id"] is None

    resp2 = api.post("/api/users/", {
        "telegram_id": "555000111", "first_name": "Игорь", "last_name": "П",
    }, format="json")
    assert resp2.status_code == 200
    assert User.objects.filter(telegram_id="555000111").count() == 1


def test_vk_and_telegram_users_with_overlapping_numeric_ids_do_not_collide(api):
    """Критично: VK user_id и Telegram chat_id — независимые пространства
    чисел (см. platform_bots/README.md, «Модель пользователя»). Один и тот
    же числовой ID у VK-пользователя (vk_id) и Telegram-пользователя
    (telegram_id) должен адресовать ДВЕ РАЗНЫЕ записи, не одну."""
    User.objects.create(vk_id="42", first_name="ВК", last_name="Юзер")
    User.objects.create(telegram_id="42", first_name="ТГ", last_name="Юзер")

    resp_vk = api.get("/api/users/?vk_id=42")
    resp_tg = api.get("/api/users/?telegram_id=42")
    assert len(resp_vk.data) == 1 and resp_vk.data[0]["first_name"] == "ВК"
    assert len(resp_tg.data) == 1 and resp_tg.data[0]["first_name"] == "ТГ"


def test_save_get_delete_progress_roundtrip_by_telegram_id(api):
    """Тот же сценарий, что test_save_get_delete_progress_roundtrip (vk_id),
    но для Telegram-пользователя — эмулирует то, что будет делать
    main_telegram.py через те же exercises/base.py::save_progress и т.д."""
    User.objects.create(telegram_id="909", first_name="Т", last_name="Т")

    resp = api.post("/api/progress/save/", {
        "telegram_id": "909", "exercise_type": "my_roles",
        "data": {"phase": "social", "social_roles": ["Продавец"]},
    }, format="json")
    assert resp.status_code == 200, resp.data

    resp = api.get("/api/progress/get/?telegram_id=909&exercise_type=my_roles")
    assert resp.status_code == 200
    assert resp.data["exists"] is True
    assert resp.data["data"]["social_roles"] == ["Продавец"]

    resp = api.delete("/api/progress/delete/", {
        "telegram_id": "909", "exercise_type": "my_roles",
    }, format="json")
    assert resp.status_code == 200

    resp = api.get("/api/progress/get/?telegram_id=909&exercise_type=my_roles")
    assert resp.data["exists"] is False


def test_save_result_and_full_review_lifecycle_by_telegram_id(api):
    """Результат + полный цикл проверки психологом (аналог
    test_save_result_creates_exercise_by_type_string и
    test_full_review_lifecycle), но для Telegram-пользователя — покрывает
    именно то, что нужно шагу «упражнения + проверка» для Telegram."""
    User.objects.create(telegram_id="303", first_name="Т", last_name="Т")

    resp = api.post("/api/results/", {
        "user_telegram_id": "303",
        "exercise_type": "stress_search",
        "result_data": {"items": [{"text": "Работа", "rate": 8}]},
    }, format="json")
    assert resp.status_code == 201, resp.data

    resp = api.post("/api/admin/review/", {
        "telegram_id": "303", "exercise_type": "stress_search", "data": {},
    }, format="json")
    assert resp.status_code == 201, resp.data
    review_id = resp.data["id"]

    resp = api.get("/api/admin/review/active_for_user/?telegram_id=303")
    assert resp.data["id"] == review_id

    resp = api.post(f"/api/admin/review/{review_id}/comment/", {
        "comment": "Хорошо", "is_admin": False,
    }, format="json")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Привязка одного человека к нескольким платформам (шаг из
# platform_bots/README.md, «Модель пользователя») — /api/link/generate/ и
# /api/link/confirm/, bot_api/views.py::AccountLinkViewSet, _merge_users.
# ---------------------------------------------------------------------------

def test_generate_link_code_returns_code_and_expiry(api):
    User.objects.create(vk_id="100", first_name="А", last_name="А")

    resp = api.post("/api/link/generate/", {"vk_id": "100"}, format="json")
    assert resp.status_code == 200, resp.data
    assert len(resp.data["code"]) == 6 and resp.data["code"].isdigit()
    assert resp.data["expires_in_minutes"] == 10


def test_generate_link_code_for_already_linked_user_fails():
    from django.test import TestCase
    from django.contrib.auth.models import User as AuthUser
    from rest_framework.test import APIClient as DRFClient
    from rest_framework.authtoken.models import Token

    tc = TestCase()
    tc._pre_setup()
    try:
        auth_user = AuthUser.objects.create_user(username="bot2", password="x")
        token = Token.objects.create(user=auth_user)
        client = DRFClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        User.objects.create(vk_id="101", telegram_id="201", first_name="А", last_name="А")
        resp = client.post("/api/link/generate/", {"vk_id": "101"}, format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "already_linked"
    finally:
        tc._post_teardown()


def test_generate_link_code_user_not_found(api):
    resp = api.post("/api/link/generate/", {"vk_id": "no-such-user"}, format="json")
    assert resp.status_code == 404
    assert resp.data["error"] == "user_not_found"


def test_confirm_link_code_merges_users_and_moves_data(api):
    source = User.objects.create(vk_id="100", first_name="А", last_name="А", streak=2)
    from datetime import date
    User.objects.filter(pk=source.pk).update(last_activity_date=date(2026, 9, 1))
    target = User.objects.create(telegram_id="200", first_name="А", last_name="А", streak=5)
    User.objects.filter(pk=target.pk).update(last_activity_date=date(2026, 9, 3))
    source.refresh_from_db()
    target.refresh_from_db()

    exercise = Exercise.objects.create(title="Дневник", type="diary")
    Result.objects.create(user=target, exercise=exercise, result_data={"mood": "ok"})
    Review.objects.create(user=target, exercise_type="diary", data={})
    ExerciseProgress.objects.create(user=target, exercise_type="diary", data={"mood": "ok"})
    ExerciseProgress.objects.create(user=source, exercise_type="stress_search", data={"items": []})
    Notification.objects.create(
        user=target, exercise_type="diary", schedule_type="daily",
        schedule_data={"time": "08:00", "type": "morning"},
    )
    Notification.objects.create(
        user=source, exercise_type="stop_technique", schedule_type="daily",
        schedule_data={"time": "12:00", "type": "stop_technique"},
    )

    gen = api.post("/api/link/generate/", {"vk_id": "100"}, format="json")
    code = gen.data["code"]

    resp = api.post("/api/link/confirm/", {"telegram_id": "200", "code": code}, format="json")
    assert resp.status_code == 200, resp.data
    assert resp.data == {"status": "ok"}

    assert not User.objects.filter(pk=target.pk).exists(), "target_user должен быть удалён после слияния"

    source.refresh_from_db()
    assert source.vk_id == "100" and source.telegram_id == "200"
    assert source.streak == 5, "стрик должен взять максимум из двух"
    assert source.last_activity_date == date(2026, 9, 3), "дата активности — более поздняя из двух"

    assert Result.objects.filter(user=source).count() == 1
    assert Review.objects.filter(user=source).count() == 1
    assert ExerciseProgress.objects.filter(user=source).count() == 2, (
        "оба непересекающихся прогресса (diary с target, stress_search с source) должны сохраниться"
    )
    assert Notification.objects.filter(user=source).count() == 2, (
        "оба непересекающихся напоминания должны сохраниться"
    )


def test_confirm_link_code_keeps_more_recent_progress_on_conflict(api):
    source = User.objects.create(vk_id="110", first_name="А", last_name="А")
    target = User.objects.create(telegram_id="210", first_name="А", last_name="А")

    old_progress = ExerciseProgress.objects.create(user=source, exercise_type="diary", data={"mood": "old"})
    new_progress = ExerciseProgress.objects.create(user=target, exercise_type="diary", data={"mood": "new"})
    from django.utils import timezone
    from datetime import timedelta
    ExerciseProgress.objects.filter(pk=old_progress.pk).update(updated_at=timezone.now() - timedelta(days=1))

    gen = api.post("/api/link/generate/", {"vk_id": "110"}, format="json")
    code = gen.data["code"]
    resp = api.post("/api/link/confirm/", {"telegram_id": "210", "code": code}, format="json")
    assert resp.status_code == 200, resp.data

    remaining = ExerciseProgress.objects.filter(user_id=source.pk, exercise_type="diary")
    assert remaining.count() == 1, "при конфликте должна остаться ровно одна запись прогресса"
    assert remaining.first().data == {"mood": "new"}, "должна победить более свежая (по updated_at) версия"


def test_confirm_link_code_deduplicates_identical_notifications(api):
    source = User.objects.create(vk_id="120", first_name="А", last_name="А")
    target = User.objects.create(telegram_id="220", first_name="А", last_name="А")

    schedule = {"time": "08:00", "type": "morning"}
    Notification.objects.create(user=source, exercise_type="diary", schedule_type="daily", schedule_data=schedule)
    Notification.objects.create(user=target, exercise_type="diary", schedule_type="daily", schedule_data=schedule)

    gen = api.post("/api/link/generate/", {"vk_id": "120"}, format="json")
    code = gen.data["code"]
    resp = api.post("/api/link/confirm/", {"telegram_id": "220", "code": code}, format="json")
    assert resp.status_code == 200, resp.data

    assert Notification.objects.filter(user_id=source.pk).count() == 1, (
        "одинаковое напоминание с обеих платформ не должно задваиваться после слияния"
    )


def test_confirm_link_code_invalid_code_fails(api):
    User.objects.create(telegram_id="230", first_name="А", last_name="А")
    resp = api.post("/api/link/confirm/", {"telegram_id": "230", "code": "000000"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"] == "invalid_or_expired"


def test_confirm_link_code_expired_code_fails(api):
    from django.utils import timezone
    from datetime import timedelta

    source = User.objects.create(vk_id="130", first_name="А", last_name="А")
    target = User.objects.create(telegram_id="240", first_name="А", last_name="А")
    link = AccountLinkCode.objects.create(code="555555", source_user=source)
    AccountLinkCode.objects.filter(pk=link.pk).update(
        created_at=timezone.now() - timedelta(minutes=AccountLinkCode.LIFETIME_MINUTES + 1)
    )

    resp = api.post("/api/link/confirm/", {"telegram_id": "240", "code": "555555"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"] == "invalid_or_expired"
    assert User.objects.filter(pk=target.pk).exists(), "истёкший код не должен ничего сливать"


def test_confirm_link_code_same_account_fails(api):
    User.objects.create(vk_id="140", first_name="А", last_name="А")

    gen = api.post("/api/link/generate/", {"vk_id": "140"}, format="json")
    code = gen.data["code"]

    resp = api.post("/api/link/confirm/", {"vk_id": "140", "code": code}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"] == "same_account"


def test_confirm_link_code_conflicting_platform_ids_fails(api):
    source = User.objects.create(vk_id="V1", first_name="А", last_name="А")
    target = User.objects.create(vk_id="V9", telegram_id="T1", first_name="Б", last_name="Б")

    gen = api.post("/api/link/generate/", {"vk_id": "V1"}, format="json")
    code = gen.data["code"]

    resp = api.post("/api/link/confirm/", {"telegram_id": "T1", "code": code}, format="json")
    assert resp.status_code == 409
    assert resp.data["error"] == "conflict"

    source.refresh_from_db()
    assert source.telegram_id is None, "при конфликте ничего не должно измениться"
    assert User.objects.filter(pk=target.pk).exists(), "при конфликте target не должен удаляться"


def test_confirm_link_code_cannot_be_reused(api):
    source = User.objects.create(vk_id="150", first_name="А", last_name="А")
    target1 = User.objects.create(telegram_id="250", first_name="А", last_name="А")
    User.objects.create(telegram_id="251", first_name="В", last_name="В")

    gen = api.post("/api/link/generate/", {"vk_id": "150"}, format="json")
    code = gen.data["code"]

    resp1 = api.post("/api/link/confirm/", {"telegram_id": "250", "code": code}, format="json")
    assert resp1.status_code == 200, resp1.data
    assert not User.objects.filter(pk=target1.pk).exists()

    resp2 = api.post("/api/link/confirm/", {"telegram_id": "251", "code": code}, format="json")
    assert resp2.status_code == 400
    assert resp2.data["error"] == "invalid_or_expired", "уже использованный код нельзя применить повторно"
