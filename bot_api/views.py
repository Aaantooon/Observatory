from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import UserProfile, Exercise, Result
from .serializers import UserProfileSerializer, ExerciseSerializer, ResultSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def get_or_create(self, request):
        """Получить или создать пользователя по vk_id"""
        vk_id = request.data.get('vk_id')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        user, created = UserProfile.objects.get_or_create(
            vk_id=vk_id,
            defaults={'first_name': first_name, 'last_name': last_name}
        )

        serializer = self.get_serializer(user)
        return Response(serializer.data)


class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.filter(is_active=True)
    serializer_class = ExerciseSerializer
    permission_classes = [AllowAny]


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        vk_id = self.request.query_params.get('vk_id')

        if vk_id:
            queryset = queryset.filter(user_profile__vk_id=vk_id)

        return queryset

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('user_vk_id')
        exercise_id = request.data.get('exercise_id')
        result_data = request.data.get('result_data')

        user = UserProfile.objects.get(vk_id=vk_id)
        exercise = Exercise.objects.get(id=exercise_id)

        result = Result.objects.create(
            user_profile=user,
            exercise=exercise,
            result_data=result_data
        )

        serializer = self.get_serializer(result)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        """Психолог подтверждает/корректирует результат"""
        result = self.get_object()
        result.is_approved = request.data.get('is_approved', True)
        result.corrected_data = request.data.get('corrected_data')
        result.correction_comment = request.data.get('correction_comment')
        result.save()

        serializer = self.get_serializer(result)
        return Response(serializer.data)