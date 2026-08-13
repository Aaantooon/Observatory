from django.urls import path
from . import views

urlpatterns = [
    path('channels/', views.channels_list, name='channels_list'),
    path('new_post/', views.new_post, name='new_post'),
    path('history/', views.post_history, name='post_history'),
]