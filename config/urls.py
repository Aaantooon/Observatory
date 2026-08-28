from django.contrib import admin
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
    path('accounts/', include('django.contrib.auth.urls')),
    path('vk/login/', vk_login_start, name='vk_login_start'),
    path('vk/callback/', vk_login_callback, name='vk_login_callback'),
    
    # VK OAuth через social_django
    path('', include('social_django.urls', namespace='social')),
    
    # Основные страницы
    path('', views.home, name='home'),
    path('map/', views.map_reactflow_view, name='map'),
    path('observer/', views.observer_view, name='observer'),
    path('put/', views.put_view, name='put'),
    path('flashlight/', views.flashlight_view, name='flashlight'),
    path('profile/', views.profile_view, name='profile'),
    
    path('', include('myapp.urls')),
    path('3d/', include('observer3d.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)