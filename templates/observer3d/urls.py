from django.urls import path
from . import views

app_name = 'observer3d'

urlpatterns = [
    path('', views.babylon_world, name='world'),
]