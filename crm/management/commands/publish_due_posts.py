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
вручную вернуть в 'scheduled' через /admin/, либо воспользоваться кнопкой
«Опубликовать сейчас» в CRM (crm/views.py: post_publish_now) — она, в
отличие от этой команды, повторяет и 'failed' тоже, потому что это
осознанный ручной клик, а не автоматический разлив по расписанию.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from bot_api.models import PostChannelStatus
from crm.publish_logic import publish_channel_statuses


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

        results = publish_channel_statuses(due)
        for r in results:
            item = r['item']
            if r['status'] == 'published':
                self.stdout.write(self.style.SUCCESS(
                    f"  опубликовано: пост {item.post_id} -> «{item.channel.name}»"
                ))
            elif r['no_adapter']:
                self.stdout.write(self.style.WARNING(
                    f"  пропущено: пост {item.post_id} -> «{item.channel.name}» "
                    f"({item.channel.platform}) — нет адаптера"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"  ОШИБКА: пост {item.post_id} -> «{item.channel.name}»: {r['message']}"
                ))
