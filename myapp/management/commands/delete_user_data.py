"""
Полное и безвозвратное удаление всех данных одного пользователя — и на
стороне сайта (Django auth.User + всё, что каскадно на него завязано:
профиль, прогресс курса, серия дней, ассоциации в игре, комментарии,
позиции на карте, закладки), и на стороне бота (bot_api.User + всё
каскадное: результаты упражнений, прогресс упражнений, уведомления,
переписка с психологом).

Используется для запросов на удаление данных (см. страницу «Политика
конфиденциальности», раздел 5). ВСЕГДА сначала запускать БЕЗ --yes —
покажет, что будет удалено, но ничего не тронет.

Примеры:
    python manage.py delete_user_data --vk-id 123456789
    python manage.py delete_user_data --vk-id 123456789 --yes
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bot_api.models import User as BotUser


class Command(BaseCommand):
    help = "Безвозвратно удаляет все данные пользователя по его VK ID (сайт + бот)."

    def add_arguments(self, parser):
        parser.add_argument('--vk-id', required=True, help='VK ID пользователя (числовая строка)')
        parser.add_argument('--yes', action='store_true', help='Реально удалить (без флага — только показать, что будет удалено)')

    def handle(self, *args, **options):
        vk_id = str(options['vk_id']).strip()
        if not vk_id.isdigit():
            raise CommandError("--vk-id должен быть числом (VK ID пользователя)")

        username = f"vk_{vk_id}"
        django_user = User.objects.filter(username=username).first()
        bot_user = BotUser.objects.filter(vk_id=vk_id).first()

        if not django_user and not bot_user:
            self.stdout.write(self.style.WARNING(f"Пользователь с VK ID {vk_id} нигде не найден — удалять нечего."))
            return

        self.stdout.write(f"VK ID: {vk_id}")
        if django_user:
            self.stdout.write(f"  Сайт: аккаунт '{username}' (id={django_user.id}), включая профиль, "
                               f"прогресс курса, серию дней, ассоциации, комментарии, позиции карты, закладки.")
        else:
            self.stdout.write("  Сайт: аккаунта нет (пользователь не входил через VK ID).")
        if bot_user:
            self.stdout.write(f"  Бот: {bot_user.first_name} {bot_user.last_name} (id={bot_user.id}), включая "
                               f"результаты упражнений, прогресс, уведомления, переписку с психологом.")
        else:
            self.stdout.write("  Бот: записи нет (пользователь не писал боту).")

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                "\nЭто был предварительный просмотр. Ничего не удалено. "
                "Чтобы удалить по-настоящему, добавь флаг --yes."
            ))
            return

        with transaction.atomic():
            if django_user:
                django_user.delete()
            if bot_user:
                bot_user.delete()

        self.stdout.write(self.style.SUCCESS(f"\nГотово — все данные VK ID {vk_id} удалены безвозвратно."))
