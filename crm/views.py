import calendar
import logging
import re
from collections import Counter
from datetime import timedelta
from django.contrib.auth.models import User as AuthUser
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from bot_api.models import User, Result, Review, Post, Channel, PostChannelStatus
from myapp.models import UserCourseProgress
from crm.ai_split import split_posts_with_ai, MANUAL_SPLIT_PROMPT_TEMPLATE
from crm.publish_logic import publish_channel_statuses

logger = logging.getLogger(__name__)

SPLIT_METHOD_LABELS = {
    'weekly': '📆 по дням недели',
    'separator': '➖ по разделителю ---',
    'ai': '🤖 с помощью ИИ',
    'single': '⚠️ не распознано — добавится одним постом',
}

MONTH_NAMES_RU = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]


@staff_member_required
def client_list(request):
    clients_qs = User.objects.all().order_by('-registered_at')
    paginator = Paginator(clients_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'crm/client_list.html', {
        'clients': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
    })


@staff_member_required
def client_detail(request, user_id):
    client = get_object_or_404(User, id=user_id)
    results = Result.objects.filter(user=client).order_by('-completed_at')
    reviews = Review.objects.filter(user=client).order_by('-created_at')
    course_progress = None
    site_user = None
    try:
        # Клиент психолога (bot_api.User, найден по vk_id) и пользователь
        # сайта (auth.User) — разные модели. Связь между ними — по
        # схеме имени, которую задаёт вход через VK ID
        # (myapp/vk_id_auth.py): username = f"vk_{vk_user_id}". Раньше тут
        # был `UserCourseProgress.objects.filter(user__vk_id=client.vk_id)`,
        # что всегда падало с FieldError (у auth.User нет поля vk_id) и
        # тихо проглатывалось.
        site_user = AuthUser.objects.filter(username=f"vk_{client.vk_id}").first()
        if site_user:
            course_progress = UserCourseProgress.objects.filter(user=site_user).first()
    except Exception:
        logger.exception("Не удалось загрузить прогресс курса для клиента vk_id=%s", client.vk_id)
    return render(request, 'crm/client_detail.html', {
        'client': client,
        'results': results,
        'reviews': reviews,
        'course_progress': course_progress,
        'site_user': site_user,
    })


@staff_member_required
def review_list(request):
    reviews_qs = Review.objects.exclude(status='closed').order_by('-created_at')
    paginator = Paginator(reviews_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'crm/review_list.html', {
        'reviews': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
    })


