from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
from decouple import config


class Observation(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название наблюдения")
    description = models.TextField(verbose_name="Описание")
    location = models.CharField(max_length=200, verbose_name="Место наблюдения", blank=True)
    image = models.ImageField(upload_to='observations/', blank=True, null=True, verbose_name="Фото")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата публикации")

    def __str__(self):
        return self.title


# --- КОД ДЛЯ ОТПРАВКИ В TELEGRAM (ЧЕРЕЗ REQUESTS) ---
@receiver(post_save, sender=Observation)
def send_to_telegram(sender, instance, created, **kwargs):
    if created:  # Срабатывает только при создании нового поста
        try:
            # Получаем токен и ID из .env
            token = config('TG_BOT_TOKEN')
            chat_id = config('TG_CHAT_ID')

            # Формируем текст сообщения
            message = f"🪐 <b>Новое наблюдение!</b>\n\n"
            message += f"📍 <b>{instance.title}</b>\n"
            if instance.location:
                message += f"🗺️ {instance.location}\n"
            message += f"\n{instance.description}"

            # 1. Сначала отправляем текст
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data)

            # 2. Если есть картинка, отправляем её отдельно
            if instance.image:
                # Для локальной разработки используем полный URL с 127.0.0.1:8000
                image_url = f"http://127.0.0.1:8000{instance.image.url}"
                photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
                photo_data = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': f"📸 Фото к посту: {instance.title}"
                }
                requests.post(photo_url, data=photo_data)

        except Exception as e:
            # Если что-то пошло не так, ошибка выведется в консоль терминала
            print(f"❌ Ошибка отправки в Telegram: {e}")