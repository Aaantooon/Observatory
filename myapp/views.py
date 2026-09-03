import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.contrib import messages
from django.db.models import Q
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from .models import Module, UserCourseProgress, GameAssociation, UserStreak, ModuleComment, UserProfile, Bookmark, MindMapNodePosition, Achievement, UserAchievement, ModuleTestResult
from . import achievements as achievements_module
import json
import csv
import os
from datetime import date
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


@login_required
def course_index(request):
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    modules = list(Module.objects.filter(is_published=True).order_by('number'))
    # Раньше is_module_completed() и get_prev() внутри цикла делали по
    # отдельному запросу на каждый модуль (N+1). Вместо этого один раз
    # достаём id пройденных модулей и строим словарь "номер -> модуль"
    # из уже загруженного списка, дальше — просто поиск в памяти.
    completed_ids = set(progress.completed_modules.values_list('id', flat=True))
    modules_by_number = {m.number: m for m in modules}
    modules_data = []
    for module in modules:
        is_completed = module.id in completed_ids
        prev = modules_by_number.get(module.number - 1)
        is_unlocked = module.number == 1 or (prev and prev.id in completed_ids) or is_completed
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
        'total_count': len(modules),
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
def module_pdf(request, module_number):
    """Отдаёт PDF-конспект модуля — раньше ссылка на media/ вела в обход
    login_required и проверки пройденных модулей (можно было скачать,
    не пройдя курс). Та же проверка прогресса, что и в module_detail."""
    module = get_object_or_404(Module, number=module_number, is_published=True)
    if not module.pdf_file:
        raise Http404("У этого модуля нет PDF-файла")

    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    if module.number > 1:
        prev = module.get_prev()
        if prev and not progress.is_module_completed(prev):
            messages.warning(request, 'Сначала пройдите предыдущий модуль')
            return redirect('course_index')

    filename = module.pdf_file.name.rsplit('/', 1)[-1]
    return FileResponse(module.pdf_file.open('rb'), as_attachment=True, filename=filename)


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
        for achievement in achievements_module.check_and_award(request.user):
            messages.success(request, f'{achievement.icon} Новое достижение: «{achievement.title}»!')
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
        module = get_object_or_404(Module, id=module_id, is_published=True)
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
        new_achievements = achievements_module.check_and_award(request.user)
        return JsonResponse({
            'success': True,
            'progress_percent': progress.get_progress_percent(),
            'is_finished': progress.completed_at is not None,
            'streak': streak.current_streak,
            'max_streak': streak.max_streak,
            'new_achievements': [
                {'icon': a.icon, 'title': a.title, 'description': a.description}
                for a in new_achievements
            ],
            'next_module': {
                'id': progress.current_module.id if progress.current_module else None,
                'number': progress.current_module.number if progress.current_module else None,
                'title': progress.current_module.title if progress.current_module else None,
            } if progress.current_module else None
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Http404:
        # Несуществующий/неопубликованный модуль — настоящий 404, а не
        # проглоченная "внутренняя ошибка сервера".
        raise
    except Exception:
        logger.exception("Ошибка при завершении модуля курса (user=%s)", request.user.id)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


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
        module = get_object_or_404(Module, id=module_id, is_published=True)
        assoc = GameAssociation.objects.create(
            user=request.user,
            module=module,
            object_name=object_name,
            association=association
        )
        new_achievements = achievements_module.check_and_award(request.user)
        return JsonResponse({
            'success': True,
            'association': {
                'id': assoc.id,
                'object': assoc.object_name,
                'association': assoc.association,
                'created_at': assoc.created_at.isoformat()
            },
            'new_achievements': [
                {'icon': a.icon, 'title': a.title, 'description': a.description}
                for a in new_achievements
            ],
        })
    except Http404:
        # Несуществующий/неопубликованный модуль — настоящий 404, а не
        # проглоченная ошибка сохранения.
        raise
    except Exception:
        logger.exception("Ошибка при сохранении ассоциации (user=%s)", request.user.id)
        return JsonResponse({'error': 'Не удалось сохранить'}, status=400)


@login_required
def add_comment(request, module_number):
    if request.method != 'POST':
        return redirect('course_index')
    module = get_object_or_404(Module, number=module_number, is_published=True)
    text = request.POST.get('text', '').strip()
    if text:
        ModuleComment.objects.create(
            module=module,
            user=request.user,
            text=text
        )
        messages.success(request, '💬 Комментарий добавлен')
        for achievement in achievements_module.check_and_award(request.user):
            messages.success(request, f'{achievement.icon} Новое достижение: «{achievement.title}»!')
    return redirect('course_module', module_number=module_number)


@login_required
def search_course(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        progress, _ = UserCourseProgress.objects.get_or_create(
            user=request.user,
            defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
        )
        matched = Module.objects.filter(
            Q(title__icontains=query) |
            Q(subtitle__icontains=query) |
            Q(description__icontains=query) |
            Q(content__icontains=query) |
            Q(key_concepts__icontains=query)
        ).filter(is_published=True)
        # Та же логика разблокировки, что и в module_detail: доступ закрыт,
        # только если у модуля есть предыдущий и он ещё не пройден.
        def is_unlocked(module):
            if module.number <= 1:
                return True
            prev = module.get_prev()
            return not (prev and not progress.is_module_completed(prev))

        results = [module for module in matched if is_unlocked(module)]
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
        # Поля с max_length режем до предела модели прямо тут — без этого
        # Postgres кидает необработанный DataError (500) на слишком длинном
        # значении. location/telegram — обычные CharField, поэтому обрезка
        # достаточна. website — URLField: значение сначала обрезаем по длине,
        # а затем, если оно не похоже на настоящий URL, просто не сохраняем
        # и показываем понятную ошибку вместо того, чтобы упасть или молча
        # сохранить мусор.
        location_max = UserProfile._meta.get_field('location').max_length
        telegram_max = UserProfile._meta.get_field('telegram').max_length
        website_max = UserProfile._meta.get_field('website').max_length

        profile.bio = request.POST.get('bio', '')
        profile.location = request.POST.get('location', '')[:location_max]
        profile.telegram = request.POST.get('telegram', '')[:telegram_max]

        website = request.POST.get('website', '').strip()[:website_max]
        if website:
            validate_url = URLValidator()
            try:
                validate_url(website)
                profile.website = website
            except ValidationError:
                messages.error(request, '❌ Некорректный адрес сайта — поле "Сайт" не сохранено')
                profile.website = ''
        else:
            profile.website = ''

        profile.notifications_enabled = request.POST.get('notifications') == 'on'
        
        if request.FILES.get('avatar'):
            avatar_file = request.FILES['avatar']
            max_avatar_size = 5 * 1024 * 1024  # 5 МБ
            if avatar_file.size > max_avatar_size:
                messages.error(request, '❌ Файл слишком большой (максимум 5 МБ)')
                return render(request, 'edit_profile.html', {'profile': profile})
            content_type = (avatar_file.content_type or '').lower()
            # content_type присылает клиент — ему нельзя доверять напрямую (легко подделать),
            # поэтому дальше ещё проверяем реальное содержимое файла через Pillow.
            # SVG отдельно запрещаем явно: это не растровый формат (Pillow его не откроет
            # и просто отбросит ниже), но явный запрет — понятнее как сообщение об ошибке,
            # и на всякий случай подчёркивает, что SVG может содержать исполняемый <script>.
            if not content_type.startswith('image/') or content_type == 'image/svg+xml':
                messages.error(request, '❌ Аватар должен быть изображением (JPG, PNG, WEBP)')
                return render(request, 'edit_profile.html', {'profile': profile})
            try:
                avatar_file.seek(0)
                Image.open(avatar_file).verify()
                avatar_file.seek(0)
            except (UnidentifiedImageError, OSError, ValueError):
                messages.error(request, '❌ Файл повреждён или не является настоящим изображением')
                return render(request, 'edit_profile.html', {'profile': profile})
            profile.avatar = avatar_file

        profile.save()
        messages.success(request, '✅ Профиль обновлён')
        return redirect('profile')
    
    return render(request, 'edit_profile.html', {
        'profile': profile,
    })


@login_required
def achievements_view(request):
    """Страница «Достижения» — заготовка геймификации из раздела
    'Не начато / в планах' СВОДКА_ПРОЕКТА.md. Заодно на каждый заход
    подчищает список: проверяет условия, которые могли выполниться без
    прохода через один из хуков ниже (например, если достижение
    добавили в ACHIEVEMENTS уже после того, как условие фактически
    выполнилось)."""
    new_achievements = achievements_module.check_and_award(request.user)
    unlocked_ids = set(
        UserAchievement.objects.filter(user=request.user).values_list('achievement_id', flat=True)
    )
    all_achievements = Achievement.objects.all()
    # Каталог мог ещё не наполниться (ни одно достижение никем не
    # получено — Achievement создаётся лениво в check_and_award при
    # первой выдаче) — тогда показываем определения из кода как есть,
    # все статус "заблокировано", ничего не создавая в БД молча на GET.
    if not all_achievements.exists():
        items = [
            {'icon': d['icon'], 'title': d['title'], 'description': d['description'], 'unlocked': False, 'unlocked_at': None}
            for d in achievements_module.ACHIEVEMENTS
        ]
    else:
        by_id = {ua.achievement_id: ua.unlocked_at for ua in UserAchievement.objects.filter(user=request.user)}
        items = [
            {
                'icon': a.icon, 'title': a.title, 'description': a.description,
                'unlocked': a.id in unlocked_ids, 'unlocked_at': by_id.get(a.id),
            }
            for a in all_achievements
        ]
    return render(request, 'myapp/achievements.html', {
        'items': items,
        'unlocked_count': len(unlocked_ids),
        'total_count': len(items),
        'new_achievements': new_achievements,
    })


# Порог «отпущено» для образов стресса — должен совпадать с
# RELEASED_RATE_THRESHOLD в vk_bot/exercises/stress_search.py (0-3 —
# уже не пугает). Не импортируется оттуда напрямую: vk_bot — отдельный
# процесс, обращающийся к сайту через bot_api по HTTP, а не общий модуль
# в этом Django-проекте.
STRESS_RELEASED_THRESHOLD = 3


@login_required
def statistics_view(request):
    """Страница «Статистика» — сравнение стресса и счастья по данным
    упражнений бота, было в «Не начато / в планах» СВОДКА_ПРОЕКТА.md.
    Данные упражнений хранятся в bot_api.Result (пишет их vk_bot через
    HTTP API), пользователь бота (bot_api.User) — не то же самое, что
    пользователь сайта (auth.User); связь между ними — по схеме имени,
    которую задаёт вход через VK ID (myapp/vk_id_auth.py:
    username = f"vk_{vk_id}"), та же схема уже используется в CRM
    (crm/views.py::client_detail, там наоборот — от bot_api.User к
    auth.User)."""
    from bot_api.models import User as BotUser, Result

    bot_user = None
    if request.user.username.startswith('vk_'):
        vk_id = request.user.username[len('vk_'):]
        bot_user = BotUser.objects.filter(vk_id=vk_id).first()

    stress_stats = None
    happiness_stats = None

    if bot_user:
        stress_result = Result.objects.filter(
            user=bot_user, exercise__type='stress_search'
        ).order_by('-completed_at').first()
        if stress_result and stress_result.result_data:
            items = stress_result.result_data.get('items') or []
            analysis = stress_result.result_data.get('analysis') or []
            if items:
                rates = [i.get('rate', 0) for i in items]
                released = sum(1 for r in rates if r <= STRESS_RELEASED_THRESHOLD)
                stress_stats = {
                    'total': len(items),
                    'avg_before': sum(rates) / len(rates),
                    'released': released,
                    'still_scary': len(items) - released,
                    'analyzed_count': len(analysis),
                }
                new_rates = [a['new_rate'] for a in analysis if 'new_rate' in a]
                if new_rates:
                    stress_stats['avg_after'] = sum(new_rates) / len(new_rates)

        happiness_result = Result.objects.filter(
            user=bot_user, exercise__type='happiness_list'
        ).order_by('-completed_at').first()
        if happiness_result and happiness_result.result_data:
            items = happiness_result.result_data.get('items') or []
            if items:
                scores = [i.get('score', 0) for i in items]
                happiness_stats = {
                    'total': len(items),
                    'avg_score': sum(scores) / len(scores),
                    'top': sorted(items, key=lambda x: x.get('score', 0), reverse=True)[:3],
                }

    return render(request, 'myapp/statistics.html', {
        'has_bot_account': bot_user is not None,
        'stress_stats': stress_stats,
        'happiness_stats': happiness_stats,
    })


@login_required
def submit_test_result_api(request):
    """Сохраняет результат теста модуля (module.test_questions) —
    раньше тест проверялся только в браузере (JS), результат нигде не
    оставался: не было видно ни в CRM, ни в статистике, ни как условие
    достижения. Хранит лучший результат и число попыток на пару
    (пользователь, модуль)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        module_id = data.get('module_id')
        score_percent = data.get('score_percent')
        if module_id is None or score_percent is None:
            return JsonResponse({'error': 'module_id и score_percent обязательны'}, status=400)
        score_percent = max(0, min(100, int(score_percent)))
        module = get_object_or_404(Module, id=module_id, is_published=True)

        result, created = ModuleTestResult.objects.get_or_create(
            user=request.user, module=module,
            defaults={'score_percent': score_percent, 'best_score_percent': score_percent, 'attempts': 1},
        )
        if not created:
            result.score_percent = score_percent
            result.attempts += 1
            result.best_score_percent = max(result.best_score_percent, score_percent)
            result.save()

        new_achievements = achievements_module.check_and_award(request.user)
        return JsonResponse({
            'success': True,
            'best_score_percent': result.best_score_percent,
            'attempts': result.attempts,
            'new_achievements': [
                {'icon': a.icon, 'title': a.title, 'description': a.description}
                for a in new_achievements
            ],
        })
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except Http404:
        raise
    except Exception:
        logger.exception("Ошибка при сохранении результата теста (user=%s)", request.user.id)
        return JsonResponse({'error': 'Не удалось сохранить результат'}, status=500)


@login_required
def toggle_bookmark(request, module_number):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    module = get_object_or_404(Module, number=module_number, is_published=True)
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

    # Один запрос вместо N: раньше progress.is_module_completed(module)
    # внутри цикла ниже дёргал БД на каждый модуль.
    completed_ids = set(progress.completed_modules.values_list('id', flat=True))

    # Позиции узлов, которые пользователь уже сам перетащил и сохранил —
    # если для узла есть сохранённая позиция, используем её вместо
    # автоматически рассчитанной.
    saved_positions = {
        p.node_id: {'x': p.x, 'y': p.y}
        for p in MindMapNodePosition.objects.filter(user=request.user)
    }

    def node_position(node_id, default_x, default_y):
        return saved_positions.get(node_id, {'x': default_x, 'y': default_y})

    nodes = []
    edges = []

    # Корневой узел
    nodes.append({
        'id': 'root',
        'type': 'mindmap',
        'position': node_position('root', 50, 300),
        'data': {
            'label': '🚀 Путь наблюдателя',
            'type': 'root',
            'url': '/flashlight/',
        },
    })

    # Достижения — отдельная ветка от корня, не привязана к конкретному
    # модулю (в отличие от ассоциаций ниже).
    unlocked_achievements_count = UserAchievement.objects.filter(user=request.user).count()
    nodes.append({
        'id': 'achievements',
        'type': 'mindmap',
        'position': node_position('achievements', 50, 80),
        'data': {
            'label': f'🏆 Достижения ({unlocked_achievements_count})',
            'type': 'achievements',
            'url': '/achievements/',
        },
    })
    edges.append({
        'id': 'e_root_achievements',
        'source': 'root',
        'target': 'achievements',
        'style': {'stroke': '#e2c044', 'strokeWidth': 2},
    })

    # Модули
    for i, module in enumerate(modules):
        is_completed = module.id in completed_ids
        is_current = progress.current_module and module.id == progress.current_module.id

        status = 'completed' if is_completed else ('current' if is_current else 'locked')
        color = '#4ac06a' if is_completed else ('#4a7a9a' if is_current else '#4a4a4a')

        module_node_id = f'module_{module.id}'
        nodes.append({
            'id': module_node_id,
            'type': 'mindmap',
            'position': node_position(module_node_id, 280, 150 + i * 150),
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
            default_x = 480
            default_y = 150 + i * 150 + (j - (len(module.associations) - 1) / 2) * 60
            nodes.append({
                'id': node_id,
                'type': 'mindmap',
                'position': node_position(node_id, default_x, default_y),
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

        if not node_id or x is None or y is None:
            return JsonResponse({'error': 'nodeId, x и y обязательны'}, status=400)

        MindMapNodePosition.objects.update_or_create(
            user=request.user,
            node_id=node_id,
            defaults={'x': x, 'y': y},
        )

        return JsonResponse({'success': True})
    except Exception:
        logger.exception("Ошибка при сохранении позиции узла карты (user=%s)", request.user.id)
        return JsonResponse({'error': 'Не удалось сохранить позицию'}, status=400)


# ===== МЕНТАЛЬНАЯ КАРТА: ВИТКИ =====

@login_required
def mindmap_rings(request):
    """Данные для карты-витков.

    Один модуль курса = одно кольцо («виток»). Внутри кольца — его смыслы:
    ключевые понятия (key_concepts), ассоциации (associations) и сама
    практика (ссылка на страницу модуля).

    Связи между кольцами считаются двумя способами:
      * последовательность курса (модуль N → N+1) — «дальше по курсу»;
      * общие понятия — если одно и то же слово встречается в двух модулях,
        значит автор к нему возвращается. Именно это делает карту картой,
        а не списком: повторяющаяся формула связывает разные темы.
    """
    progress, _ = UserCourseProgress.objects.get_or_create(
        user=request.user,
        defaults={'current_module': Module.objects.filter(is_published=True).order_by('number').first()}
    )
    modules = list(Module.objects.filter(is_published=True).order_by('number'))
    completed_ids = set(progress.completed_modules.values_list('id', flat=True))
    current_id = progress.current_module_id

    rings = []
    # нормализованное слово -> номера колец, где оно встречается
    word_index = {}

    def add_word(word, ring_i):
        key = word.strip().lower()
        if len(key) < 3:
            return
        word_index.setdefault(key, set()).add(ring_i)

    for ring_i, module in enumerate(modules):
        items = []
        for j, concept in enumerate(module.key_concepts or []):
            if not isinstance(concept, str) or not concept.strip():
                continue
            items.append({'id': f'c{module.id}_{j}', 'title': concept.strip(), 'type': 'concept'})
            add_word(concept, ring_i)
        for j, assoc in enumerate(module.associations or []):
            if not isinstance(assoc, str) or not assoc.strip():
                continue
            items.append({'id': f'a{module.id}_{j}', 'title': assoc.strip(), 'type': 'assoc'})
            add_word(assoc, ring_i)
        items.append({
            'id': f'p{module.id}',
            'title': 'Пройти модуль',
            'type': 'practice',
            'url': f'/course/module/{module.number}/',
        })

        if module.id in completed_ids:
            status = 'completed'
        elif current_id and module.id == current_id:
            status = 'current'
        else:
            status = 'open'

        rings.append({
            'i': ring_i,
            'id': module.id,
            'number': module.number,
            'title': module.title,
            'subtitle': module.subtitle,
            'duration': module.duration,
            'url': f'/course/module/{module.number}/',
            'status': status,
            'items': items,
        })

    links = {}
    for i in range(len(rings) - 1):
        links[(i, i + 1)] = {'seq': 1, 'shared': []}
    for word, ring_set in word_index.items():
        if len(ring_set) < 2:
            continue
        ordered = sorted(ring_set)
        for x in range(len(ordered)):
            for y in range(x + 1, len(ordered)):
                key = (ordered[x], ordered[y])
                links.setdefault(key, {'seq': 0, 'shared': []})['shared'].append(word)

    out_links = [
        {
            'a': a, 'b': b,
            'seq': data['seq'],
            'shared': sorted(data['shared'])[:6],
            'weight': data['seq'] + len(data['shared']),
        }
        for (a, b), data in sorted(links.items())
    ]

    return JsonResponse({
        'rings': rings,
        'links': out_links,
        'progress_percent': progress.get_progress_percent(),
    })


# ===== КАРТОЧКИ КУРСА =====

CARDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cards.json')

CARD_TYPES = {
    'formula': {'label': 'формула', 'color': '#e2c044'},
    'concept': {'label': 'понятие', 'color': '#5aa9e6'},
    'image': {'label': 'образ', 'color': '#6fbf73'},
    'story': {'label': 'история', 'color': '#b98ac9'},
    'practice': {'label': 'практика', 'color': '#e0785a'},
}


def _load_cards():
    """Читает карточки курса из myapp/data/cards.json.

    Карточки — авторский материал (как модули в seed_modules), а не данные
    пользователя, поэтому лежат файлом в репозитории: правятся правкой файла,
    деплоятся обычным git pull, миграций не требуют.
    """
    try:
        with open(CARDS_FILE, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        logger.exception("Не удалось прочитать карточки курса (%s)", CARDS_FILE)
        return {'cards': [], 'links': [], 'meta': {}}


def cards_view(request):
    """Страница «Карточки курса»: формулы автора с их схемами и связями."""
    data = _load_cards()
    cards = data.get('cards', [])
    links = data.get('links', [])
    by_id = {c['id']: c for c in cards}

    for card in cards:
        card['type_label'] = CARD_TYPES.get(card.get('type'), {}).get('label', card.get('type', ''))
        card['type_color'] = CARD_TYPES.get(card.get('type'), {}).get('color', '#8a9aaa')
        related = []
        for link in links:
            if link['a'] == card['id']:
                other, kind = link['b'], link['kind']
            elif link['b'] == card['id']:
                other, kind = link['a'], '← ' + link['kind']
            else:
                continue
            if other in by_id:
                related.append({'id': other, 'kind': kind, 'title': by_id[other]['title']})
        card['related'] = related

    return render(request, 'myapp/cards.html', {
        'cards': cards,
        'meta': data.get('meta', {}),
        'types': CARD_TYPES,
    })
