from django.urls import path
from . import views

urlpatterns = [
    path('clients/', views.client_list, name='crm_client_list'),
    path('clients/<int:user_id>/', views.client_detail, name='crm_client_detail'),
]