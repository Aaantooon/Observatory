"""
Создаёт стартовый набор разделов форума (категория + несколько форумов
внутри неё) в теме проекта — «туман / фонарик / путь». Без этого форум
после включения в urls.py технически доступен, но полностью пуст.

⚠️ Честно, как и в platform_bots/max_adapter.py: модель Forum — из
стороннего пакета django-machina, которого нет в песочнице, где писался
этот код, поэтому команда НЕ была проверена реальным запуском против
настоящей базы — только `ast.parse`. Поля name/type (через константы
Forum.FORUM_CAT/Forum.FORUM_POST)/parent — это стабильная,
задокументированная часть API machina, в них уверен. А вот текстовое
поле description у machina — не обычный CharField, а поле с разметкой,
и как именно оно ведёт себя при обычном присваивании строки — не
проверял вживую, поэтому это место обёрнуто в try/except: если раздел
создался, а описание — нет, ничего не сломается, просто допиши
описание вручную в /admin/.

По умолчанию — предпросмотр, ничего не пишет в базу. Идемпотентна:
раздел с таким названием и родителем, который уже существует, повторно
не создаётся — команду можно запускать сколько угодно раз.

Примеры:
    python manage.py seed_forum
    python manage.py seed_forum --yes
"""
from django.core.management.base import BaseCommand, CommandError

try:
    from machina.apps.forum.models import Forum
except ImportError:
    Forum = None


# Категория и форумы внутри неё — под тему проекта. Можно смело
# дописывать/переименовывать пункты здесь и просто перезапустить
# команду: то, что уже есть в базе (по названию), создано не будет.
SECTIONS = [
    {
        "name": "🌫️ Тропы наблюдателя",
        "description": "Общее пространство для тех, кто идёт по пути — вопросы, наблюдения, поддержка.",
        "children": [
            {
                "name": "🔦 Вопросы и ответы",
                "description": "Что-то не получается в упражнении или на сайте — спрашивай здесь.",
            },
            {
                "name": "🌱 Мой путь",
                "description": "Делись тем, что удалось заметить или изменить в себе — свой опыт прохождения курса.",
            },
            {
                "name": "💬 Свободный разговор",
                "description": "Всё, что не поместилось в другие разделы.",
            },
            {
                "name": "📢 Объявления",
                "description": "Новости и объявления проекта.",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Создаёт стартовые разделы форума (тема: туман/фонарик/путь). Без --yes — только предпросмотр."

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help='Реально создать (без флага — только показать, что будет создано)'
        )

    def handle(self, *args, **options):
        if Forum is None:
            raise CommandError(
                "Не удалось импортировать machina (from machina.apps.forum.models import Forum). "
                "Эта команда должна выполняться на сервере, где установлен и настроен django-machina."
            )

        dry_run = not options['yes']
        planned = 0

        for cat_def in SECTIONS:
            cat_name = cat_def["name"]
            category = Forum.objects.filter(name=cat_name, parent=None, type=Forum.FORUM_CAT).first()

            if category:
                self.stdout.write(f"= уже есть категория: {cat_name}")
            else:
                planned += 1
                self.stdout.write(f"{'[предпросмотр] ' if dry_run else ''}+ категория: {cat_name}")
                if not dry_run:
                    category = Forum.objects.create(name=cat_name, type=Forum.FORUM_CAT)
                    self._set_description(category, cat_def.get("description", ""))

            for child_def in cat_def.get("children", []):
                child_name = child_def["name"]
                # Если категория ещё не существует по-настоящему (ни раньше,
                # ни только что в этом прогоне, потому что это предпросмотр),
                # то и дочернего форума внутри неё точно нет.
                exists = (not dry_run) and bool(category) and Forum.objects.filter(
                    name=child_name, parent=category
                ).exists()

                if exists:
                    self.stdout.write(f"  = уже есть: {child_name}")
                    continue

                planned += 1
                self.stdout.write(f"  {'[предпросмотр] ' if dry_run else ''}+ {child_name}")
                if not dry_run:
                    forum = Forum.objects.create(name=child_name, type=Forum.FORUM_POST, parent=category)
                    self._set_description(forum, child_def.get("description", ""))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nЭто был предпросмотр — ничего не создано ({planned} раздел(ов) было бы создано). "
                "Чтобы создать по-настоящему, добавь флаг --yes."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nГотово — создано новых разделов: {planned}."))
            self.stdout.write(
                "Дальше — права: у machina своя система прав (не обычные Django-права), "
                "настраивается через собственный интерфейс форума (у форума для админа есть "
                "ссылка на управление правами) или через раздел 'Forum permission' в /admin/ — "
                "выдай группе аутентифицированных пользователей право видеть/читать/отвечать "
                "в новых разделах, иначе они будут видны, но писать в них будет нельзя."
            )

    def _set_description(self, forum, text):
        if not text:
            return
        try:
            forum.description = text
            forum.save()
        except Exception:
            # Поле description у machina может требовать особого способа
            # присваивания (markup-поле, не обычный CharField) — раздел
            # всё равно создан, описание можно дописать вручную в /admin/.
            self.stdout.write(self.style.WARNING(
                f"    (описание для «{forum.name}» не сохранилось автоматически — допиши вручную в /admin/)"
            ))
