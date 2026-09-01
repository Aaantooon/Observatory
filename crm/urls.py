from django.urls import path
from . import views

urlpatterns = [
    path('', views.review_list, name='crm_review_list'),
    path('review/<int:review_id>/', views.review_detail, name='crm_review_detail'),
    path('clients/', views.client_list, name='crm_client_list'),
    path('clients/<int:user_id>/', views.client_detail, name='crm_client_detail'),
    path('posts/', views.post_list, name='crm_post_list'),
    path('posts/new/', views.post_create, name='crm_post_create'),
    path('posts/bulk/', views.post_bulk_create, name='crm_post_bulk'),
    path('posts/<int:post_id>/edit/', views.post_edit, name='crm_post_edit'),
    path('posts/<int:post_id>/delete/', views.post_delete, name='crm_post_delete'),
]