from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, ExerciseViewSet, ResultViewSet, ProgressViewSet, NotificationViewSet,
    ReviewViewSet, AccountLinkViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'exercises', ExerciseViewSet, basename='exercises')
router.register(r'results', ResultViewSet, basename='results')
router.register(r'progress', ProgressViewSet, basename='progress')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'admin/review', ReviewViewSet, basename='review')
router.register(r'link', AccountLinkViewSet, basename='link')

urlpatterns = [
    path('', include(router.urls)),
]