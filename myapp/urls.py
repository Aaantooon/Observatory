from django.urls import path
from . import views

urlpatterns = [
    path('course/', views.course_index, name='course_index'),
    path('course/module/<int:module_number>/', views.module_detail, name='course_module'),
    path('course/module/<int:module_number>/pdf/', views.module_pdf, name='module_pdf'),
    path('course/module/<int:module_number>/complete/', views.complete_module, name='complete_module'),
    path('course/module/<int:module_number>/comment/', views.add_comment, name='add_comment'),
    path('course/module/<int:module_number>/bookmark/', views.toggle_bookmark, name='toggle_bookmark'),
    path('api/course/progress/', views.course_progress_api, name='api_course_progress'),
    path('api/course/complete/', views.complete_module_api, name='api_course_complete'),
    path('api/course/association/', views.association_api, name='api_course_association'),
    path('api/stats/', views.course_progress_api, name='api_stats'),
    path('api/mindmap/', views.mindmap_data, name='api_mindmap'),
    path('api/mindmap/save-position/', views.mindmap_save_position, name='api_mindmap_save_position'),
    path('api/course/test-result/', views.submit_test_result_api, name='api_submit_test_result'),
    path('search/', views.search_course, name='search_course'),
    path('export/', views.export_progress, name='export_progress'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('achievements/', views.achievements_view, name='achievements'),
]