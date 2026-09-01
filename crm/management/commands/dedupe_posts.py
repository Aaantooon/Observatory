"""
Находит посты с полностью совпадающим текстом (точные дубли — например,
оставшиеся от массовой загрузки до 01.09.2026, когда защиты от дублей
ещё не было) и удаляет лишние копии, оставляя одну.

Безопасность: из каждой группы дублей оставляется САМЫЙ РАННИЙ по дате
пост, а более поздние дубли удаляются — но только если это ничего не
теряет:
  - если у дубля вообще нет каналов — удаляется сразу;
  - если у дубля есть каналы, но у оригинала уже есть ТЕ ЖЕ каналы
    (по набору channel_id) — дубль всё равно безопасно удалить, оригинал
    и так их покрывает;
  - если у дубля есть хоть один опубликованный канал (status='published')
    — никогда не трогается автоматически, это реально отправленный пост;
  - если у дубля есть канал, которого нет у оригинала, — тоже не трогается
    автоматически (иначе эта привязка потеряется).
Всё, что не удалено автоматически, попадает в список "пропущено" — для
ручной проверки.

По умолчанию — только предпросмотр (dry-run), ничего не удаляет.
Реальное удаление — только с флагом --apply:

    python manage.py dedupe_posts            # предпросмотр
    python manage.py dedupe_posts --apply    # реально удалить
"""
from django.core.management.base import BaseCommand

from bot_api.models import Post


class Command(BaseCommand):
    help = "Удаляет точные дубли постов (по тексту), оставляя самый ранний экземпляр."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Реально удалить (без флага — только показать).')

    def handle(self, *args, **options):
        apply = options['apply']

        seen = {}
        to_delete = []
        skipped = []

        for post in Post.objects.order_by('publish_date', 'id'):
            key = post.text
            if key not in seen:
                seen[key] = post
                continue

            original = seen[key]
            dup_statuses = list(post.channel_statuses.all())

            if any(cs.status == 'published' for cs in dup_statuses):
                skipped.append((post, 'есть опубликованный канал'))
                continue

            dup_channel_ids = {cs.channel_id for cs in dup_statuses}
            original_channel_ids = set(original.channel_statuses.values_list('channel_id', flat=True))

            if not dup_channel_ids.issubset(original_channel_ids):
                missing = dup_channel_ids - original_channel_ids
                skipped.append((post, f'есть канал(ы), которых нет у оригинала: {sorted(missing)}'))
                continue

            to_delete.append((post, original))

        self.stdout.write(f"Дублей на удаление: {len(to_delete)}")
        for dup, original in to_delete:
            self.stdout.write(f"  удалить #{dup.id} ({dup.publish_date}) — дубль #{original.id} ({original.publish_date})")

        if skipped:
            self.stdout.write(self.style.WARNING(f"\nПропущено (нужно смотреть руками): {len(skipped)}"))
            for post, reason in skipped:
                self.stdout.write(f"  #{post.id} ({post.publish_date}) — {reason}")

        if not apply:
            self.stdout.write(self.style.NOTICE("\nЭто предпросмотр, ничего не удалено. Чтобы удалить — добавь флаг --apply"))
            return

        count = len(to_delete)
        for dup, _ in to_delete:
            dup.delete()
        self.stdout.write(self.style.SUCCESS(f"\nУдалено: {count}"))