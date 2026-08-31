from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .admin import admin_site  # Импортируем кастомную админку
from myapp.vk_id_auth import vk_login_start, vk_login_callback

urlpatterns = [
    path('admin/', admin_site.urls),  # Используем кастомную админку
    path('api/', include('bot_api.urls')),
    #path('forum/', include('machina.urls')),
    # Только login/logout из django.contrib.auth — реальный вход только
    # через VK ID (/vk/login/), у пользователей нет пароля, поэтому
    # password_change/password_reset НЕ подключаем: у них нет шаблонов
    # (никогда не были нужны) и они бы падали 500 у случайного визитёра.
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('vk/login/', vk_login_start, name='vk_login_start'),
    path('vk/callback/', vk_login_callback, name='vk_login_callback'),
    
    # VK OAuth через social_django
    path('', include('social_django.urls', namespace='social')),
    
    # Основные страницы
    path('', views.home, name='home'),
    path('map/', views.map_reactflow_view, name='map'),
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
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