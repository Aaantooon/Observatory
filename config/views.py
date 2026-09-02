from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from myapp.models import Module, UserCourseProgress, UserStreak, Achievement, UserAchievement
from myapp import achievements as achievements_module

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

def terms_of_service_view(request):
    return render(request, 'terms_of_service.html', {
        'title': 'Пользовательское соглашение — Путь наблюдателя'
    })

def faq_view(request):
    return render(request, 'faq.html', {
        'title': 'Вопросы и ответы — Путь наблюдателя'
    })

def robots_txt(request):
    # Разрешаем всё, кроме служебных разделов (админка, CRM психолога, API).
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /crm/',
        'Disallow: /api/',
        '',
        'Sitemap: https://putnabludatel.ru/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')

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

    # Раньше здесь была отдельная, захардкоженная мини-версия достижений
    # (только по streak/completed_count, 5 фиксированных пунктов) — она
    # никак не была связана с настоящей системой достижений
    # (myapp/achievements.py, страница /achievements/) и показывала бы
    # другую картину, чем она. Теперь профиль берёт те же самые реальные
    # достижения, просто показывает последние несколько плюс ссылку на
    # полный список.
    achievements_module.check_and_award(request.user)
    unlocked = list(
        UserAchievement.objects.filter(user=request.user).select_related('achievement').order_by('-unlocked_at')
    )

    return render(request, 'profile.html', {
        'progress_percent': progress.get_progress_percent(),
        'completed_count': progress.completed_modules.count(),
        'total_count': Module.objects.filter(is_published=True).count(),
        'streak': streak.current_streak,
        'max_streak': streak.max_streak,
        'recent_achievements': unlocked[:6],
        'unlocked_achievements_count': len(unlocked),
        'total_achievements_count': Achievement.objects.count() or len(achievements_module.ACHIEVEMENTS),
    })