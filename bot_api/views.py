from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date, timedelta
from django.utils import timezone
from .models import User, Exercise, Result, ExerciseProgress, Notification
from .serializers import (
    UserSerializer, ExerciseSerializer, ResultSerializer,
    NotificationSerializer
)
from .models import Review
from .serializers import ReviewSerializer
from django.utils import timezone

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        try:
            user = User.objects.get(vk_id=str(vk_id))
            review = Review.objects.create(
                user=user,
                exercise_type=request.data.get('exercise_type'),
                data=request.data.get('data', {}),
                status='pending'
            )
            return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def status(self, request):
        vk_id = request.query_params.get('vk_id')
        exercise_type = request.query_params.get('exercise_type')
        review = Review.objects.filter(
            user__vk_id=str(vk_id), exercise_type=exercise_type
        ).exclude(status='closed').order_by('-created_at').first()
        if review:
            return Response(self.get_serializer(review).data)
        return Response({'exists': False})

    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        review = self.get_object()
        review.comments.append({
            'text': request.data.get('comment'),
            'is_admin': request.data.get('is_admin', False),
            'created_at': timezone.now().isoformat()
        })
        if review.status == 'pending':
            review.status = 'in_review'
        review.save()
        return Response(self.get_serializer(review).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        review = self.get_object()
        review.status = 'closed'
        review.save()
        return Response(self.get_serializer(review).data)

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

    @action(detail=False, methods=['get'])
    def due(self, request):
        """Получить уведомления, которые пора отправить"""
        now = timezone.now()
        result = []
        for n in Notification.objects.filter(is_active=True):
            if n.schedule_type == 'once':
                delay = n.schedule_data.get('delay_hours', 0)
                if n.last_sent is None and now >= n.created_at + timedelta(hours=delay):
                    result.append(n)
            elif n.schedule_type == 'daily':
                target_time = n.schedule_data.get('time', '')
                current_time = now.strftime('%H:%M')
                already_today = n.last_sent and n.last_sent.date() == now.date()
                if current_time == target_time and not already_today:
                    result.append(n)
        serializer = self.get_serializer(result, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        """Отметить уведомление как отправленное"""
        notif = self.get_object()
        notif.last_sent = timezone.now()
        if notif.schedule_type == 'once':
            notif.is_active = False
        notif.save()
        return Response({'status': 'ok'})


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
        exercise_type = request.data.get('exercise_type')  # Изменено с exercise_id
        
        try:
            user = User.objects.get(vk_id=str(user_vk_id))
            
            # Ищем упражнение по типу
            exercise = Exercise.objects.filter(title=exercise_type).first()
            if not exercise:
                # Если упражнение не найдено, создаём его
                exercise = Exercise.objects.create(title=exercise_type)
            
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