@staff_member_required
def review_detail(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'comment':
            text = request.POST.get('comment', '').strip()
            if text:
                review.comments.append({
                    'text': text,
                    'is_admin': True,
                    'created_at': timezone.now().isoformat()
                })
                review.status = 'in_review'
                review.save()
        elif action == 'close':
            review.status = 'closed'
            review.save()
            return redirect('crm_review_list')
        return redirect('crm_review_detail', review_id=review.id)

    return render(request, 'crm/review_detail.html', {'review': review})


@staff_member_required
def post_list(request):
    posts = list(Post.objects.prefetch_related('channel_statuses__channel').all())
    # Сколько каналов у поста реально можно отправить прямо сейчас кнопкой
    # «Опубликовать сейчас» — 'scheduled' (ещё не пробовали) или 'failed'
    # (пробовали, но сорвалось — ручной клик осознанно повторяет и такие),
    # у активного канала. channel_statuses уже prefetch'нуты — доп. запросов нет.
    for post in posts:
        post.publishable_count = sum(
            1 for cs in post.channel_statuses.all()
            if cs.status in ('scheduled', 'failed') and cs.channel.is_active
        )
    return render(request, 'crm/post_list.html', {'posts': posts})


def _parse_publish_date(request, raw_value):
    """Разбирает значение поля publish_date (datetime-local).
    Возвращает aware datetime или None, если значение пустое/некорректное
    (в этом случае в request уже добавлено сообщение об ошибке)."""
    raw_value = (raw_value or '').strip()
    if not raw_value:
        messages.error(request, '❌ Укажите дату и время публикации')
        return None
    parsed = parse_datetime(raw_value)
    if parsed is None:
        messages.error(request, '❌ Некорректная дата публикации')
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _sync_post_channels(post, selected_channel_ids):
    """Приводит PostChannelStatus поста в соответствие с выбранными в форме
    каналами: добавляет недостающие (status='scheduled'), убирает те, что
    сняли в форме — но только пока они ещё не отправлены (status
    'scheduled'); уже опубликованные/провалившиеся записи не трогаем,
    это история, а не план. Возвращает актуальный статус поста для
    Post.status (сводка для списка в CRM)."""
    existing = {pcs.channel_id: pcs for pcs in post.channel_statuses.all()}

    for channel_id in selected_channel_ids - existing.keys():
        PostChannelStatus.objects.create(post=post, channel_id=channel_id, status='scheduled')

    for channel_id, pcs in existing.items():
        if channel_id not in selected_channel_ids and pcs.status == 'scheduled':
            pcs.delete()

    statuses = set(post.channel_statuses.values_list('status', flat=True))
    if 'published' in statuses:
        return 'published'
    if 'scheduled' in statuses:
        return 'scheduled'
    if statuses:
        return 'failed'
    return 'draft'


def _selected_channel_ids(request):
    return {int(x) for x in request.POST.getlist('channels') if x.isdigit()}


def _split_bulk_posts(raw_text):
    """Разбивает вставленный текст на отдельные посты по строке-разделителю
    '---' (строка, которая после strip() равна ровно '---'). Пустые куски
    (только пробелы/переносы между разделителями) отбрасываются."""
    lines = (raw_text or '').replace('\r\n', '\n').split('\n')
    chunks = []
    current = []
    for line in lines:
        if line.strip() == '---':
            chunks.append('\n'.join(current).strip())
            current = []
        else:
            current.append(line)
    chunks.append('\n'.join(current).strip())
    return [c for c in chunks if c]


WEEKDAY_RE = re.compile(
    r'^(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\s*:?\s*$'
)
FIELD_LABELS = ['Заголовок', 'Введение', 'Основная часть', 'Вывод', 'Призыв к действию']
FIELD_LABEL_RE = re.compile(
    r'^(Заголовок|Введение|Основная часть|Вывод|Призыв к действию)\s*:\s*(.*)$'
)
WEEK_HEADER_RE = re.compile(r'^неделя\s+\d+\.?\s*(.*)$')


def _looks_like_weekly_format(raw_text):
    """Похож ли текст на недельную заготовку (Понедельник..Воскресенье с
    полями Заголовок/Введение/Основная часть/Вывод/Призыв к действию) —
    определяем по наличию минимум двух строк-названий дней недели."""
    lines = [line.strip().lower() for line in raw_text.splitlines()]
    return sum(1 for line in lines if WEEKDAY_RE.match(line)) >= 2


def _extract_week_label(raw_text):
    """Возвращает заголовок вида «Неделя 16. Закон бумеранга и вера», если он
    есть в начале текста — только для отображения в подтверждении, в сами
    посты не попадает."""
    for line in raw_text.splitlines():
        if WEEK_HEADER_RE.match(line.strip().lower()):
            return line.strip()
    return None


def _split_weekly_posts(raw_text):
    """Разбирает недельную заготовку по дням недели и собирает из полей
    Заголовок/Введение/Основная часть/Вывод/Призыв к действию один чистовой
    текст поста на каждый день — без служебных подписей полей."""
    lines = (raw_text or '').replace('\r\n', '\n').split('\n')
    days = []
    current = None
    for line in lines:
        if WEEKDAY_RE.match(line.strip().lower()):
            if current is not None:
                days.append(current)
            current = []
        elif current is not None:
            current.append(line)
    if current is not None:
        days.append(current)

    posts = []
    for day_lines in days:
        fields = {}
        label = None
        for line in day_lines:
            m = FIELD_LABEL_RE.match(line.strip())
            if m:
                label = m.group(1)
                fields[label] = [m.group(2).strip()] if m.group(2).strip() else []
            elif label and line.strip():
                fields[label].append(line.strip())
        parts = [' '.join(fields[l]).strip() for l in FIELD_LABELS if fields.get(l)]
        text = '\n\n'.join(p for p in parts if p)
        if text:
            posts.append(text)
    return posts


def _parse_bulk_text(raw_text):
    """Выбирает формат разбора автоматически и возвращает (посты, метод).
    Порядок попыток: недельная заготовка (дни недели + подписанные поля) →
    разделитель --- → если и это не дало больше одного поста, а в .env
    настроен ANTHROPIC_API_KEY — ИИ-разбор как подстраховка для текста без
    чёткой разметки. Если ничего не сработало (в т.ч. ИИ выключен/недоступен)
    — весь текст остаётся одним постом, как и раньше, но метод помечается
    'single', чтобы предпросмотр честно предупредил об этом."""
    if _looks_like_weekly_format(raw_text):
        posts = _split_weekly_posts(raw_text)
        if posts:
            return posts, 'weekly'

    posts = _split_bulk_posts(raw_text)
    if len(posts) > 1:
        return posts, 'separator'

    ai_posts = split_posts_with_ai(raw_text)
    if ai_posts:
        return ai_posts, 'ai'

    return posts, 'single'


WEEKDAY_LABELS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']


def _weekday_label(dt):
    return WEEKDAY_LABELS_RU[timezone.localtime(dt).weekday()]


def _build_preview_items(chunks, dates):
    """Собирает список для предпросмотра — по каждому будущему посту дата,
    день недели и заголовок (первая строка, обрезанная), без создания
    записей в базе."""
    items = []
    for text, publish_date in zip(chunks, dates):
        first_line = text.splitlines()[0].strip() if text.strip() else ''
        title = first_line if len(first_line) <= 100 else first_line[:100] + '…'
        items.append({
            'date': publish_date,
            'weekday': _weekday_label(publish_date),
            'title': title,
            'text': text,
        })
    return items


def _month_progress(new_dates):
    """Для дат только что добавленных постов считает по каждому затронутому
    месяцу: сколько добавлено сейчас, сколько всего постов на этот месяц в
    базе и сколько ещё нужно добавить до нормы «пост на каждый день
    месяца»."""
    added_counts = Counter((d.year, d.month) for d in new_dates)
    progress = []
    for (year, month) in sorted(added_counts.keys()):
        days_in_month = calendar.monthrange(year, month)[1]
        total = Post.objects.filter(
            publish_date__year=year, publish_date__month=month
        ).count()
        progress.append({
            'label': f'{MONTH_NAMES_RU[month - 1]} {year}',
            'added': added_counts[(year, month)],
            'total': total,
            'target': days_in_month,
            'remaining': max(0, days_in_month - total),
        })
    return progress


@staff_member_required
def post_bulk_create(request):
    channels = Channel.objects.filter(is_active=True)
    # Общее для всех веток — шаблон-подсказка для внешней нейросети всегда
    # доступен на странице, даже если свой ИИ-ключ (ANTHROPIC_API_KEY) не
    # настроен: психолог может скопировать его в ChatGPT/Claude.ai сама,
    # дописать свой текст и вставить результат обратно в форму.
    base_context = {
        'channels': channels,
        'manual_prompt_template': MANUAL_SPLIT_PROMPT_TEMPLATE,
    }

    if request.method == 'POST':
        # 'preview' по умолчанию — если поле action почему-то не пришло,
        # безопаснее показать разбор текста, чем сразу создать посты.
        action = request.POST.get('action', 'preview')
        raw_text = request.POST.get('bulk_text', '')
        chunks, split_method = _parse_bulk_text(raw_text)
        split_method_label = SPLIT_METHOD_LABELS.get(split_method, '')
        week_label = _extract_week_label(raw_text)
        start_date = _parse_publish_date(request, request.POST.get('start_date'))
        selected_channel_ids = _selected_channel_ids(request)

        if not chunks:
            messages.error(request, '❌ Не нашлось ни одного поста в тексте — раздели их строкой ---, либо пришли заготовку по дням недели')
            return render(request, 'crm/post_bulk.html', {
                **base_context, 'bulk_text': raw_text, 'selected_channel_ids': selected_channel_ids,
            })
        if start_date is None:
            return render(request, 'crm/post_bulk.html', {
                **base_context, 'bulk_text': raw_text, 'selected_channel_ids': selected_channel_ids,
            })

        dates = [start_date + timedelta(days=i) for i in range(len(chunks))]

        if action != 'confirm':
            # Предпросмотр — ничего не создаём в базе, просто показываем,
            # что получится, чтобы можно было проверить и поправить текст
            # или дату до реального добавления.
            local_start = timezone.localtime(start_date)
            return render(request, 'crm/post_bulk.html', {
                **base_context,
                'bulk_text': raw_text,
                'selected_channel_ids': selected_channel_ids,
                'preview_items': _build_preview_items(chunks, dates),
                'preview_count': len(chunks),
                'preview_week_label': week_label,
                'preview_first_date': dates[0],
                'preview_last_date': dates[-1],
                'split_method_label': split_method_label,
                'split_method_warn': split_method == 'single',
                'prefill_date': local_start.strftime('%d.%m.%Y'),
                'prefill_time': local_start.strftime('%H:%M'),
            })

        created_dates = []
        for text, publish_date in zip(chunks, dates):
            post = Post.objects.create(text=text, publish_date=publish_date, status='draft')
            post.status = _sync_post_channels(post, selected_channel_ids)
            post.save(update_fields=['status'])
            created_dates.append(publish_date)

        success_msg = f'✅ Добавлено постов: {len(chunks)}'
        if week_label:
            success_msg += f' ({week_label})'
        if split_method_label:
            success_msg += f' · разбор: {split_method_label}'
        messages.success(request, success_msg)

        next_date = created_dates[-1] + timedelta(days=1)
        return render(request, 'crm/post_bulk.html', {
            **base_context,
            'added_count': len(chunks),
            'progress': _month_progress(created_dates),
            'first_date': created_dates[0],
            'last_date': created_dates[-1],
            'continue_date': next_date.strftime('%d.%m.%Y'),
            'continue_time': next_date.strftime('%H:%M'),
        })

    return render(request, 'crm/post_bulk.html', {
        **base_context,
        'prefill_date': request.GET.get('continue_date', ''),
        'prefill_time': request.GET.get('continue_time', ''),
    })


@staff_member_required
def post_create(request):
    channels = Channel.objects.filter(is_active=True)
    if request.method == 'POST':
        publish_date = _parse_publish_date(request, request.POST.get('publish_date'))
        if publish_date is None:
            return render(request, 'crm/post_form.html', {'post': None, 'channels': channels})

        post = Post.objects.create(
            text=request.POST.get('text', ''),
            publish_date=publish_date,
            status='draft',
        )
        post.status = _sync_post_channels(post, _selected_channel_ids(request))
        post.save(update_fields=['status'])
        return redirect('crm_post_list')
    return render(request, 'crm/post_form.html', {'post': None, 'channels': channels})


@staff_member_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    channels = Channel.objects.filter(is_active=True)
    if request.method == 'POST':
        publish_date = _parse_publish_date(request, request.POST.get('publish_date'))
        if publish_date is None:
            return render(request, 'crm/post_form.html', {'post': post, 'channels': channels})

        post.text = request.POST.get('text', '')
        post.publish_date = publish_date
        post.status = _sync_post_channels(post, _selected_channel_ids(request))
        post.save()
        return redirect('crm_post_list')
    return render(request, 'crm/post_form.html', {
        'post': post,
        'channels': channels,
        'selected_channel_ids': set(post.channel_statuses.values_list('channel_id', flat=True)),
    })


@staff_member_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('crm_post_list')
    return render(request, 'crm/post_confirm_delete.html', {'post': post})


@staff_member_required
def post_publish_now(request, post_id):
    """Ручная отправка поста прямо сейчас, по клику из списка постов —
    в отличие от cron-команды publish_due_posts, повторяет и 'failed'
    каналы тоже (это осознанное действие человека, а не автоматика)."""
    post = get_object_or_404(Post, id=post_id)
    if request.method != 'POST':
        return redirect('crm_post_list')

    items = list(
        post.channel_statuses
        .filter(status__in=['scheduled', 'failed'], channel__is_active=True)
        .select_related('post', 'channel')
    )
    if not items:
        messages.warning(request, '⚠️ У этого поста нет активных каналов, ожидающих отправки.')
        return redirect('crm_post_list')

    results = publish_channel_statuses(items)
    published = [r for r in results if r['status'] == 'published']
    failed = [r for r in results if r['status'] != 'published']

    if published and not failed:
        names = ', '.join(r['item'].channel.name for r in published)
        messages.success(request, f'✅ Опубликовано: {names}.')
    elif published and failed:
        ok_names = ', '.join(r['item'].channel.name for r in published)
        bad_names = ', '.join(f"{r['item'].channel.name} ({r['message']})" for r in failed)
        messages.warning(request, f'✅ Опубликовано: {ok_names}. ❌ Не удалось: {bad_names}.')
    else:
        bad_names = ', '.join(f"{r['item'].channel.name} ({r['message']})" for r in failed)
        messages.error(request, f'❌ Не удалось опубликовать: {bad_names}.')

    return redirect('crm_post_list')