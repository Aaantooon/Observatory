import logging
from django.contrib.auth.models import User as AuthUser
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from bot_api.models import User, Result, Review, Post
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
    posts = Post.objects.all()
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


@staff_member_required
def post_create(request):
    if request.method == 'POST':
        publish_date = _parse_publish_date(request, request.POST.get('publish_date'))
        if publish_date is None:
            return render(request, 'crm/post_form.html', {
                'platform_choices': Post.PLATFORM_CHOICES,
                'status_choices': Post.STATUS_CHOICES,
                'post': None,
            })
        Post.objects.create(
            platform=request.POST.get('platform'),
            text=request.POST.get('text'),
            publish_date=publish_date,
            status=request.POST.get('status', 'draft'),
        )
        return redirect('crm_post_list')
    return render(request, 'crm/post_form.html', {'platform_choices': Post.PLATFORM_CHOICES, 'status_choices': Post.STATUS_CHOICES})


@staff_member_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        publish_date = _parse_publish_date(request, request.POST.get('publish_date'))
        if publish_date is None:
            return render(request, 'crm/post_form.html', {
                'post': post,
                'platform_choices': Post.PLATFORM_CHOICES,
                'status_choices': Post.STATUS_CHOICES,
            })
        post.platform = request.POST.get('platform')
        post.text = request.POST.get('text')
        post.publish_date = publish_date
        post.status = request.POST.get('status', post.status)
        post.save()
        return redirect('crm_post_list')
    return render(request, 'crm/post_form.html', {
        'post': post,
        'platform_choices': Post.PLATFORM_CHOICES,
        'status_choices': Post.STATUS_CHOICES,
    })


@staff_member_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('crm_post_list')
    return render(request, 'crm/post_confirm_delete.html', {'post': post})