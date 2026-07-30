"""
context_processors.py — функции, которые добавляют переменные
во все шаблоны сайта.
"""

from .models import Profile
from .constants import USER_LEVEL_NAMES, USER_LEVEL_DESCRIPTIONS


def site_context(request):
    """
    Добавляет во все шаблоны:
    - user_level: уровень текущего пользователя
    - level_names: названия уровней
    - level_descriptions: описания уровней
    - is_authenticated: авторизован ли пользователь
    """
    context = {
        'level_names': USER_LEVEL_NAMES,
        'level_descriptions': USER_LEVEL_DESCRIPTIONS,
        'is_authenticated': request.user.is_authenticated,
    }

    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)
        context['user_level'] = profile.level
        context['user_level_name'] = USER_LEVEL_NAMES.get(profile.level, '')

    return context