"""
cleanup_candidates.py — команда для очистки устаревших кандидатов.
Запускается через python manage.py cleanup_candidates
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from main.models import AutoTriggerCandidate
from main.constants import TriggerStatus


class Command(BaseCommand):
    help = 'Очищает устаревшие кандидаты на триггеры'

    def handle(self, *args, **options):
        # Находим кандидатов, у которых истёк срок
        expired = AutoTriggerCandidate.objects.filter(
            status=TriggerStatus.PENDING.value,
            expires_at__lt=timezone.now()
        )

        count = expired.count()
        if count > 0:
            # Переводим их в статус "подавлен" (или удаляем)
            expired.update(status=TriggerStatus.SUPPRESSED.value)
            self.stdout.write(
                self.style.SUCCESS(f'Обработано {count} устаревших кандидатов')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Нет устаревших кандидатов')
            )