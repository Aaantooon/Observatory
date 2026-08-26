from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from myapp.models import Module, UserCourseProgress, UserStreak

def home(request):
    context = {
        'title': 'Главная — Путь наблюдателя',
        'subtitle': 'Фонарь рассеивает туман: шаг за шагом мы видим путь'
    }
    
    if request.user.is_authenticated:
        progress, _ = UserCourseProgress.objects.get_or_create(
            user=request.user,
            defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
        )
        streak, _ = UserStreak.objects.get_or_create(user=request.user)
        context.update({
            'progress_percent': progress.get_progress_percent(),
            'completed_count': progress.completed_modules.count(),
            'total_count': Module.objects.filter(is_published=True).count(),
            'streak': streak.current_streak,
        })
    
    return render(request, 'home.html', context)

def about(request):
    return render(request, 'about.html', {
        'title': 'О проекте — Путь наблюдателя'
    })

def map_reactflow_view(request):
    """Страница с ментальной картой (React Flow)"""
    return render(request, 'map_reactflow.html', {
        'title': 'Ментальная карта — Путь наблюдателя'
    })

def observer_view(request):
    return render(request, 'observer_map.html')

def put_view(request):
    return render(request, 'put.html')

def flashlight_view(request):
    return render(request, 'flashlight.html', {
        'title': 'Фонарик — Путь наблюдателя'
    })

@login_required
def profile_view(request):
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    
    return render(request, 'profile.html', {
        'progress_percent': progress.get_progress_percent(),
        'completed_count': progress.completed_modules.count(),
        'total_count': Module.objects.filter(is_published=True).count(),
        'streak': streak.current_streak,
        'max_streak': streak.max_streak,
    })