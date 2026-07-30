"""
views.py — здесь мы обрабатываем запросы пользователей.
Каждая функция — это страница сайта.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from .models import *
from .constants import USER_LEVEL_NAMES, USER_LEVEL_DESCRIPTIONS, UserLevel


# ============================================================
# 1. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_user_level(user):
    """Получить уровень пользователя."""
    if user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=user)
        return profile.level
    return None


def get_user_profile(user):
    """Получить профиль пользователя."""
    if user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=user)
        return profile
    return None


# ============================================================
# 2. РЕГИСТРАЦИЯ
# ============================================================

def signup(request):
    """
    Страница регистрации нового пользователя.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Создаём профиль для пользователя
            Profile.objects.create(
                user=user,
                level=UserLevel.BEGINNER.value  # По умолчанию новичок
            )

            # Автоматически входим после регистрации
            login(request, user)
            messages.success(request, f"Добро пожаловать, {user.username}! Вы зарегистрированы.")
            return redirect('main:home')
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = UserCreationForm()

    return render(request, 'main/signup.html', {'form': form})


# ============================================================
# 3. СТРАНИЦЫ САЙТА
# ============================================================

def home(request):
    """
    Главная страница.
    Показывает три луча фонарика: новичок, опытный, наблюдатель.
    """
    context = {
        'level_names': USER_LEVEL_NAMES,
        'level_descriptions': USER_LEVEL_DESCRIPTIONS,
        'courses': Course.objects.filter(is_published=True)[:6],
        'recent_maps': ObservationMap.objects.order_by('-created_at')[:5],
        'recent_threads': ForumThread.objects.filter(is_closed=False).order_by('-created_at')[:5],
    }
    return render(request, 'main/home.html', context)


def community(request):
    """Страница сообщества."""
    context = {
        'threads': ForumThread.objects.filter(is_closed=False).order_by('-created_at')[:20],
        'chat_messages': ChatMessage.objects.filter(is_public=True).order_by('-created_at')[:30],
        'total_users': User.objects.count(),
        'total_maps': ObservationMap.objects.count(),
        'total_threads': ForumThread.objects.count(),
    }
    return render(request, 'main/community.html', context)


def course_list(request):
    """Список курсов с фильтрацией по уровню."""
    level = request.GET.get('level')
    courses = Course.objects.filter(is_published=True)

    if level:
        courses = courses.filter(level=level)

    context = {
        'courses': courses,
        'current_level': level,
        'level_names': USER_LEVEL_NAMES,
    }
    return render(request, 'main/course_list.html', context)


