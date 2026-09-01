"""
Находит посты с полностью совпадающим текстом (точные дубли — например,
оставшиеся от массовой загрузки до 01.09.2026, когда защиты от дублей
ещё не было) и удаляет лишние копии, оставляя одну.

Безопасность: из каждой группы дублей оставляется САМЫЙ РАННИЙ по дате
пост, а более поздние дубли удаляются — но только если у дубля НЕТ ни
одного привязанного канала (PostChannelStatus). Если у дубля есть хоть
один канал (запланирован, опубликован или неудачно) — он не трогается
автоматически и попадает в список "пропущено", чтобы посмотреть руками.

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
            if post.channel_statuses.exists():
                skipped.append(post)
                continue
            to_delete.append((post, seen[key]))

        self.stdout.write(f"Дублей на удаление: {len(to_delete)}")
        for dup, original in to_delete:
            self.stdout.write(f"  удалить #{dup.id} ({dup.publish_date}) — дубль #{original.id} ({original.publish_date})")

        if skipped:
            self.stdout.write(self.style.WARNING(f"\nПропущено (есть привязанный канал — нужно смотреть руками): {len(skipped)}"))
            for post in skipped:
                self.stdout.write(f"  #{post.id} ({post.publish_date}) статус: {post.status}")

        if not apply:
            self.stdout.write(self.style.NOTICE("\nЭто предпросмотр, ничего не удалено. Чтобы удалить — добавь флаг --apply"))
            return

        count = len(to_delete)
        for dup, _ in to_delete:
            dup.delete()
        self.stdout.write(self.style.SUCCESS(f"\nУдалено: {count}"))