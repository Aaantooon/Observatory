import random

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from .models import User, Exercise, Result, ExerciseProgress, Notification, AccountLinkCode
from .serializers import (
    UserSerializer, ExerciseSerializer, ResultSerializer,
    NotificationSerializer
)
from .models import Review
from .serializers import ReviewSerializer
from django.utils import timezone


def _platform_id_kwargs(vk_id=None, telegram_id=None, prefix=''):
    """Kwargs для User.objects.get/filter (или queryset.filter(user__...))
    по ID пользователя ЛЮБОЙ платформы — VK (vk_id, как было всегда) или
    Telegram (telegram_id, добавлено на шаге 4 плана platform_bots/README.md).
    telegram_id в приоритете, если передан — так исторически ходит
    api_client.py (vk_bot/api_client.py::APIClient сам решает, какое из
    двух полей слать, в зависимости от self.platform); существующие
    VK-запросы шлют только vk_id и telegram_id никогда не передают, так что
    их поведение не меняется ни на бит. prefix — для фильтрации через
    related-поле, например 'user__' в queryset.filter(**kwargs)."""
    if telegram_id:
        return {f'{prefix}telegram_id': str(telegram_id)}
    return {f'{prefix}vk_id': str(vk_id)}


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')
        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
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
        telegram_id = request.query_params.get('telegram_id')
        exercise_type = request.query_params.get('exercise_type')
        review = Review.objects.filter(
            exercise_type=exercise_type,
            **_platform_id_kwargs(vk_id, telegram_id, prefix='user__')
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

    @action(detail=False, methods=['get'])
    def pending_admin_comments(self, request):
        """Комментарии админа, ещё не отправленные пользователю в боте.

        Отдаём и user_vk_id, и user_telegram_id (одно из них null,
        зависит от платформы пользователя) — этот эндпоинт, как и
        /notifications/due/, не фильтрует по платформе на сервере, оба
        фоновых процесса (VK и Telegram) видят один и тот же список и сами
        решают по этим двум полям, что им обрабатывать (см.
        vk_bot/notifications.py::NotificationSystem._extract_platform_user_id)."""
        result = []
        for review in Review.objects.exclude(status='closed'):
            for i, c in enumerate(review.comments):
                if c.get('is_admin') and not c.get('sent_to_bot'):
                    result.append({
                        'review_id': review.id,
                        'comment_index': i,
                        'user_vk_id': review.user.vk_id,
                        'user_telegram_id': review.user.telegram_id,
                        'exercise_type': review.exercise_type,
                        'text': c.get('text')
                    })
        return Response(result)

    @action(detail=True, methods=['post'])
    def mark_comment_sent(self, request, pk=None):
        review = self.get_object()
        idx = request.data.get('comment_index')
        if idx is not None and 0 <= idx < len(review.comments):
            review.comments[idx]['sent_to_bot'] = True
            review.save()
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'])
    def active_for_user(self, request):
        """Активная проверка пользователя (для ответа)"""
        vk_id = request.query_params.get('vk_id')
        telegram_id = request.query_params.get('telegram_id')
        review = Review.objects.filter(
            **_platform_id_kwargs(vk_id, telegram_id, prefix='user__')
        ).exclude(status='closed').order_by('-created_at').first()
        if review:
            return Response(self.get_serializer(review).data)
        return Response({'exists': False})

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        vk_id = self.request.query_params.get('vk_id')
        telegram_id = self.request.query_params.get('telegram_id')
        if vk_id or telegram_id:
            queryset = queryset.filter(**_platform_id_kwargs(vk_id, telegram_id, prefix='user__'))
        return queryset

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')
        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
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
        # Напоминания 'daily' задаются пользователем как локальное время
        # (например "08:00" по Москве, см. vk_bot/notifications.py) — но
        # now.strftime()/.date() без localtime() работает в UTC (settings.py:
        # USE_TZ=True, TIME_ZONE='Europe/Moscow', а timezone.now() всегда
        # возвращает UTC-aware datetime независимо от TIME_ZONE). Без этой
        # поправки все дневные напоминания срабатывали на 3 часа позже, чем
        # настроил пользователь.
        local_now = timezone.localtime(now)
        result = []
        for n in Notification.objects.filter(is_active=True):
            if n.schedule_type == 'once':
                delay = n.schedule_data.get('delay_hours', 0)
                if n.last_sent is None and now >= n.created_at + timedelta(hours=delay):
                    result.append(n)
            elif n.schedule_type == 'daily':
                target_time = n.schedule_data.get('time', '')
                current_time = local_now.strftime('%H:%M')
                already_today = n.last_sent and timezone.localtime(n.last_sent).date() == local_now.date()
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
        telegram_id = self.request.query_params.get('telegram_id')
        if vk_id or telegram_id:
            queryset = queryset.filter(**_platform_id_kwargs(vk_id, telegram_id))
        return queryset

    def create(self, request, *args, **kwargs):
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')
        if vk_id or telegram_id:
            user = User.objects.filter(**_platform_id_kwargs(vk_id, telegram_id)).first()
            if user:
                serializer = self.get_serializer(user)
                return Response(serializer.data)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def update_streak(self, request):
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')
        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
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
        telegram_id = self.request.query_params.get('telegram_id')
        if vk_id or telegram_id:
            queryset = queryset.filter(**_platform_id_kwargs(vk_id, telegram_id, prefix='user__'))
        return queryset

    def create(self, request, *args, **kwargs):
        user_vk_id = request.data.get('user_vk_id')
        user_telegram_id = request.data.get('user_telegram_id')
        exercise_type = request.data.get('exercise_type')  # Изменено с exercise_id

        try:
            user = User.objects.get(**_platform_id_kwargs(user_vk_id, user_telegram_id))

            # Ищем упражнение по типу. get_or_create вместо filter().first()
            # + create() — при filter+create два параллельных запроса на ещё
            # не существующий exercise_type (например, первый результат
            # нового упражнения от двух разных пользователей одновременно)
            # оба видели пустой filter() и оба создавали свою запись Exercise
            # с одинаковым type — задваивая справочник упражнений.
            exercise, _ = Exercise.objects.get_or_create(
                type=exercise_type, defaults={'title': exercise_type}
            )

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
        telegram_id = request.data.get('telegram_id')
        exercise_type = request.data.get('exercise_type', 'besilki')
        data = request.data.get('data', {})

        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
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
        telegram_id = request.query_params.get('telegram_id')
        exercise_type = request.query_params.get('exercise_type', 'besilki')

        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
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
        telegram_id = request.data.get('telegram_id')
        exercise_type = request.data.get('exercise_type', 'besilki')

        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
            ExerciseProgress.objects.filter(
                user=user,
                exercise_type=exercise_type
            ).delete()
            return Response({'status': 'deleted'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


def _merge_users(source_user, target_user):
    """Переносит ВСЕ данные target_user на source_user и удаляет теперь
    пустой target_user — единственное место, где реально происходит
    объединение аккаунтов (см. AccountLinkViewSet.confirm ниже). Вызывать
    только внутри transaction.atomic() с уже проверенными
    source_user != target_user и отсутствием конфликта полей vk_id/telegram_id
    (см. confirm — обе проверки там, до вызова этой функции).

    Политика слияния по каждой модели, у которой есть FK на User
    (это все 4 модели — Result, Review, ExerciseProgress, Notification,
    сверено по bot_api/models.py):
    - Result, Review: конфликтов быть не может (нет unique-ограничений с
      user) — просто переносим все записи.
    - ExerciseProgress: unique_together('user', 'exercise_type') — если
      ОБА аккаунта уже начинали одно и то же упражнение, конфликт
      разрешается в пользу более СВЕЖЕЙ (по updated_at) версии, вторая
      отбрасывается — молча терять прогресс плохо, но молча оставлять
      дублирующий незавершённый черновик ещё хуже (не с чем сравнивать,
      какой правильный), а более новая правка почти всегда то, что
      человек редактировал последним.
    - Notification: конфликтов на уровне БД нет, но одинаковое
      напоминание (тот же exercise_type/schedule_type/schedule_data),
      настроенное на ОБЕИХ платформах, задвоило бы рассылку — такие
      дубли у target_user просто удаляются, а не переносятся.
    - streak/last_activity_date (поля самого User) — берём МАКСИМУМ
      streak и БОЛЕЕ ПОЗДНЮЮ last_activity_date из двух: это эвристика
      (реальный дневной стрик по объединённой активности с обеих
      платформ задним числом точно не восстановить), но она не отбирает
      уже накопленный прогресс ни у одной из сторон.

    ВАЖНО про порядок операций: source_user.save() с уже скопированными
    vk_id/telegram_id должен произойти ПОСЛЕ target_user.delete() — пока
    target_user ещё существует в БД, эти значения на нём же и лежат
    (unique-ограничение на обоих полях), и сохранение source_user с тем
    же значением упадёт с IntegrityError. Поэтому: сначала переносим/
    разрешаем всё, что ссылается на target_user (Result/Review/
    ExerciseProgress/Notification), потом удаляем сам target_user, и
    только затем сохраняем source_user с новыми значениями полей.
    """
    for field in ('vk_id', 'telegram_id'):
        target_value = getattr(target_user, field)
        if target_value and not getattr(source_user, field):
            setattr(source_user, field, target_value)

    if target_user.streak > source_user.streak:
        source_user.streak = target_user.streak
    activity_dates = [d for d in (source_user.last_activity_date, target_user.last_activity_date) if d]
    if activity_dates:
        source_user.last_activity_date = max(activity_dates)

    Result.objects.filter(user=target_user).update(user=source_user)
    Review.objects.filter(user=target_user).update(user=source_user)

    for progress in ExerciseProgress.objects.filter(user=target_user):
        existing = ExerciseProgress.objects.filter(
            user=source_user, exercise_type=progress.exercise_type
        ).first()
        if existing:
            if progress.updated_at > existing.updated_at:
                existing.data = progress.data
                existing.save()
            progress.delete()
        else:
            progress.user = source_user
            progress.save()

    for notif in Notification.objects.filter(user=target_user):
        is_duplicate = Notification.objects.filter(
            user=source_user,
            exercise_type=notif.exercise_type,
            schedule_type=notif.schedule_type,
            schedule_data=notif.schedule_data,
        ).exists()
        if is_duplicate:
            notif.delete()
        else:
            notif.user = source_user
            notif.save()

    target_user.delete()
    source_user.save()


class AccountLinkViewSet(viewsets.ViewSet):
    """Привязка одного человека к нескольким платформам через одноразовый
    код — см. platform_bots/README.md, раздел «Модель пользователя», и
    bot_api/models.py::AccountLinkCode. Два действия, оба вызываются ботом
    (vk_bot/api_client.py::generate_link_code/confirm_link_code), у
    обычного человека нет прямого доступа к этому API:
    - generate: пользователь одной платформы просит код
    - confirm: пользователь ДРУГОЙ платформы называет этот код — сервер
      объединяет оба аккаунта в один (см. _merge_users выше)
    """

    @action(detail=False, methods=['post'])
    def generate(self, request):
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')
        try:
            user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
        except User.DoesNotExist:
            return Response({'error': 'user_not_found'}, status=status.HTTP_404_NOT_FOUND)

        if user.vk_id and user.telegram_id:
            return Response({'error': 'already_linked'}, status=status.HTTP_400_BAD_REQUEST)

        # Не плодить мусор — у одного пользователя разом действует не
        # больше одного кода (старые неиспользованные всё равно устарели
        # бы через LIFETIME_MINUTES, но нет смысла их копить).
        AccountLinkCode.objects.filter(source_user=user, used_at__isnull=True).delete()

        cutoff = timezone.now() - timedelta(minutes=AccountLinkCode.LIFETIME_MINUTES)
        code = None
        for _ in range(5):
            candidate = f"{random.randint(0, 999999):06d}"
            active_collision = AccountLinkCode.objects.filter(
                code=candidate, used_at__isnull=True, created_at__gte=cutoff
            ).exists()
            if not active_collision:
                code = candidate
                break
        if code is None:
            return Response({'error': 'try_again'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        link = AccountLinkCode.objects.create(code=code, source_user=user)
        return Response({'code': link.code, 'expires_in_minutes': AccountLinkCode.LIFETIME_MINUTES})

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        code = (request.data.get('code') or '').strip()
        vk_id = request.data.get('vk_id')
        telegram_id = request.data.get('telegram_id')

        try:
            target_user = User.objects.get(**_platform_id_kwargs(vk_id, telegram_id))
        except User.DoesNotExist:
            return Response({'error': 'user_not_found'}, status=status.HTTP_404_NOT_FOUND)

        link = AccountLinkCode.objects.filter(code=code).order_by('-created_at').first()
        if not link or not link.is_valid():
            return Response({'error': 'invalid_or_expired'}, status=status.HTTP_400_BAD_REQUEST)

        source_user = link.source_user
        if source_user.pk == target_user.pk:
            return Response({'error': 'same_account'}, status=status.HTTP_400_BAD_REQUEST)

        for field in ('vk_id', 'telegram_id'):
            s = getattr(source_user, field)
            t = getattr(target_user, field)
            if s and t and s != t:
                # Оба аккаунта уже отдельно привязаны к разным ID одной и
                # той же платформы — объединить некуда, потребовалась бы
                # отдельная операция "отвязать", которой пока нет.
                return Response({'error': 'conflict'}, status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            link = AccountLinkCode.objects.select_for_update().get(pk=link.pk)
            if not link.is_valid():
                return Response({'error': 'invalid_or_expired'}, status=status.HTTP_400_BAD_REQUEST)

            _merge_users(source_user, target_user)

            link.used_at = timezone.now()
            link.save()

        return Response({'status': 'ok'})

