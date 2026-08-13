from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Профиль пользователя из VK"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    vk_id = models.BigIntegerField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (VK: {self.vk_id})"


class Exercise(models.Model):
    """Упражнение"""
    EXERCISE_TYPES = [
        ('number', 'Число'),
        ('text', 'Текст'),
        ('time', 'Время'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=EXERCISE_TYPES, default='text')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Result(models.Model):
    """Результат выполнения упражнения"""
    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='results'
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='results'
    )

    result_data = models.JSONField(verbose_name="Ответ пользователя")
    is_approved = models.BooleanField(default=False)
    corrected_data = models.JSONField(null=True, blank=True, verbose_name="Коррекция психолога")
    correction_comment = models.TextField(null=True, blank=True, verbose_name="Комментарий психолога")

    completed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user_profile} - {self.exercise} ({self.completed_at})"