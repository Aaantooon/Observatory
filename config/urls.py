"""
urls.py — здесь мы связываем URL-адреса с кодом, который их обрабатывает.
Это как карта: по запросу пользователя мы находим нужную "страницу".
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Импортируем view из main, а не из config
from main import views

urlpatterns = [
    # Админка
    path('admin/', admin.site.urls),

    # Все маршруты из приложения main
    path('', include('main.urls')),

    # Встроенные маршруты для авторизации
    path('accounts/', include('django.contrib.auth.urls')),

    # Регистрация (добавляем напрямую)
    path('signup/', views.signup, name='signup'),
]

# В режиме отладки добавляем маршруты для медиа-файлов
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)