"""
Общая логика отправки PostChannelStatus через нужный адаптер публикации —
используется и планировщиком (crm/management/commands/publish_due_posts.py,
раз в 5 минут по cron), и ручной кнопкой «Опубликовать сейчас» в CRM
(crm/views.py: post_publish_now), чтобы не дублировать одну и ту же логику
в двух местах.
"""
from django.utils import timezone

from bot_api.models import Post
from crm.publishers import PUBLISHERS


def publish_channel_statuses(items):
    """Публикует список PostChannelStatus (обычно с select_related('post',
    'channel')) через адаптер платформы канала, обновляет статус каждой
    записи и агрегирует итоговый Post.status по всем затронутым постам.

    Возвращает список словарей — по одному на каждый item:
        {'item': PostChannelStatus, 'status': 'published'|'failed',
         'no_adapter': bool, 'message': str}
    Ничего не бросает наружу — сбой адаптера (сеть, токен и т.п.) уже
    учтён и записан как 'failed' с текстом ошибки в message."""
    items = list(items)
    results = []

    for item in items:
        publisher = PUBLISHERS.get(item.channel.platform)
        if publisher is None:
            item.status = 'failed'
            item.error_message = f"Нет адаптера публикации для платформы «{item.channel.platform}»"
            item.save(update_fields=['status', 'error_message'])
            results.append({
                'item': item, 'status': 'failed', 'no_adapter': True,
                'message': item.error_message,
            })
            continue

        success, result = publisher.publish(item.channel, item.post)
        if success:
            item.status = 'published'
            item.published_at = timezone.now()
            item.external_post_id = result or ''
            item.error_message = ''
            results.append({
                'item': item, 'status': 'published', 'no_adapter': False,
                'message': item.external_post_id,
            })
        else:
            item.status = 'failed'
            item.error_message = result or 'Неизвестная ошибка'
            results.append({
                'item': item, 'status': 'failed', 'no_adapter': False,
                'message': item.error_message,
            })
        item.save(update_fields=['status', 'published_at', 'external_post_id', 'error_message'])

    # Пост в целом считается опубликованным, когда опубликован хотя бы в
    # одном канале — статус на уровне Post нужен только для быстрого обзора
    # в CRM-списке, точная картина всегда в channel_statuses.
    touched_post_ids = {item.post_id for item in items}
    for post in Post.objects.filter(id__in=touched_post_ids):
        statuses = set(post.channel_statuses.values_list('status', flat=True))
        if 'published' in statuses:
            post.status = 'published'
        elif statuses and statuses <= {'failed'}:
            post.status = 'failed'
        post.save(update_fields=['status'])

    return results
