from django.urls import path
from . import views

urlpatterns = [
    path('course/', views.course_index, name='course_index'),
    path('course/module/<int:module_number>/', views.module_detail, name='course_module'),
    path('course/module/<int:module_number>/complete/', views.complete_module, name='complete_module'),
    path('api/course/progress/', views.course_progress_api, name='api_course_progress'),
    path('api/course/complete/', views.complete_module_api, name='api_course_complete'),
    path('api/course/association/', views.association_api, name='api_course_association'),
]