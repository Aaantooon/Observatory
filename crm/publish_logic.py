"""
Общая логика отправки PostChannelStatus через нужный адаптер публикации —
используется и планировщиком (crm/management/commands/publish_due_posts.py,
раз в 5 минут по cron), и вебхуком-будильником (crm/views.py:
publish_due_webhook), и ручной кнопкой «Опубликовать сейчас» в CRM
(crm/views.py: post_publish_now), чтобы не дублировать одну и ту же логику
в трёх местах.
"""
from django.db import transaction
from django.utils import timezone

from bot_api.models import Post, PostChannelStatus
from crm.publishers import PUBLISHERS


def publish_channel_statuses(items):
    """Публикует список PostChannelStatus (обычно с select_related('post',
    'channel')) через адаптер платформы канала, обновляет статус каждой
    записи и агрегирует итоговый Post.status по всем затронутым постам.

    Возвращает список словарей — по одному на каждый item:
        {'item': PostChannelStatus, 'status': 'published'|'failed',
         'no_adapter': bool, 'message': str}
    Ничего не бросает наружу — сбой адаптера (сеть, токен и т.п.) уже
    учтён и записан как 'failed' с текстом ошибки в message.

    Раньше статус записи менялся только ПОСЛЕ вызова publisher.publish() —
    если два вызова наложатся друг на друга по времени (например, ручной
    cron и вебхук-будильник настроены оба сразу, или один прогон cron
    подвис на медленном ответе VK и следующий тик стартовал поверх него),
    оба успевали увидеть одну и ту же запись ещё в 'scheduled' и оба
    реально публиковали пост — получался дубль в ленте. Теперь каждая
    запись перед публикацией захватывается блокировкой строки
    (select_for_update) внутри транзакции и перепроверяется: если статус
    уже не тот, что был у вызывающего кода (кто-то другой успел раньше),
    запись просто пропускается, а не публикуется повторно."""
    items = list(items)
    expected_statuses = {item.pk: item.status for item in items}
    results = []

    with transaction.atomic():
        locked_by_id = {
            obj.pk: obj
            for obj in PostChannelStatus.objects
            .select_for_update()
            .filter(pk__in=expected_statuses.keys())
            .select_related('post', 'channel')
        }

        for item in items:
            locked = locked_by_id.get(item.pk)
            if locked is None or locked.status != expected_statuses[item.pk]:
                # Кто-то другой (второй параллельный запуск, вебхук поверх
                # cron и т.п.) уже забрал и обработал эту запись, пока мы
                # ждали блокировку — пропускаем, чтобы не отправить дубль.
                continue
            item = locked
            _publish_one(item, results)

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


def _publish_one(item, results):
    """Публикует одну (уже заблокированную select_for_update) запись и
    добавляет результат в results — вынесено из publish_channel_statuses,
    чтобы основная функция читалась как «захватить → опубликовать»."""
    publisher = PUBLISHERS.get(item.channel.platform)
    if publisher is None:
        item.status = 'failed'
        item.error_message = f"Нет адаптера публикации для платформы «{item.channel.platform}»"
        item.save(update_fields=['status', 'error_message'])
        results.append({
            'item': item, 'status': 'failed', 'no_adapter': True,
            'message': item.error_message,
        })
        return

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
