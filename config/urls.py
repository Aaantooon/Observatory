from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bot_api.urls')),
    
    # --- Форум (Machina) ---
    path('forum/', include('machina.urls')),
    
    # --- Авторизация (VK + стандартная) ---
    # ОБЯЗАТЕЛЬНО добавить этот путь для работы входа через VK
    path('', include('social_django.urls')),

    # Стандартные пути auth (login, logout и т.д.)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # --- Страницы сайта ---
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('map/', views.map_view, name='map'),
    path('observer/', views.observer_view, name='observer'),
    path('put/', views.put_view, name='put'),
    path('flashlight/', views.flashlight_view, name='flashlight'),
    
    # --- Наблюдения (myapp) ---
    path('observations/', include('myapp.urls')),
    
    # --- 3D Мир ---
    path('3d/', include('observer3d.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)