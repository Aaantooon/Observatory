from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    # Главные страницы
    path('', views.home, name='home'),
    path('community/', views.community, name='community'),

    # Курсы
    path('courses/', views.course_list, name='course_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),

    # Тренинги
    path('trainings/', views.trainings, name='trainings'),
    path('psychodiving/', views.psychodiving, name='psychodiving'),
    path('film-club/', views.film_club, name='film_club'),
    path('contact/', views.contact, name='contact'),

    # Личный кабинет
    path('dashboard/', views.dashboard, name='dashboard'),

    # Ментальные карты
    path('map/', views.map_view, name='map_view'),
    path('map/<int:pk>/', views.map_detail, name='map_detail'),
    path('map/create/', views.map_create, name='map_create'),

    # Форум
    path('forum/', views.forum_index, name='forum_index'),
    path('forum/<int:pk>/', views.forum_thread, name='forum_thread'),
    path('forum/create/', views.forum_create, name='forum_create'),

    # Семинарские группы
    path('groups/', views.group_list, name='group_list'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/join/', views.group_join, name='group_join'),

    # Профиль
    path('profile/<str:username>/', views.profile, name='profile'),

    # Регистрация (добавлено)
    path('signup/', views.signup, name='signup'),
]