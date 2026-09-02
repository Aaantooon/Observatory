from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .admin import admin_site  # Импортируем кастомную админку
from myapp.vk_id_auth import vk_login_start, vk_login_callback
from myapp.sitemaps import StaticViewSitemap, ModuleSitemap
from .twofa_views import setup_2fa, verify_2fa

sitemaps = {
    'static': StaticViewSitemap,
    'modules': ModuleSitemap,
}

urlpatterns = [
    path('admin/', admin_site.urls),  # Используем кастомную админку
    path('api/', include('bot_api.urls')),
    path('forum/', include('machina.urls')),
    # Только login/logout из django.contrib.auth — реальный вход только
    # через VK ID (/vk/login/), у пользователей нет пароля, поэтому
    # password_change/password_reset НЕ подключаем: у них нет шаблонов
    # (никогда не были нужны) и они бы падали 500 у случайного визитёра.
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('vk/login/', vk_login_start, name='vk_login_start'),
    path('vk/callback/', vk_login_callback, name='vk_login_callback'),

    # 2FA для /admin/ и /crm/ (01.09.2026) — см. REQUIRE_2FA в settings.py
    path('2fa/setup/', setup_2fa, name='twofa_setup'),
    path('2fa/verify/', verify_2fa, name='twofa_verify'),

    # ВАЖНО: URL-маршруты social_django (path('', include('social_django.urls', ...)))
    # намеренно НЕ подключаются. Это старый параллельный вход через VK OAuth,
    # который создавал бы отдельные, не связанные с ботом аккаунты User
    # (по другой схеме именования, чем vk_{vk_user_id} у настоящего входа
    # myapp/vk_id_auth.py). Ни один шаблон на него не ссылается — реальный
    # вход только через /vk/login/. Приложение social_django, миддлварь и
    # AUTHENTICATION_BACKENDS в settings.py оставлены как есть (решение
    # не трогать миграции/таблицы social_django) — закрыт только сам маршрут.

    # Основные страницы
    path('', views.home, name='home'),
    path('map/', views.map_reactflow_view, name='map'),
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_of_service_view, name='terms_of_service'),
    path('faq/', views.faq_view, name='faq'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('observer/', views.observer_view, name='observer'),
    path('put/', views.put_view, name='put'),
    path('flashlight/', views.flashlight_view, name='flashlight'),
    path('profile/', views.profile_view, name='profile'),
    
    path('', include('myapp.urls')),
    path('3d/', include('observer3d.urls')),
    path('crm/', include('crm.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)