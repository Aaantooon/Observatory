from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required  # если нужна авторизация
from .forms import SocialAccountForm, PostForm
from .models import SocialAccount, Post
from .utils.social_poster import send_telegram, send_vk
from django.utils import timezone

@login_required  # если хотите ограничить доступ
def channels_list(request):
    channels = SocialAccount.objects.all()
    if request.method == 'POST':
        form = SocialAccountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Канал добавлен!')
            return redirect('channels_list')
    else:
        form = SocialAccountForm()
    return render(request, 'myapp/channels.html', {'channels': channels, 'form': form})

@login_required
def new_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.status = 'pending'
            post.save()
            form.save_m2m()  # сохраняем ManyToMany
            # Отправляем во все выбранные каналы
            success = True
            for account in post.platforms.all():
                try:
                    if account.platform == 'telegram':
                        result = send_telegram(account.token, account.chat_id, post.text, post.image.path if post.image else None)
                    elif account.platform == 'vk':
                        result = send_vk(account.token, account.chat_id, post.text, post.image.path if post.image else None)
                    # Можно проверить результат и установить статус
                except Exception as e:
                    success = False
                    messages.error(request, f'Ошибка при отправке в {account.name}: {e}')
            post.status = 'sent' if success else 'failed'
            post.sent_at = timezone.now()
            post.save()
            if success:
                messages.success(request, 'Пост опубликован!')
            return redirect('post_history')
    else:
        form = PostForm()
    return render(request, 'myapp/new_post.html', {'form': form})

@login_required
def post_history(request):
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'myapp/history.html', {'posts': posts})