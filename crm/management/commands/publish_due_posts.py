"""
Публикует запланированные посты, время которых уже наступило — в каждый
привязанный к посту канал (VK, позже Telegram/MAX).

Рассчитана на запуск по cron, как scripts/backup_db.sh, например раз в
5 минут:
    */5 * * * * cd ~/Observatory && source venv/bin/activate && \
        python manage.py publish_due_posts >> /var/log/observatory_publish.log 2>&1

Идемпотентна в разумных пределах: берёт только записи со статусом
'scheduled', и сразу переводит их в 'published' или 'failed', так что
повторный запуск (например, случайно запущенный вручную сразу после
cron) не отправит уже обработанные посты повторно. 'failed' сама не
повторяется — если токен истёк или была сетевая ошибка, статус нужно
вручную вернуть в 'scheduled' через /admin/ (или поправить канал и
пересоздать статус), чтобы не заспамить группу повторными попытками
без присмотра.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from bot_api.models import Post, PostChannelStatus
from crm.publishers import PUBLISHERS


class Command(BaseCommand):
    help = "Публикует посты, время которых наступило, во все привязанные каналы."

    def handle(self, *args, **options):
        due = (
            PostChannelStatus.objects
            .filter(status='scheduled', post__publish_date__lte=timezone.now(), channel__is_active=True)
            .select_related('post', 'channel')
        )

        if not due:
            self.stdout.write("Публиковать нечего.")
            return

        for item in due:
            publisher = PUBLISHERS.get(item.channel.platform)
            if publisher is None:
                item.status = 'failed'
                item.error_message = f"Нет адаптера публикации для платформы «{item.channel.platform}»"
                item.save(update_fields=['status', 'error_message'])
                self.stdout.write(self.style.WARNING(
                    f"  пропущено: пост {item.post_id} -> «{item.channel.name}» "
                    f"({item.channel.platform}) — нет адаптера"
                ))
                continue

            success, result = publisher.publish(item.channel, item.post)

            if success:
                item.status = 'published'
                item.published_at = timezone.now()
                item.external_post_id = result or ''
                item.error_message = ''
                self.stdout.write(self.style.SUCCESS(
                    f"  опубликовано: пост {item.post_id} -> «{item.channel.name}»"
                ))
            else:
                item.status = 'failed'
                item.error_message = result or 'Неизвестная ошибка'
                self.stdout.write(self.style.ERROR(
                    f"  ОШИБКА: пост {item.post_id} -> «{item.channel.name}»: {result}"
                ))

            item.save(update_fields=['status', 'published_at', 'external_post_id', 'error_message'])

        # Пост в целом считается опубликованным, когда опубликован хотя бы
        # в одном канале — статус на уровне Post нужен только для быстрого
        # обзора в CRM-списке, точная картина — в channel_statuses.
        touched_post_ids = {item.post_id for item in due}
        for post in Post.objects.filter(id__in=touched_post_ids):
            statuses = set(post.channel_statuses.values_list('status', flat=True))
            if 'published' in statuses:
                post.status = 'published'
            elif statuses and statuses <= {'failed'}:
                post.status = 'failed'
            post.save(update_fields=['status'])
