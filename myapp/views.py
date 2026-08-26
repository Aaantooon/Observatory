from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Count, Q
from django.db import models
from .models import Observation, Module, UserCourseProgress, GameAssociation, UserStreak, ModuleComment, UserProfile
import json
import csv
from datetime import date


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
    
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    
    return render(request, 'myapp/course/index.html', {
        'modules': modules_data,
        'progress_percent': progress.get_progress_percent(),
        'completed_count': progress.completed_modules.count(),
        'total_count': modules.count(),
        'streak': streak.current_streak,
        'max_streak': streak.max_streak,
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
    comments = module.comments.all() if module.allow_comments else []
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    return render(request, 'myapp/course/module.html', {
        'module': module,
        'is_completed': is_completed,
        'next_module': module.get_next(),
        'prev_module': module.get_prev(),
        'associations': associations,
        'comments': comments,
        'streak': streak.current_streak,
        'profile': profile,
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
        streak, _ = UserStreak.objects.get_or_create(user=request.user)
        streak.update_streak()
        messages.success(request, f'🎉 Модуль "{module.title}" успешно завершён!')
    return redirect('course_module', module_number=module_number)


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
        streak, _ = UserStreak.objects.get_or_create(user=request.user)
        streak.update_streak()
        return JsonResponse({
            'success': True,
            'progress_percent': progress.get_progress_percent(),
            'is_finished': progress.completed_at is not None,
            'streak': streak.current_streak,
            'max_streak': streak.max_streak,
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


@login_required
def add_comment(request, module_number):
    if request.method != 'POST':
        return redirect('course_index')
    module = get_object_or_404(Module, number=module_number)
    text = request.POST.get('text', '').strip()
    if text:
        ModuleComment.objects.create(
            module=module,
            user=request.user,
            text=text
        )
        messages.success(request, '💬 Комментарий добавлен')
    return redirect('course_module', module_number=module_number)


def search_course(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        results = Module.objects.filter(
            Q(title__icontains=query) |
            Q(subtitle__icontains=query) |
            Q(description__icontains=query) |
            Q(content__icontains=query) |
            Q(key_concepts__icontains=query)
        ).filter(is_published=True)
    return render(request, 'search_results.html', {
        'query': query,
        'results': results,
    })


@login_required
def export_progress(request):
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    modules = Module.objects.filter(is_published=True).order_by('number')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="progress_{request.user.username}_{date.today()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Модуль', 'Название', 'Статус', 'Ассоциации'])
    
    for module in modules:
        status = '✅ Пройдено' if progress.is_module_completed(module) else '⏳ Не пройдено'
        associations = ', '.join(module.associations) if module.associations else '-'
        writer.writerow([module.number, module.title, status, associations])
    
    writer.writerow([])
    writer.writerow(['Итого', f'{progress.completed_modules.count()}/{modules.count()}', f'{progress.get_progress_percent()}%', ''])
    
    return response


@login_required
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '')
        profile.location = request.POST.get('location', '')
        profile.website = request.POST.get('website', '')
        profile.telegram = request.POST.get('telegram', '')
        profile.notifications_enabled = request.POST.get('notifications') == 'on'
        
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        messages.success(request, '✅ Профиль обновлён')
        return redirect('profile')
    
    return render(request, 'edit_profile.html', {
        'profile': profile,
    })


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'module']
    
    def __str__(self):
        return f"{self.user.username} → {self.module.title}"


@login_required
def toggle_bookmark(request, module_number):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    module = get_object_or_404(Module, number=module_number)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, module=module)
    if not created:
        bookmark.delete()
        return JsonResponse({'bookmarked': False})
    return JsonResponse({'bookmarked': True})


# ===== МЕНТАЛЬНАЯ КАРТА (React Flow) =====

@login_required
def mindmap_data(request):
    """Возвращает данные для ментальной карты"""
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    modules = Module.objects.filter(is_published=True).order_by('number')
    
    nodes = []
    edges = []
    
    # Корневой узел
    nodes.append({
        'id': 'root',
        'type': 'mindmap',
        'position': {'x': 50, 'y': 300},
        'data': {
            'label': '🚀 Путь наблюдателя',
            'type': 'root',
            'url': '/flashlight/',
        },
    })
    
    # Модули
    for i, module in enumerate(modules):
        is_completed = progress.is_module_completed(module)
        is_current = progress.current_module and module.id == progress.current_module.id
        
        status = 'completed' if is_completed else ('current' if is_current else 'locked')
        color = '#4ac06a' if is_completed else ('#4a7a9a' if is_current else '#4a4a4a')
        
        nodes.append({
            'id': f'module_{module.id}',
            'type': 'mindmap',
            'position': {'x': 280, 'y': 150 + i * 150},
            'data': {
                'label': f"{'✅' if is_completed else '📖'} {module.title}",
                'status': status,
                'url': f'/course/module/{module.number}/',
                'game_url': '/3d/',
                'color': color,
            },
        })
        
        # Связь от корня
        edges.append({
            'id': f'e_root_{module.id}',
            'source': 'root',
            'target': f'module_{module.id}',
            'style': {'stroke': '#2a3a4a', 'strokeWidth': 2},
        })
        
        # Ассоциации как дочерние узлы
        for j, assoc in enumerate(module.associations):
            node_id = f'assoc_{module.id}_{j}'
            nodes.append({
                'id': node_id,
                'type': 'mindmap',
                'position': {
                    'x': 480,
                    'y': 150 + i * 150 + (j - (len(module.associations) - 1) / 2) * 60
                },
                'data': {
                    'label': f'🔗 {assoc}',
                    'type': 'association',
                },
            })
            edges.append({
                'id': f'e_{module.id}_{j}',
                'source': f'module_{module.id}',
                'target': node_id,
                'style': {'stroke': '#2a3a4a', 'strokeWidth': 1.5},
            })
    
    return JsonResponse({'nodes': nodes, 'edges': edges})


@login_required
def mindmap_save_position(request):
    """Сохраняет позицию узла"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        node_id = data.get('nodeId')
        x = data.get('x')
        y = data.get('y')
        
        # TODO: Сохранять позиции в базу данных
        # Например: UserMindMapNodePosition.objects.update_or_create(...)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)