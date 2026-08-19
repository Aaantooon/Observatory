from django.urls import path
from . import views

app_name = 'myapp'

urlpatterns = [
    path('', views.ObservationListView.as_view(), name='observation_list'),
    path('add/', views.ObservationCreateView.as_view(), name='observation_add'),

    # VK-авторизация
    path('auth/vk/login/', views.vk_login, name='vk_login'),
    path('auth/vk/callback/', views.vk_callback, name='vk_callback'),
]