from django.urls import path
from . import views

app_name = 'myapp'

urlpatterns = [
    path('', views.ObservationListView.as_view(), name='observation_list'),
    path('add/', views.ObservationCreateView.as_view(), name='observation_add'),
]