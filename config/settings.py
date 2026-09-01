import os
from pathlib import Path
from dotenv import load_dotenv
from machina import MACHINA_MAIN_STATIC_DIR
from machina import MACHINA_MAIN_TEMPLATE_DIR

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY не найден в .env файле!")

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', '5.42.103.203', 'putnabludatel.ru', 'www.putnabludatel.ru']

# ===== Мониторинг ошибок (Sentry) =====
# Полностью опционально: без SENTRY_DSN в .env — просто ничего не делает.
# Чтобы включить: добавить SENTRY_DSN=<адрес из sentry.io> в .env и
# установить пакет sentry-sdk (pip install sentry-sdk).
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
    except ImportError:
        pass  # sentry-sdk не установлен — просто работаем без мониторинга

# ===== Логирование =====
# Без этого блока Django всё равно выводит logger.exception(...) в stderr
# (который systemd/journalctl перехватывает), но с явным форматом и
# уровнями — понятнее искать проблему в логах.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'myapp': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'crm': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ===== INSTALLED_APPS =====
INSTALLED_APPS = [
    # Стандартные приложения Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'jazzmin',
    
    # Зависимости Machina
    'mptt',
    'haystack',
    'widget_tweaks',
    
    # Machina
    'machina',
    'machina.apps.forum',
    'machina.apps.forum_conversation',
    'machina.apps.forum_conversation.forum_attachments',
    'machina.apps.forum_conversation.forum_polls',
    'machina.apps.forum_feeds',
    'machina.apps.forum_moderation',
    'machina.apps.forum_search',
    'machina.apps.forum_tracking',
    'machina.apps.forum_member',
    'machina.apps.forum_permission',
    
    # Сторонние приложения
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'social_django',  # Вход через VK
    'django_otp',                       # 2FA для /admin/ и /crm/ (01.09.2026)
    'django_otp.plugins.otp_totp',       # TOTP-устройства (Google Authenticator и т.п.)

    # Ваши приложения
    'myapp',
    'bot_api',
    'crm',
    'observer3d',

    # sitemap.xml (фреймворк, без своих моделей — миграция не нужна)
    'django.contrib.sitemaps',
]

# =======================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',  # 2FA — сразу после AuthenticationMiddleware (01.09.2026)
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'machina.apps.forum_permission.middleware.ForumPermissionMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',  # Вход через VK
    'config.twofa_middleware.TwoFactorGateMiddleware',  # Гейт на /admin/ и /crm/ — включается REQUIRE_2FA (01.09.2026)
]

# 2FA для /admin/ и /crm/. По умолчанию ВЫКЛЮЧЕНО (False), чтобы не заблокировать
# самого себя раньше, чем устройство реально настроено и проверено. Порядок:
# 1) задеплоить этот код с REQUIRE_2FA не заданным (или =False) в .env,
# 2) зайти в /admin/ как обычно (логин/пароль), открыть /2fa/setup/, привязать
#    приложение-аутентификатор по QR, ввести код для подтверждения,
# 3) убедиться, что устройство подтверждено,
# 4) только после этого поставить REQUIRE_2FA=True в .env на сервере и
#    перезапустить observatory — вот теперь /admin/ и /crm/ требуют код.
# Если что-то пошло не так и доступ пропал — вернуть REQUIRE_2FA=False в .env
# и перезапустить сервис, без обращения к базе данных.
REQUIRE_2FA = os.getenv('REQUIRE_2FA', 'False') == 'True'
OTP_TOTP_ISSUER = 'Путь наблюдателя'

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            MACHINA_MAIN_TEMPLATE_DIR,
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'machina.core.context_processors.metadata',
                # Вход через VK
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- PostgreSQL ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'observatory_db'),
        'USER': os.getenv('DB_USER', 'observatory_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
    MACHINA_MAIN_STATIC_DIR,
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'machina_attachments': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': BASE_DIR / 'cache',
    },
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}
HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'auth.User'

