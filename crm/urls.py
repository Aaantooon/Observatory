from django.urls import path
from . import views

urlpatterns = [
    path('', views.review_list, name='crm_review_list'),
    path('review/<int:review_id>/', views.review_detail, name='crm_review_detail'),
]