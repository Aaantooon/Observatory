from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date, timedelta
from .models import User, Exercise, Result, ExerciseProgress
from .serializers import UserSerializer, ExerciseSerializer, ResultSerializer
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        vk_id = self.request.query_params.get('vk_id')
        if vk_id:
            queryset = queryset.filter(user__vk_id=str(vk_id))
        return queryset

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        try:
            user = User.objects.get(vk_id=str(vk_id))
            notif = Notification.objects.create(
                user=user,
                exercise_type=request.data.get('exercise_type'),
                schedule_type=request.data.get('schedule_type'),
                schedule_data=request.data.get('schedule_data', {})
            )
            serializer = self.get_serializer(notif)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        vk_id = self.request.query_params.get('vk_id')
        if vk_id:
            queryset = queryset.filter(vk_id=str(vk_id))
        return queryset

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        if vk_id:
            user = User.objects.filter(vk_id=str(vk_id)).first()
            if user:
                serializer = self.get_serializer(user)
                return Response(serializer.data)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def update_streak(self, request):
        vk_id = request.data.get('vk_id')
        try:
            user = User.objects.get(vk_id=str(vk_id))
            today = date.today()
            
            if user.last_activity_date == today:
                return Response({'streak': user.streak, 'message': 'already_today'})
            elif user.last_activity_date == today - timedelta(days=1):
                user.streak += 1
            else:
                user.streak = 1 if user.last_activity_date else 0
            
            user.last_activity_date = today
            user.save()
            
            return Response({'streak': user.streak, 'message': 'updated'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        vk_id = self.request.query_params.get('vk_id')
        if vk_id:
            queryset = queryset.filter(user__vk_id=str(vk_id))
        return queryset

    def create(self, request, *args, **kwargs):
        user_vk_id = request.data.get('user_vk_id')
        exercise_id = request.data.get('exercise_id')
        
        try:
            user = User.objects.get(vk_id=str(user_vk_id))
            exercise = Exercise.objects.get(id=exercise_id)
            
            result = Result.objects.create(
                user=user,
                exercise=exercise,
                result_data=request.data.get('result_data', {})
            )
            
            serializer = self.get_serializer(result)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exercise.DoesNotExist:
            return Response(
                {'error': 'Exercise not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ProgressViewSet(viewsets.ViewSet):
    """API для сохранения и восстановления прогресса упражнений"""

    @action(detail=False, methods=['post'])
    def save(self, request):
        vk_id = request.data.get('vk_id')
        exercise_type = request.data.get('exercise_type', 'besilki')
        data = request.data.get('data', {})

        try:
            user = User.objects.get(vk_id=str(vk_id))
            progress, created = ExerciseProgress.objects.update_or_create(
                user=user,
                exercise_type=exercise_type,
                defaults={'data': data}
            )
            return Response({'status': 'saved', 'created': created})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def get(self, request):
        vk_id = request.query_params.get('vk_id')
        exercise_type = request.query_params.get('exercise_type', 'besilki')

        try:
            user = User.objects.get(vk_id=str(vk_id))
            progress = ExerciseProgress.objects.filter(
                user=user,
                exercise_type=exercise_type
            ).first()

            if progress:
                return Response({'data': progress.data, 'exists': True})
            return Response({'exists': False})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete'])
    def delete(self, request):
        vk_id = request.data.get('vk_id')
        exercise_type = request.data.get('exercise_type', 'besilki')

        try:
            user = User.objects.get(vk_id=str(vk_id))
            ExerciseProgress.objects.filter(
                user=user,
                exercise_type=exercise_type
            ).delete()
            return Response({'status': 'deleted'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)