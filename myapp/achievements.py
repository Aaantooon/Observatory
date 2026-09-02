"""Заготовка геймификации «стать Наблюдателем» — числилась в
СВОДКА_ПРОЕКТА.md как «не начато». Все условия проверяются по данным,
которые в проекте уже и так считаются (прогресс курса, серия дней,
ассоциации из игры, результаты тестов) — новых источников данных не
потребовалось, только сама выдача и учёт полученных достижений.

Как добавить новое достижение: дописать словарь в ACHIEVEMENTS ниже —
не нужно трогать модели или места, откуда вызывается check_and_award().
`code` — стабильный идентификатор (используется как Achievement.code в
БД), менять его для существующего достижения нельзя — это создаст новую
запись и выдаст достижение повторно всем, у кого оно уже было.
"""
from .models import (
    Achievement, UserAchievement, UserCourseProgress, UserStreak, GameAssociation,
    ModuleTestResult, ModuleComment, Bookmark, UserProfile,
)


def _course_progress(user):
    return UserCourseProgress.objects.filter(user=user).first()


def _streak(user):
    return UserStreak.objects.filter(user=user).first()


ACHIEVEMENTS = [
    {
        'code': 'first_step',
        'title': 'Первый шаг',
        'description': 'Пройди первый модуль курса',
        'icon': '🌱',
        'order': 10,
        'check': lambda user: (p := _course_progress(user)) is not None and p.completed_modules.count() >= 1,
    },
    {
        'code': 'halfway',
        'title': 'На середине пути',
        'description': 'Пройди половину модулей курса',
        'icon': '🌓',
        'order': 20,
        'check': lambda user: (p := _course_progress(user)) is not None and p.get_progress_percent() >= 50,
    },
    {
        'code': 'course_finished',
        'title': 'Наблюдатель',
        'description': 'Пройди курс полностью',
        'icon': '🔭',
        'order': 30,
        'check': lambda user: (p := _course_progress(user)) is not None and p.completed_at is not None,
    },
    {
        'code': 'streak_3',
        'title': 'Три дня подряд',
        'description': 'Занимайся 3 дня подряд',
        'icon': '🔥',
        'order': 40,
        'check': lambda user: (s := _streak(user)) is not None and s.current_streak >= 3,
    },
    {
        'code': 'streak_7',
        'title': 'Неделя света',
        'description': 'Занимайся 7 дней подряд',
        'icon': '🕯️',
        'order': 41,
        'check': lambda user: (s := _streak(user)) is not None and s.current_streak >= 7,
    },
    {
        'code': 'streak_30',
        'title': 'Месяц пути',
        'description': 'Занимайся 30 дней подряд',
        'icon': '🏮',
        'order': 42,
        'check': lambda user: (s := _streak(user)) is not None and s.current_streak >= 30,
    },
    {
        'code': 'first_association',
        'title': 'Первая связь',
        'description': 'Оставь первую ассоциацию в 3D-игре',
        'icon': '🔗',
        'order': 50,
        'check': lambda user: GameAssociation.objects.filter(user=user).exists(),
    },
    {
        'code': 'association_master',
        'title': 'Мастер ассоциаций',
        'description': 'Оставь 10 ассоциаций в 3D-игре',
        'icon': '🧩',
        'order': 51,
        'check': lambda user: GameAssociation.objects.filter(user=user).count() >= 10,
    },
    {
        'code': 'perfect_test',
        'title': 'Отличник',
        'description': 'Пройди тест модуля на 100%',
        'icon': '🎯',
        'order': 60,
        'check': lambda user: ModuleTestResult.objects.filter(user=user, best_score_percent=100).exists(),
    },
    {
        'code': 'commentator',
        'title': 'Голос из тумана',
        'description': 'Оставь первый комментарий к модулю',
        'icon': '💬',
        'order': 70,
        'check': lambda user: ModuleComment.objects.filter(user=user).exists(),
    },
    {
        'code': 'collector',
        'title': 'Собиратель',
        'description': 'Сохрани первый модуль в закладки',
        'icon': '🔖',
        'order': 80,
        'check': lambda user: Bookmark.objects.filter(user=user).exists(),
    },
    {
        'code': 'open_book',
        'title': 'Открытая книга',
        'description': 'Заполни профиль полностью — о себе, город и сайт',
        'icon': '📖',
        'order': 90,
        'check': lambda user: (
            (p := UserProfile.objects.filter(user=user).first()) is not None
            and bool(p.bio.strip()) and bool(p.location.strip()) and bool(p.website.strip())
        ),
    },
]

_ACHIEVEMENTS_BY_CODE = {a['code']: a for a in ACHIEVEMENTS}


def check_and_award(user):
    """Проверяет все условия для user и выдаёт ещё не полученные
    достижения. Возвращает список СВЕЖЕВЫДАННЫХ Achievement (пустой,
    если ничего нового). Безопасно вызывать на каждое релевантное
    действие — уже полученные достижения повторно не проверяются и не
    выдаются (unique_together в UserAchievement — дополнительная
    страховка от гонки при параллельных запросах)."""
    if not user or not user.is_authenticated:
        return []

    already_unlocked = set(
        UserAchievement.objects.filter(user=user).values_list('achievement__code', flat=True)
    )
    newly_unlocked = []

    for definition in ACHIEVEMENTS:
        code = definition['code']
        if code in already_unlocked:
            continue
        try:
            unlocked = definition['check'](user)
        except Exception:
            # Условие одного достижения не должно ронять действие
            # пользователя (завершение модуля, сохранение ассоциации и
            # т.п.) — пропускаем это достижение, остальные проверяются
            # как обычно.
            unlocked = False
        if not unlocked:
            continue

        achievement, _ = Achievement.objects.get_or_create(
            code=code,
            defaults={
                'title': definition['title'],
                'description': definition['description'],
                'icon': definition['icon'],
                'order': definition['order'],
            },
        )
        _, created = UserAchievement.objects.get_or_create(user=user, achievement=achievement)
        if created:
            newly_unlocked.append(achievement)

    return newly_unlocked


def sync_achievement_catalog():
    """Приводит таблицу Achievement в соответствие с ACHIEVEMENTS —
    создаёт недостающие записи и обновляет текст/иконку/порядок для уже
    существующих (по коду). Не выдаёт и не отбирает ничего у
    пользователей — только каталог самих достижений. Вызывать вручную
    (`python manage.py shell`) после правки списка ACHIEVEMENTS, если
    нужно сразу увидеть новые/обновлённые достижения в /achievements/ и
    в админке, не дожидаясь, пока их кто-то заработает."""
    for definition in ACHIEVEMENTS:
        Achievement.objects.update_or_create(
            code=definition['code'],
            defaults={
                'title': definition['title'],
                'description': definition['description'],
                'icon': definition['icon'],
                'order': definition['order'],
            },
        )
