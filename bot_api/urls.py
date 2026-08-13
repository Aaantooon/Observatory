from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ExerciseViewSet, ResultViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'exercises', ExerciseViewSet, basename='exercises')
router.register(r'results', ResultViewSet, basename='results')

urlpatterns = [
    path('', include(router.urls)),
]