from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ExerciseViewSet, ResultViewSet, ProgressViewSet
from .views import UserViewSet, ExerciseViewSet, ResultViewSet, ProgressViewSet, NotificationViewSet
from .views import ReviewViewSet
router.register(r'admin/review', ReviewViewSet, basename='review')

router.register(r'notifications', NotificationViewSet, basename='notifications')
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'exercises', ExerciseViewSet, basename='exercises')
router.register(r'results', ResultViewSet, basename='results')
router.register(r'progress', ProgressViewSet, basename='progress')

urlpatterns = [
    path('', include(router.urls)),
]