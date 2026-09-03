from django.db import models

class User(models.Model):
    # null=True на обоих полях — намеренно (шаг 4 плана миграции ботов на
    # несколько платформ, platform_bots/README.md): один и тот же человек
    # пока не может быть привязан сразу к VK и Telegram (см. README, раздел
    # «Модель пользователя»), у каждой записи заполнено ровно одно из двух
    # полей. unique=True на CharField с null=True допускает СКОЛЬКО УГОДНО
    # NULL-значений (в отличие от пустых строк, которых допускается только
    # одна) — то есть много VK-пользователей с telegram_id=NULL и много
    # Telegram-пользователей с vk_id=NULL сосуществуют без конфликта.
    vk_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    telegram_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    streak = models.IntegerField(default=0, verbose_name="Серия дней")
    last_activity_date = models.DateField(null=True, blank=True, verbose_name="Последняя активность")

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        platform_id = self.vk_id or self.telegram_id or '—'
        return f"{self.first_name} {self.last_name} (ID: {platform_id})"


class Exercise(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=50, default='default')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Result(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='results')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    result_data = models.JSONField()
    is_approved = models.BooleanField(default=False)
    corrected_data = models.JSONField(null=True, blank=True)
    correction_comment = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user} - {self.exercise.title}"


class ExerciseProgress(models.Model):
    """Сохраняет прогресс упражнения для продолжения"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progresses')
    exercise_type = models.CharField(max_length=50, default='besilki')
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'exercise_type']

    def __str__(self):
        return f"{self.user} - {self.exercise_type}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    exercise_type = models.CharField(max_length=50)
    schedule_type = models.CharField(max_length=20)  # 'daily' или 'once'
    schedule_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent = models.DateTimeField(null=True, blank=True)

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    exercise_type = models.CharField(max_length=50)
    data = models.JSONField()
    status = models.CharField(max_length=20, default='pending')  # pending / in_review / closed
    comments = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)    

class Channel(models.Model):
    """Конкретное место публикации — группа/канал в одной из платформ.
    Токен доступа вводится вручную через /admin/ (2FA) — эта сессия его
    не видит и не вводит за пользователя."""
    PLATFORM_CHOICES = [('vk', 'VK'), ('telegram', 'Telegram'), ('max', 'MAX')]

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=100, help_text="Человекочитаемое имя, например «Основная группа ВК»")
    external_id = models.CharField(
        max_length=100,
        help_text="ID группы/канала. Для VK — числовой ID сообщества (без минуса), из vk.com/club<ID> или "
                   "vk.com/id_community.",
    )
    access_token = models.CharField(
        max_length=255, blank=True,
        help_text="Токен доступа для публикации (для VK — токен сообщества с правом 'wall', из "
                   "Управление сообществом → Работа с API → Ключи доступа).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['platform', 'name']

    def __str__(self):
        return f"{self.get_platform_display()}: {self.name}"


class Post(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('scheduled', 'Запланирован'),
        ('published', 'Опубликован'),
        ('failed', 'Ошибка публикации'),
    ]
    # platform/status — старые поля, оставлены для совместимости с постами,
    # созданными до появления Channel/PostChannelStatus (per-канальный статус
    # ниже). Новые посты используют channels (M2M) — конкретная платформа и
    # статус публикации хранятся отдельно на каждый канал в PostChannelStatus.
    platform = models.CharField(max_length=20, blank=True, help_text="Устаревшее поле, не используется в новых постах.")
    text = models.TextField()
    publish_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    channels = models.ManyToManyField(Channel, through='PostChannelStatus', blank=True, related_name='posts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['publish_date']

    def __str__(self):
        return f"Пост от {self.publish_date:%d.%m.%Y %H:%M}: {self.text[:40]}"


class PostChannelStatus(models.Model):
    """Статус публикации одного поста в одном конкретном канале — у поста,
    отправленного сразу в VK и Telegram, статус в каждом свой (например,
    в VK успешно ушло, а в Telegram — ошибка токена)."""
    STATUS_CHOICES = [
        ('scheduled', 'Запланирован'),
        ('published', 'Опубликован'),
        ('failed', 'Ошибка'),
    ]
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='channel_statuses')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='post_statuses')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    published_at = models.DateTimeField(null=True, blank=True)
    external_post_id = models.CharField(max_length=100, blank=True, help_text="ID опубликованного поста в самой платформе (для ссылки).")
    error_message = models.TextField(blank=True)

    class Meta:
        unique_together = [('post', 'channel')]

    def __str__(self):
        return f"{self.post_id} -> {self.channel.name} ({self.status})"