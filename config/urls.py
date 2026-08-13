from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('map/', views.map_view, name='map'),
    path('put/', views.put_view, name='put'),
    path('observer-map/', views.observer_view, name='observer_view'),
    path('social/', include('myapp.urls')),
    path('api/', include('bot_api.urls')),   # ← ДОБАВИТЬ (API для бота)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)