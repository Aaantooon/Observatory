import logging
from django.contrib.auth.models import User as AuthUser
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from bot_api.models import User, Result, Review, Post, Channel, PostChannelStatus
from myapp.models import UserCourseProgress

logger = logging.getLogger(__name__)


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
    posts = Post.objects.prefetch_related('channel_statuses__channel').all()
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