from django.db import models
from django.utils import timezone

class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('telegram', 'Telegram'),
        ('vk', 'ВКонтакте'),
    ]
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=100, verbose_name='Название канала/группы')
    chat_id = models.CharField(max_length=50, verbose_name='ID чата (Telegram) или owner_id (VK)')
    token = models.CharField(max_length=200, verbose_name='Токен доступа')
    active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_platform_display()}: {self.name}"

    class Meta:
        verbose_name = 'Социальный аккаунт'
        verbose_name_plural = 'Социальные аккаунты'


class Post(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('sent', 'Отправлен'),
        ('failed', 'Ошибка'),
    ]
    text = models.TextField(verbose_name='Текст поста')
    image = models.ImageField(upload_to='posts/', blank=True, null=True, verbose_name='Изображение')
    platforms = models.ManyToManyField(SocialAccount, verbose_name='Платформы для публикации')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Пост от {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = 'Пост'
        verbose_name_plural = 'Посты'