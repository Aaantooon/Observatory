"""
services.py — здесь хранится вся бизнес-логика.
Это отдельный слой между моделями и представлениями.
"""

from django.utils import timezone
from datetime import timedelta
from .constants import (
    BASE_REQUIRED_MATCHES, REJECTION_MULTIPLIER,
    SUPPRESSION_DAYS, TriggerStatus
)


# ============================================================
# 1. РАБОТА С КАНДИДАТАМИ НА ТРИГГЕРЫ
# ============================================================

def calculate_required_matches(rejection_count: int) -> int:
    """
    Рассчитывает, сколько совпадений нужно для возврата из тихого режима.
    Чем больше отклонений, тем выше порог.

    Пример:
    - 0 отклонений → нужно 5 совпадений
    - 1 отклонение → нужно 7 совпадений
    - 2 отклонения → нужно 9 совпадений
    """
    return BASE_REQUIRED_MATCHES + (rejection_count * REJECTION_MULTIPLIER)


def is_candidate_eligible_for_creation(candidate) -> bool:
    """
    Проверяет, можно ли создать/показать кандидата.
    Возвращает False, если кандидат в тихом режиме и не набрал порог для пробуждения.
    """
    # Если не в тихом режиме — всё ок
    if candidate.status != TriggerStatus.SUPPRESSED.value:
        return True

    # Если нет даты последнего отклонения — странно, но пусть будет False
    if not candidate.last_rejected_at:
        return False

    # Проверяем, прошло ли достаточно времени
    time_since_reject = timezone.now() - candidate.last_rejected_at
    if time_since_reject < timedelta(days=SUPPRESSION_DAYS):
        return False

    # Проверяем, набрано ли достаточно новых совпадений
    required = calculate_required_matches(candidate.rejection_count)
    if candidate.post_suppression_count < required:
        return False

    # Порог пройден — возвращаем кандидата в состояние "на рассмотрении"
    candidate.status = TriggerStatus.PENDING.value
    candidate.save(update_fields=["status"])
    return True