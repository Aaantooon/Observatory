"""
models.py — это описание структуры базы данных.
Каждая модель — это таблица в базе данных.
Каждое поле — это колонка в таблице.
Django умеет автоматически создавать таблицы по этим описаниям.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from .constants import *


# ============================================================
# 1. ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# ============================================================

class Profile(models.Model):
    """Расширение пользователя — добавляет уровень, биографию, аватар."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    level = models.CharField(
        max_length=20,
        choices=[(l.value, l.name.capitalize()) for l in UserLevel],
        default=UserLevel.BEGINNER.value
    )
    bio = models.TextField("О себе", blank=True)
    avatar = models.ImageField("Аватар", upload_to='avatars/', blank=True, null=True)
    last_seen_feedback_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_level_display()})"

    def get_absolute_url(self):
        return reverse('profile', kwargs={'username': self.user.username})


# ============================================================
# 2. КУРСЫ И МОДУЛИ
# ============================================================

class CourseCategory(models.Model):
    """Категория курсов."""
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField("Описание", blank=True)
    icon = models.CharField("Иконка", max_length=50, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Категория курсов"
        verbose_name_plural = "Категории курсов"

    def __str__(self):
        return self.name


class Course(models.Model):
    """Курс — основной продукт."""
    category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField("Название", max_length=200)
    slug = models.SlugField(unique=True)
    subtitle = models.CharField("Подзаголовок", max_length=300, blank=True)
    description = models.TextField("Описание")
    level = models.CharField(
        max_length=20,
        choices=[(l.value, l.name.capitalize()) for l in UserLevel],
        default=UserLevel.BEGINNER.value
    )
    image = models.ImageField("Изображение", upload_to='courses/', blank=True, null=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField("Бесплатный", default=False)
    is_published = models.BooleanField("Опубликован", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course_detail', kwargs={'slug': self.slug})


class Module(models.Model):
    """Модуль внутри курса."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField("Название модуля", max_length=200)
    number = models.PositiveIntegerField("Номер модуля")
    description = models.TextField("Описание", blank=True)
    is_required = models.BooleanField("Обязательный", default=True)

    class Meta:
        ordering = ['number']
        unique_together = ('course', 'number')

    def __str__(self):
        return f"{self.course.title} — Модуль {self.number}: {self.title}"


class Lesson(models.Model):
    """Урок внутри модуля."""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField("Название", max_length=200)
    number = models.PositiveIntegerField("Номер урока")
    content = models.TextField("Содержание")
    video_url = models.URLField("Ссылка на видео", blank=True, null=True)
    duration = models.PositiveIntegerField("Длительность (мин)", default=0)

    class Meta:
        ordering = ['number']
        unique_together = ('module', 'number')

    def __str__(self):
        return f"{self.module.title} — Урок {self.number}: {self.title}"


# ============================================================
# 3. СЕМИНАРСКИЕ ГРУППЫ
# ============================================================

class SeminarGroup(models.Model):
    """Группа для бесплатных семинаров."""
    name = models.CharField("Название группы", max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='seminar_groups', null=True, blank=True)
    description = models.TextField("Описание", blank=True)
    min_participants = models.PositiveIntegerField("Минимум участников", default=3)
    start_date = models.DateField("Дата старта")
    end_date = models.DateField("Дата окончания", null=True, blank=True)
    is_active = models.BooleanField("Активна", default=True)
    is_full = models.BooleanField("Набрана", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.participants_count()}/{self.min_participants}+)"

    def participants_count(self):
        return self.participations.count()

    def is_ready_to_start(self):
        return self.participants_count() >= self.min_participants


class Seminar(models.Model):
    """Один семинар в цикле из 16."""
    group = models.ForeignKey(SeminarGroup, on_delete=models.CASCADE, related_name='seminars')
    number = models.PositiveIntegerField("Номер семинара")
    title = models.CharField("Тема семинара", max_length=250)
    date = models.DateTimeField("Дата и время")
    description = models.TextField("Описание/задание", blank=True)
    material_url = models.URLField("Ссылка на материалы", blank=True, null=True)
    video_url = models.URLField("Ссылка на видео", blank=True, null=True)
    is_completed = models.BooleanField("Проведён", default=False)

    class Meta:
        ordering = ['number']
        unique_together = ('group', 'number')

    def __str__(self):
        return f"{self.group.name} — №{self.number}: {self.title}"


class Participation(models.Model):
    """Участие пользователя в группе и его прогресс."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='participations')
    group = models.ForeignKey(SeminarGroup, on_delete=models.CASCADE, related_name='participations')
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_seminars = models.ManyToManyField(Seminar, blank=True, related_name='completed_by')

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.username} в {self.group.name}"

    def progress(self):
        total = self.group.seminars.count()
        if total == 0:
            return 0
        return int(self.completed_seminars.count() / total * 100)


# ============================================================
# 4. МЕНТАЛЬНЫЕ КАРТЫ
# ============================================================

class ObservationMap(models.Model):
    """Ментальная карта наблюдателя."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='maps')
    title = models.CharField("Название карты", max_length=200)
    central_node = models.CharField("Центральный узел", max_length=200)
    level = models.CharField(
        max_length=20,
        choices=[(l.value, l.name.capitalize()) for l in UserLevel],
        default=UserLevel.BEGINNER.value
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_level_display()})"

    def get_absolute_url(self):
        return reverse('map_detail', kwargs={'pk': self.pk})


class MapNode(models.Model):
    """Узел ментальной карты (ветвь)."""
    map = models.ForeignKey(ObservationMap, on_delete=models.CASCADE, related_name='nodes')
    parent_node = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    label = models.CharField("Метка узла", max_length=150)
    content = models.TextField("Содержание узла", blank=True)
    node_type = models.CharField(
        "Тип узла",
        max_length=30,
        choices=[(t.value, t.name.capitalize()) for t in MapNodeType],
        default=MapNodeType.FACT.value
    )
    source_seminar = models.ForeignKey(Seminar, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    review_status = models.CharField(
        "Статус проверки",
        max_length=30,
        choices=[
            ('pending', 'На проверке'),
            ('approved', 'Одобрено'),
            ('needs_rework', 'На доработке'),
            ('excellent', 'Отлично'),
            ('possible_substitution', 'Возможная подмена'),
        ],
        default='pending'
    )
    risk_type = models.CharField(
        "Тип риска",
        max_length=50,
        choices=[
            ('none', 'Нет риска'),
            ('possible_substitution', 'Возможная подмена понятий'),
            ('weak_argument', 'Слабая аргументация'),
            ('no_example', 'Нет примера'),
            ('ambiguous', 'Двусмысленность'),
        ],
        default='none'
    )
    weight = models.FloatField("Вес", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label} ({self.get_node_type_display()})"


class MapEdge(models.Model):
    """Связь между узлами (A → B)."""
    source_node = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name='outgoing_edges')
    target_node = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name='incoming_edges')
    edge_type = models.CharField(
        "Тип связи",
        max_length=30,
        choices=[(e.value, e.name.capitalize()) for e in EdgeType],
        default=EdgeType.EXPLAINS.value
    )
    reason = models.TextField("Пояснение", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('source_node', 'target_node')

    def __str__(self):
        return f"{self.source_node.label} → {self.target_node.label} ({self.get_edge_type_display()})"


# ============================================================
# 5. СЕМИНАРСКИЕ ОТВЕТЫ (мини-разборы)
# ============================================================

class SeminarSubmission(models.Model):
    """Ответ на задание семинара (3 поля: факт, интерпретация, искажение)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    seminar = models.ForeignKey(Seminar, on_delete=models.CASCADE, related_name='submissions')
    fact = models.TextField("Факт, который я заметил")
    interpretation = models.TextField("Моя интерпретация")
    possible_bias = models.TextField("Возможное искажение", blank=True)
    is_submitted = models.BooleanField("Сдано", default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_status = models.CharField(
        max_length=30,
        choices=[
            ('pending', 'Ожидает проверки'),
            ('approved', 'Принято'),
            ('needs_clarification', 'Нужно уточнение'),
            ('rejected', 'Требует переработки'),
        ],
        default='pending'
    )
    review_comment = models.TextField("Комментарий ведущего", blank=True)
    needs_personal_review = models.BooleanField("Требует личной проработки", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'seminar')

    def __str__(self):
        return f"{self.user.username} — {self.seminar.title}"


# ============================================================
# 6. ВЕРСИИ УЗЛОВ
# ============================================================

class MapNodeVersion(models.Model):
    """Версия узла — снимок состояния на момент изменения."""
    node = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name='versions')
    label = models.CharField(max_length=150)
    content = models.TextField(blank=True)
    node_type = models.CharField(max_length=30)
    review_status = models.CharField(max_length=30)
    risk_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField("Активная версия", default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.node.label} — версия от {self.created_at.strftime('%d.%m.%Y %H:%M')}"


# ============================================================
# 7. ФОРУМ
# ============================================================

class ForumCategory(models.Model):
    """Категория форума."""
    name = models.CharField("Название категории", max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField("Описание", blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Категория форума"
        verbose_name_plural = "Категории форума"

    def __str__(self):
        return self.name


class ForumThread(models.Model):
    """Тема на форуме."""
    category = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='threads')
    title = models.CharField("Заголовок темы", max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_threads')
    content = models.TextField("Содержание")
    is_pinned = models.BooleanField("Закреплена", default=False)
    is_closed = models.BooleanField("Закрыта", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('forum_thread', kwargs={'pk': self.pk})

    def post_count(self):
        return self.posts.count()


class ForumPost(models.Model):
    """Сообщение в теме форума."""
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    content = models.TextField("Сообщение")
    parent_post = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} — {self.thread.title[:30]}"


# ============================================================
# 8. ЧАТ
# ============================================================

class ChatMessage(models.Model):
    """Сообщение в чате."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    content = models.TextField("Сообщение")
    is_public = models.BooleanField("Публичное", default=True)
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.author.username}: {self.content[:50]}"


# ============================================================
# 9. ОБРАТНАЯ СВЯЗЬ ПО РАЗБОРАМ
# ============================================================

class ReviewFeedback(models.Model):
    """Обратная связь ведущего на мини-разбор."""
    submission = models.OneToOneField(SeminarSubmission, on_delete=models.CASCADE, related_name='feedback')
    feedback_strengths = models.TextField("Комментарий по сильным сторонам", blank=True)
    feedback_shadows = models.TextField("Комментарий по теням", blank=True)
    feedback_to_check = models.TextField("Что проверить", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Обратная связь для {self.submission.user.username}"


class FeedbackNodeLink(models.Model):
    """Связь между обратной связью и узлами карты."""
    feedback = models.ForeignKey(ReviewFeedback, on_delete=models.CASCADE, related_name='node_links')
    node = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name='feedback_links')
    block_type = models.CharField(
        max_length=20,
        choices=[
            ('strengths', 'Сильные стороны'),
            ('shadows', 'Тени'),
            ('to_check', 'Что проверить'),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback.submission.user.username} — {self.node.label}"


# ============================================================
# 10. ЗАПРОСЫ НА УТОЧНЕНИЕ
# ============================================================

class ClarificationRequest(models.Model):
    """Запрос уточнения от ведущего к куратору."""
    feedback = models.ForeignKey(ReviewFeedback, on_delete=models.CASCADE, related_name='clarification_requests')
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Черновик'),
            ('sent', 'Отправлен'),
            ('in_progress', 'В работе'),
            ('resolved', 'Закрыт'),
        ],
        default='draft'
    )
    message = models.TextField("Текст запроса")
    resolved_nodes = models.ManyToManyField(MapNode, blank=True, related_name='clarified_in')
    resolution_summary = models.TextField("Ответ куратора", blank=True)
    snapshot_data = models.JSONField("Снапшот данных", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Запрос по {self.feedback.submission.user.username}"


# ============================================================
# 11. ПАТТЕРНЫ (ТРИГГЕРЫ) ДЛЯ АВТО-ДЕТЕКЦИИ
# ============================================================

class TriggerRule(models.Model):
    """Активное правило замены слов."""
    old_phrase = models.CharField(max_length=200)
    new_phrase = models.CharField(max_length=200)
    node_type = models.CharField(max_length=100, blank=True, null=True)
    count = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(auto_now=True)
    sample_node_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("old_phrase", "new_phrase", "node_type")

    def __str__(self):
        return f"{self.old_phrase} → {self.new_phrase}"


class AutoTriggerCandidate(models.Model):
    """Кандидат на правило, найденный автоматически."""
    old_phrase = models.CharField(max_length=200)
    new_phrase = models.CharField(max_length=200)
    node_type = models.CharField(max_length=100, blank=True, null=True)
    count = models.PositiveIntegerField(default=0)
    post_suppression_count = models.PositiveIntegerField(default=0)
    sample_data = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name.capitalize()) for s in TriggerStatus],
        default=TriggerStatus.PENDING.value
    )
    rejection_count = models.PositiveIntegerField(default=0)
    last_rejected_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"Candidate: {self.old_phrase} → {self.new_phrase} ({self.status})"


class RejectedTrigger(models.Model):
    """Отклонённое правило (для истории и анализа)."""
    old_phrase = models.CharField(max_length=200)
    new_phrase = models.CharField(max_length=200)
    node_type = models.CharField(max_length=100, blank=True, null=True)
    rejection_count = models.PositiveIntegerField(default=0)
    last_rejected_at = models.DateTimeField(auto_now=True)
    rejected_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ("old_phrase", "new_phrase", "node_type")


class TriggerApprovalLog(models.Model):
    """Лог одобрений/отклонений."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    candidate = models.ForeignKey(AutoTriggerCandidate, on_delete=models.SET_NULL, null=True)
    rule = models.ForeignKey(TriggerRule, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=[('approve', 'Одобрено'), ('reject', 'Отклонено')])
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.action} ({self.timestamp})"