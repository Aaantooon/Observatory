from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count
from .models import Observation, Module, UserCourseProgress, GameAssociation, UserStreak
from datetime import date
import json

# ===== КУРС =====

@login_required
def course_index(request):
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    modules = Module.objects.filter(is_published=True).order_by('number')
    modules_data = []
    for module in modules:
        is_completed = progress.is_module_completed(module)
        is_unlocked = module.number == 1 or (module.get_prev() and progress.is_module_completed(module.get_prev())) or is_completed
        modules_data.append({
            'module': module,
            'is_completed': is_completed,
            'is_unlocked': is_unlocked,
            'is_current': progress.current_module and module.id == progress.current_module.id
        })
    
    # Статистика
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    
    return render(request, 'myapp/course/index.html', {
        'modules': modules_data,
        'progress_percent': progress.get_progress_percent(),
        'completed_count': progress.completed_modules.count(),
        'total_count': modules.count(),
        'streak': streak.current_streak,
    })

@login_required
def module_detail(request, module_number):
    module = get_object_or_404(Module, number=module_number, is_published=True)
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    if module.number > 1:
        prev = module.get_prev()
        if prev and not progress.is_module_completed(prev):
            messages.warning(request, 'Сначала пройдите предыдущий модуль')
            return redirect('course_index')
    is_completed = progress.is_module_completed(module)
    associations = request.user.game_associations.filter(module=module)
    return render(request, 'myapp/course/module.html', {
        'module': module,
        'is_completed': is_completed,
        'next_module': module.get_next(),
        'prev_module': module.get_prev(),
        'associations': associations,
        'streak': UserStreak.objects.get_or_create(user=request.user)[0].current_streak,
    })

@login_required
def complete_module(request, module_number):
    if request.method != 'POST':
        return redirect('course_index')
    module = get_object_or_404(Module, number=module_number, is_published=True)
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    if progress.is_module_completed(module):
        messages.info(request, 'Этот модуль уже пройден')
    else:
        progress.complete_module(module)
        # Обновляем серию
        streak, _ = UserStreak.objects.get_or_create(user=request.user)
        streak.update_streak()
        messages.success(request, f'🎉 Модуль "{module.title}" успешно завершён!')
    return redirect('course_module', module_number=module_number)


# ===== API =====

@login_required
def course_progress_api(request):
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    game_state = progress.get_game_state()
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    return JsonResponse({
        'modules': game_state['modules'],
        'progress_percent': game_state['progress_percent'],
        'current_module_id': game_state['current_module_id'],
        'is_finished': game_state['is_finished'],
        'completed_module_ids': list(progress.completed_modules.values_list('id', flat=True)),
        'streak': streak.current_streak,
        'max_streak': streak.max_streak,
    })

@login_required
def complete_module_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        module_id = data.get('module_id')
        if not module_id:
            return JsonResponse({'error': 'module_id required'}, status=400)
        module = get_object_or_404(Module, id=module_id)
        progress, _ = UserCourseProgress.objects.get_or_create(
            user=request.user,
            defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
        )
        if progress.is_module_completed(module):
            return JsonResponse({'success': True, 'already_completed': True})
        if module.number > 1:
            prev = module.get_prev()
            if prev and not progress.is_module_completed(prev):
                return JsonResponse({'error': 'Предыдущий модуль не пройден'}, status=403)
        progress.complete_module(module)
        # Обновляем серию
        streak, _ = UserStreak.objects.get_or_create(user=request.user)
        streak.update_streak()
        return JsonResponse({
            'success': True,
            'progress_percent': progress.get_progress_percent(),
            'is_finished': progress.completed_at is not None,
            'streak': streak.current_streak,
            'next_module': {
                'id': progress.current_module.id if progress.current_module else None,
                'number': progress.current_module.number if progress.current_module else None,
                'title': progress.current_module.title if progress.current_module else None,
            } if progress.current_module else None
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def association_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        module_id = data.get('module_id')
        object_name = data.get('object_name', '').strip()
        association = data.get('association', '').strip()
        if not all([module_id, object_name, association]):
            return JsonResponse({'error': 'Все поля обязательны'}, status=400)
        module = get_object_or_404(Module, id=module_id)
        assoc = GameAssociation.objects.create(
            user=request.user,
            module=module,
            object_name=object_name,
            association=association
        )
        return JsonResponse({
            'success': True,
            'association': {
                'id': assoc.id,
                'object': assoc.object_name,
                'association': assoc.association,
                'created_at': assoc.created_at.isoformat()
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ===== СТАТИСТИКА ДЛЯ ГЛАВНОЙ =====

def get_user_stats(request):
    """Получить статистику пользователя для главной"""
    if not request.user.is_authenticated:
        return {
            'total_modules': 0,
            'completed': 0,
            'progress': 0,
            'streak': 0,
        }
    
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    
    return {
        'total_modules': Module.objects.filter(is_published=True).count(),
        'completed': progress.completed_modules.count(),
        'progress': progress.get_progress_percent(),
        'streak': streak.current_streak,
    }