def course_detail(request, slug):
    """Страница одного курса."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    context = {'course': course}
    return render(request, 'main/course_detail.html', context)


def trainings(request):
    """Страница тренингов."""
    context = {
        'groups': SeminarGroup.objects.filter(is_active=True),
    }
    return render(request, 'main/trainings.html', context)


def psychodiving(request):
    """Страница психодайвинга."""
    return render(request, 'main/psychodiving.html')


def film_club(request):
    """Страница киноклуба."""
    return render(request, 'main/film_club.html')


def contact(request):
    """Страница контактов."""
    return render(request, 'main/contact.html')


# ============================================================
# 4. ЛИЧНЫЙ КАБИНЕТ (ДАШБОРД)
# ============================================================

@login_required
def dashboard(request):
    """Личный кабинет пользователя."""
    user = request.user
    profile = get_user_profile(user)

    participations = Participation.objects.filter(user=user).select_related('group')
    maps = ObservationMap.objects.filter(author=user).order_by('-created_at')
    submissions = SeminarSubmission.objects.filter(user=user).order_by('-created_at')[:10]

    context = {
        'profile': profile,
        'participations': participations,
        'maps': maps,
        'submissions': submissions,
    }
    return render(request, 'main/dashboard.html', context)


# ============================================================
# 5. МЕНТАЛЬНЫЕ КАРТЫ
# ============================================================

@login_required
def map_view(request):
    """Страница со списком ментальных карт."""
    level = request.GET.get('level')
    maps = ObservationMap.objects.all()

    if level:
        maps = maps.filter(level=level)

    context = {
        'maps': maps,
        'level_names': USER_LEVEL_NAMES,
    }
    return render(request, 'main/map_list.html', context)


@login_required
def map_detail(request, pk):
    """Страница одной ментальной карты."""
    map_obj = get_object_or_404(ObservationMap, pk=pk)

    if map_obj.author != request.user and not request.user.is_staff:
        messages.error(request, "У вас нет доступа к этой карте.")
        return redirect('main:map_view')

    nodes = map_obj.nodes.all()

    context = {
        'map': map_obj,
        'nodes': nodes,
        'level_names': USER_LEVEL_NAMES,
    }
    return render(request, 'main/map_detail.html', context)


@login_required
def map_create(request):
    """Создание новой ментальной карты."""
    if request.method == 'POST':
        title = request.POST.get('title')
        central_node = request.POST.get('central_node')
        level = request.POST.get('level', UserLevel.BEGINNER.value)

        if title and central_node:
            map_obj = ObservationMap.objects.create(
                author=request.user,
                title=title,
                central_node=central_node,
                level=level
            )
            messages.success(request, f"Карта '{title}' создана!")
            return redirect('main:map_detail', pk=map_obj.pk)
        else:
            messages.error(request, "Заполните все обязательные поля.")

    context = {
        'level_names': USER_LEVEL_NAMES,
    }
    return render(request, 'main/map_create.html', context)


# ============================================================
# 6. ФОРУМ
# ============================================================

def forum_index(request):
    """Главная страница форума."""
    categories = ForumCategory.objects.all()
    threads = ForumThread.objects.filter(is_closed=False).order_by('-is_pinned', '-created_at')

    context = {
        'categories': categories,
        'threads': threads,
    }
    return render(request, 'main/forum_index.html', context)


def forum_thread(request, pk):
    """Страница темы форума."""
    thread = get_object_or_404(ForumThread, pk=pk)
    posts = thread.posts.all()

    context = {
        'thread': thread,
        'posts': posts,
    }
    return render(request, 'main/forum_thread.html', context)


@login_required
def forum_create(request):
    """Создание новой темы на форуме."""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        category_id = request.POST.get('category')

        if title and content and category_id:
            category = get_object_or_404(ForumCategory, pk=category_id)
            thread = ForumThread.objects.create(
                title=title,
                content=content,
                author=request.user,
                category=category
            )
            messages.success(request, f"Тема '{title}' создана!")
            return redirect('main:forum_thread', pk=thread.pk)
        else:
            messages.error(request, "Заполните все поля.")

    context = {
        'categories': ForumCategory.objects.all(),
    }
    return render(request, 'main/forum_create.html', context)


# ============================================================
# 7. СЕМИНАРСКИЕ ГРУППЫ
# ============================================================

def group_list(request):
    """Список семинарских групп."""
    groups = SeminarGroup.objects.filter(is_active=True)

    context = {
        'groups': groups,
    }
    return render(request, 'main/group_list.html', context)


def group_detail(request, pk):
    """Страница одной группы."""
    group = get_object_or_404(SeminarGroup, pk=pk)
    seminars = group.seminars.all().order_by('number')

    is_participant = False
    if request.user.is_authenticated:
        is_participant = Participation.objects.filter(user=request.user, group=group).exists()

    context = {
        'group': group,
        'seminars': seminars,
        'is_participant': is_participant,
    }
    return render(request, 'main/group_detail.html', context)


@login_required
def group_join(request, pk):
    """Запись в семинарскую группу."""
    group = get_object_or_404(SeminarGroup, pk=pk)

    if Participation.objects.filter(user=request.user, group=group).exists():
        messages.warning(request, "Вы уже записаны в эту группу.")
        return redirect('main:group_detail', pk=group.pk)

    if group.is_full:
        messages.warning(request, "Группа уже набрана.")
        return redirect('main:group_detail', pk=group.pk)

    Participation.objects.create(user=request.user, group=group)
    messages.success(request, f"Вы записаны в группу '{group.name}'!")

    return redirect('main:group_detail', pk=group.pk)


# ============================================================
# 8. ПРОФИЛЬ
# ============================================================

def profile(request, username):
    """Страница профиля пользователя."""
    user = get_object_or_404(User, username=username)
    profile = get_user_profile(user)

    context = {
        'profile_user': user,
        'profile': profile,
        'maps': ObservationMap.objects.filter(author=user).order_by('-created_at')[:10],
        'level_names': USER_LEVEL_NAMES,
    }
    return render(request, 'main/profile.html', context)