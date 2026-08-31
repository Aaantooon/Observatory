import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from bot_api.models import User, Result, Review, Post
from myapp.models import UserCourseProgress

logger = logging.getLogger(__name__)


@staff_member_required
def client_list(request):
    clients = User.objects.all().order_by('-registered_at')
    return render(request, 'crm/client_list.html', {'clients': clients})


@staff_member_required
def client_detail(request, user_id):
    client = get_object_or_404(User, id=user_id)
    results = Result.objects.filter(user=client).order_by('-completed_at')
    reviews = Review.objects.filter(user=client).order_by('-created_at')
    course_progress = None
    try:
        course_progress = UserCourseProgress.objects.filter(user__vk_id=client.vk_id).first()
    except Exception:
        logger.exception("Не удалось загрузить прогресс курса для клиента vk_id=%s", client.vk_id)
    return render(request, 'crm/client_detail.html', {
        'client': client,
        'results': results,
        'reviews': reviews,
        'course_progress': course_progress,
    })


@staff_member_required
def review_list(request):
    reviews = Review.objects.exclude(status='closed').order_by('-created_at')
    return render(request, 'crm/review_list.html', {'reviews': reviews})


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


@staff_member_required
def post_create(request):
    if request.method == 'POST':
        Post.objects.create(
            platform=request.POST.get('platform'),
            text=request.POST.get('text'),
            publish_date=request.POST.get('publish_date'),
            status=request.POST.get('status', 'draft'),
        )
        return redirect('crm_post_list')
    return render(request, 'crm/post_form.html', {'platform_choices': Post.PLATFORM_CHOICES, 'status_choices': Post.STATUS_CHOICES})


@staff_member_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        post.platform = request.POST.get('platform')
        post.text = request.POST.get('text')
        post.publish_date = request.POST.get('publish_date')
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