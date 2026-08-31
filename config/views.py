from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from myapp.models import Module, UserCourseProgress, UserStreak

def home(request):
    if request.GET.get('code') and request.GET.get('device_id'):
        from myapp.vk_id_auth import vk_login_callback
        return vk_login_callback(request)
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

def privacy_policy_view(request):
    return render(request, 'privacy_policy.html', {
        'title': 'Политика конфиденциальности — Путь наблюдателя'
    })

def map_reactflow_view(request):
    """Страница с ментальной картой (React Flow)"""
    return render(request, 'map_reactflow.html', {
        'title': 'Ментальная карта — Путь наблюдателя'
    })

@login_required
def observer_view(request):
    return render(request, 'observer3d/world_babylon.html')

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