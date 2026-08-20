import requests
from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Observation
from .forms import ObservationForm


# Главная страница с лентой наблюдений
class ObservationListView(ListView):
    model = Observation
    template_name = 'myapp/observation_list.html'
    context_object_name = 'observations'
    ordering = ['-created_at']


# Страница добавления нового наблюдения
class ObservationCreateView(CreateView):
    model = Observation
    form_class = ObservationForm
    template_name = 'myapp/observation_form.html'
    success_url = reverse_lazy('myapp:observation_list')


# --- VK АВТОРИЗАЦИЯ (VK ID SDK) ---

def vk_login(request):
    """Страница с виджетом VK ID для входа"""
    return render(request, 'myapp/vk_login.html', {
        'vk_app_id': settings.VK_APP_ID,
    })


@require_POST
def vk_callback(request):
    """Принимает access_token от JS-виджета VK ID и логинит пользователя"""
    access_token = request.POST.get('access_token')
    if not access_token:
        return JsonResponse({'error': 'no token'}, status=400)

    resp = requests.get('https://api.vk.com/method/users.get', params={
        'access_token': access_token,
        'v': '5.199',
        'fields': 'photo_200',
    })
    data = resp.json()

    if 'error' in data:
        return JsonResponse({'error': data['error']}, status=400)

    vk_user = data['response'][0]
    vk_id = vk_user['id']
    first_name = vk_user.get('first_name', '')
    last_name = vk_user.get('last_name', '')

    username = f'vk_{vk_id}'
    user, created = User.objects.get_or_create(username=username, defaults={
        'first_name': first_name,
        'last_name': last_name,
    })

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'success': True, 'redirect': '/'})