# ===== НАСТРОЙКИ ВХОДА =====
# ВАЖНО: раньше здесь было '/login/' — такой страницы на сайте не существует
# (реальный вход только через VK ID, роут '/vk/login/'). Из-за этого любая
# защищённая страница (@login_required) при разлогине кидала на 404 вместо
# входа. Обнаружено и исправлено 30.08.2026.
LOGIN_URL = '/vk/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    # ВАЖНО: этот API (bot_api) используется только VK-ботом — он всегда
    # шлёт Authorization: Token ... на каждый запрос. Ничего на сайте
    # (шаблоны, JS) им не пользуется. Раньше тут стоял IsAuthenticatedOrReadOnly,
    # из-за чего ЛЮБОЙ человек в интернете мог без пароля читать
    # /api/users/, /api/results/ (результаты упражнений) и
    # /api/admin/review/ (переписка клиента с психологом). Исправлено
    # 30.08.2026 — теперь чтение тоже требует токен.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Защита от перебора/шторма запросов к bot_api. Лимиты щедрые — бот
    # опрашивает несколько эндпоинтов на каждое событие VK longpoll — это
    # просто верхняя граница, а не рабочий предел обычной нагрузки.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '300/minute',
    },
}

CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
if not CORS_ALLOWED_ORIGINS or CORS_ALLOWED_ORIGINS == ['']:
    CORS_ALLOWED_ORIGINS = ['http://localhost:8000']

CORS_ALLOW_CREDENTIALS = True

# ВАЖНО: раньше эти 3 настройки включались только если явно задать
# соответствующую переменную в .env (а её там могло и не быть — тогда
# сайт работал бы БЕЗ этой защиты, даже в проде). Теперь они включаются
# автоматически, когда DEBUG=False (то есть всегда на сервере), и
# выключаются в локальной разработке (DEBUG=True), где HTTPS обычно нет.
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')

if not DEBUG:
    # HSTS — говорит браузеру всегда ходить на сайт только по HTTPS.
    # Начинаем с небольшого срока (1 час), чтобы проверить, что HTTPS
    # стабильно работает. Если через пару недель проблем не будет —
    # можно увеличить до года (31536000), как принято для продакшена.
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Верхняя граница на размер одной загрузки (аватар и т.п.) — защита от
# заполнения диска повторными большими файлами. Отдельная явная проверка
# размера/типа для аватара — в myapp/views.py: edit_profile.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 МБ
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 МБ

ADMIN_SITE_HEADER = "Путь Наблюдателя - Панель управления"
ADMIN_SITE_TITLE = "Путь Наблюдателя"
ADMIN_INDEX_TITLE = "Добро пожаловать в панель управления!"

VK_TOKEN = os.getenv('VK_TOKEN')
VK_GROUP_ID = os.getenv('VK_GROUP_ID')

# ===== ИИ-разбор текста на посты (массовая загрузка в CRM) =====
# Полностью опционально: без ANTHROPIC_API_KEY в .env — массовая загрузка
# постов работает как раньше (по дням недели / по строке ---), просто без
# ИИ-подстраховки для текста без чёткой разметки. Ключ — с console.anthropic.com,
# вводится сюда самостоятельно, Claude Code его не видит и не запрашивает.
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
AI_SPLIT_MODEL = os.getenv('AI_SPLIT_MODEL', 'claude-haiku-4-5')

# ===== Почта =====
# Ничего в проекте сейчас email не отправляет, но без EMAIL_BACKEND
# Django по умолчанию пытается отправлять письма через настоящий SMTP
# с пустыми настройками, что просто падает. Если в .env задан EMAIL_HOST —
# используем настоящий SMTP; если нет — безопасный вариант по умолчанию:
# письма печатаются в консоль/лог вместо реальной отправки.
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

MACHINA_FORUM_NAME = 'Путь наблюдателя'
MACHINA_MAIN_CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ================================================================
# ===== АВТОРИЗАЦИЯ ЧЕРЕЗ VK (social_django) =====
# ================================================================

AUTHENTICATION_BACKENDS = (
    'social_core.backends.vk.VKOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

# Используем переменные из .env
SOCIAL_AUTH_VK_OAUTH2_KEY = os.getenv('VK_CLIENT_ID')      # ID приложения
SOCIAL_AUTH_VK_OAUTH2_SECRET = os.getenv('VK_CLIENT_SECRET') # Защищённый ключ
SOCIAL_AUTH_VK_OAUTH2_SCOPE = ['email']
SOCIAL_AUTH_VK_OAUTH2_EXTRA_DATA = ['email', 'photo_max_orig']

SOCIAL_AUTH_CREATE_USERS = True
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = False
SOCIAL_AUTH_RAISE_EXCEPTIONS = False

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'myapp.pipeline.save_vk_avatar',  # Сохранение аватара
)

# Для совместимости с другими частями проекта
VK_APP_ID = os.getenv('VK_CLIENT_ID', '')
VK_APP_SECRET = os.getenv('VK_CLIENT_SECRET', '')