"""
Создаёт по одной приветственной теме в каждом разделе форума, которые
создаёт seed_forum.py — иначе разделы после создания видны, но
совершенно пустые, и непонятно, что вообще в них писать.

⚠️ Честно, как и в seed_forum.py и platform_bots/max_adapter.py: эта
команда написана БЕЗ живого запуска против настоящей базы (в песочнице,
где она писалась, нет пакета django-machina) — только `ast.parse`.
В отличие от seed_forum.py (там использовалась только модель Forum,
в её API уверен уверенно), здесь ещё используются Topic и Post —
создание темы и первого сообщения в ней. Общая схема (Topic.objects.create
с полями forum/poster/subject/type, затем Post.objects.create с полями
topic/poster/subject/content) — это то, как django-machina создаёт темы
и в своих собственных тестовых фабриках, и это должно сработать, но
раз я не проверил это вживую — сначала прогони с --dry-run (по
умолчанию), посмотри на реальную ошибку, если она будет, и покажи мне
её текст, если что-то пойдёт не так: я поправлю по конкретной ошибке
вместо того чтобы гадать заранее.

Кто автор приветственных тем — первый пользователь с is_superuser=True
(обычно это ты сам, вошедший через /admin/). Если такого нет — команда
остановится с понятной ошибкой, ничего не сломав.

По умолчанию — предпросмотр, ничего не пишет в базу. Идемпотентна: если
в разделе уже есть хоть одна тема — новую не создаёт (значит, уже не
пусто, автоматическое приветствие больше не нужно).

Примеры:
    python manage.py seed_forum_topics
    python manage.py seed_forum_topics --yes
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

try:
    from machina.apps.forum.models import Forum
    from machina.apps.forum_conversation.models import Topic, Post
except ImportError:
    Forum = None
    Topic = None
    Post = None


# Названия форумов должны совпадать с child-разделами в seed_forum.py —
# если там переименуешь раздел, переименуй и здесь.
WELCOME_TOPICS = [
    {
        "forum_name": "🔦 Вопросы и ответы",
        "subject": "Добро пожаловать",
        "content": (
            "Если в упражнении бота или на сайте что-то не получается или непонятно — "
            "спрашивай прямо здесь, не стесняйся. Скорее всего, ты не единственный, "
            "у кого возник этот вопрос — твой вопрос поможет и другим."
        ),
    },
    {
        "forum_name": "🌱 Мой путь",
        "subject": "Добро пожаловать",
        "content": (
            "Здесь можно делиться тем, что получилось заметить или изменить в себе, "
            "проходя курс, — свои маленькие и большие наблюдения. Это не отчёт "
            "и не соревнование, просто место, где путь становится видимым не только тебе."
        ),
    },
    {
        "forum_name": "💬 Свободный разговор",
        "subject": "Добро пожаловать",
        "content": "Всё, что не поместилось в другие разделы, — сюда. Обычный человеческий разговор.",
    },
    {
        "forum_name": "📢 Объявления",
        "subject": "Форум открыт",
        "content": (
            "Здесь будут появляться новости и объявления проекта. "
            "А пока — просто добро пожаловать на форум «Путь наблюдателя»."
        ),
    },
]


class Command(BaseCommand):
    help = "Создаёт приветственную тему в каждом разделе форума. Без --yes — только предпросмотр."

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Реально создать (без флага — только показать, что будет создано)'
        )

    def handle(self, *args, **options):
        if Forum is None or Topic is None or Post is None:
            raise CommandError(
                "Не удалось импортировать machina (Forum/Topic/Post). Эта команда должна "
                "выполняться на сервере, где установлен и настроен django-machina, и после "
                "того как разделы форума уже созданы (python manage.py seed_forum --yes)."
            )

        poster = User.objects.filter(is_superuser=True).order_by('id').first()
        if poster is None:
            raise CommandError(
                "Не нашлось ни одного пользователя с is_superuser=True — создать тему не от "
                "чьего имени. Заведи суперпользователя (python manage.py createsuperuser) "
                "или зайди в /admin/ под существующим и повтори."
            )

        dry_run = not options['yes']
        planned = 0

        for item in WELCOME_TOPICS:
            forum = Forum.objects.filter(name=item["forum_name"]).first()
            if forum is None:
                self.stdout.write(self.style.WARNING(
                    f"? раздел «{item['forum_name']}» не найден — сначала выполни "
                    f"'python manage.py seed_forum --yes'"
                ))
                continue

            if Topic.objects.filter(forum=forum).exists():
                self.stdout.write(f"= в «{item['forum_name']}» уже есть темы — пропускаю")
                continue

            planned += 1
            self.stdout.write(f"{'[предпросмотр] ' if dry_run else ''}+ «{item['subject']}» → {item['forum_name']}")
            if not dry_run:
                topic = Topic.objects.create(
                    forum=forum,
                    poster=poster,
                    subject=item["subject"],
                    type=Topic.TOPIC_POST,
                )
                Post.objects.create(
                    topic=topic,
                    poster=poster,
                    subject=item["subject"],
                    content=item["content"],
                )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nЭто был предпросмотр — ничего не создано ({planned} тем было бы создано). "
                "Чтобы создать по-настоящему, добавь флаг --yes."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nГотово — создано тем: {planned}."))
