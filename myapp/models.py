from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ===== СУЩЕСТВУЮЩАЯ МОДЕЛЬ =====
class Observation(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название наблюдения")
    description = models.TextField(verbose_name="Описание")
    location = models.CharField(max_length=200, verbose_name="Место наблюдения", blank=True)
    image = models.ImageField(upload_to='observations/', blank=True, null=True, verbose_name="Фото")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата публикации")

    def __str__(self):
        return self.title


@receiver(post_save, sender=Observation)
def send_to_telegram(sender, instance, created, **kwargs):
    if created:
        try:
            token = os.getenv('TG_BOT_TOKEN')
            chat_id = os.getenv('TG_CHAT_ID')
            if not token or not chat_id:
                print("⚠️ TG_BOT_TOKEN или TG_CHAT_ID не заданы в .env файле")
                return
            message = f"🪐 <b>Новое наблюдение!</b>\n\n📍 <b>{instance.title}</b>\n"
            if instance.location:
                message += f"🗺️ {instance.location}\n"
            message += f"\n{instance.description}"
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
            response = requests.post(url, data=data)
            if response.status_code != 200:
                print(f"⚠️ Ошибка отправки текста в Telegram: {response.text}")
            if instance.image:
                image_url = f"http://127.0.0.1:8000{instance.image.url}"
                photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
                photo_data = {'chat_id': chat_id, 'photo': image_url, 'caption': f"📸 Фото к посту: {instance.title}"}
                photo_response = requests.post(photo_url, data=photo_data)
                if photo_response.status_code != 200:
                    print(f"⚠️ Ошибка отправки фото в Telegram: {photo_response.text}")
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")


# ===== НОВЫЕ МОДЕЛИ ДЛЯ КУРСА =====
class Module(models.Model):
    """Модуль курса 'Путь наблюдателя'"""
    number = models.PositiveIntegerField(unique=True, verbose_name="Номер модуля")
    title = models.CharField(max_length=200, verbose_name="Название")
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="Подзаголовок")
    description = models.TextField(verbose_name="Описание")
    content = models.TextField(verbose_name="Содержание лекции", blank=True)
    
    position_x = models.FloatField(default=0, verbose_name="Позиция X в 3D")
    position_z = models.FloatField(default=0, verbose_name="Позиция Z в 3D")
    color = models.CharField(max_length=7, default="#6cbfff", verbose_name="Цвет в 3D")
    
    key_concepts = models.JSONField(default=list, verbose_name="Ключевые понятия")
    duration = models.PositiveIntegerField(default=30, verbose_name="Длительность (мин)")
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['number']
        verbose_name = "Модуль"
        verbose_name_plural = "Модули курса"
    
    def __str__(self):
        return f"{self.number}. {self.title}"
    
    def get_next(self):
        return Module.objects.filter(number=self.number + 1, is_published=True).first()
    
    def get_prev(self):
        return Module.objects.filter(number=self.number - 1, is_published=True).first()


class UserCourseProgress(models.Model):
    """Прогресс пользователя в курсе"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='course_progress')
    current_module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='users_at')
    completed_modules = models.ManyToManyField(Module, blank=True, related_name='completed_by')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Прогресс пользователя"
        verbose_name_plural = "Прогресс пользователей"
    
    def __str__(self):
        module = self.current_module
        return f"{self.user.username} - {module.title if module else 'Завершён'}"
    
    def get_progress_percent(self):
        total = Module.objects.filter(is_published=True).count()
        if total == 0:
            return 0
        return int((self.completed_modules.count() / total) * 100)
    
    def is_module_completed(self, module):
        return self.completed_modules.filter(id=module.id).exists()
    
    def complete_module(self, module):
        if not self.is_module_completed(module):
            self.completed_modules.add(module)
            next_module = module.get_next()
            if next_module:
                self.current_module = next_module
            else:
                self.completed_at = timezone.now()
            self.save()
            return True
        return False
    
    def get_game_state(self):
        modules = Module.objects.filter(is_published=True).order_by('number')
        completed_ids = list(self.completed_modules.values_list('id', flat=True))
        result = []
        for m in modules:
            if m.id in completed_ids:
                status = 'completed'
            elif self.current_module and m.id == self.current_module.id:
                status = 'unlocked'
            elif m.number == 1:
                status = 'unlocked'
            else:
                prev = m.get_prev()
                if prev and prev.id in completed_ids:
                    status = 'unlocked'
                else:
                    status = 'locked'
            result.append({
                'id': m.id,
                'number': m.number,
                'title': m.title,
                'subtitle': m.subtitle,
                'color': m.color,
                'x': m.position_x,
                'z': m.position_z,
                'status': status
            })
        return {'modules': result, 'progress_percent': self.get_progress_percent(), 'current_module_id': self.current_module.id if self.current_module else None, 'is_finished': self.completed_at is not None}


class GameAssociation(models.Model):
    """Ассоциации из игры"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_associations')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='associations')
    object_name = models.CharField(max_length=100, verbose_name="Объект")
    association = models.TextField(verbose_name="Ассоциация")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Ассоциация"
        verbose_name_plural = "Ассоциации"
    
    def __str__(self):
        return f"{self.user.username}: {self.object_name} → {self.association[:30]}"