import requests
from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.conf import settings

from .models import Observation
from .forms import ObservationForm


# Главная страница с лентой наблюдений
class ObservationListView(ListView):
    model = Observation
    template_name = 'myapp/observation_list.html'
    context_object_name = 'observations'
    ordering = ['-created_at']  # Сортируем от новых к старым


# Страница добавления нового наблюдения
class ObservationCreateView(CreateView):
    model = Observation
    form_class = ObservationForm
    template_name = 'myapp/observation_form.html'
    success_url = reverse_lazy('myapp:observation_list')  # После добавления вернет в ленту


# --- VK АВТОРИЗАЦИЯ ---

def vk_login(request):
    """Кнопка 'Войти через VK' ведёт сюда — редиректим на VK"""
    vk_auth_url = (
        "https://oauth.vk.com/authorize"
        f"?client_id={settings.VK_CLIENT_ID}"
        f"&redirect_uri={settings.VK_REDIRECT_URI}"
        "&display=page"
        "&scope=email"
        "&response_type=code"
        "&v=5.199"
    )
    return redirect(vk_auth_url)


def vk_callback(request):
    """VK возвращает сюда с кодом после подтверждения доступа"""
    code = request.GET.get('code')
    if not code:
        return redirect('myapp:observation_list')  # пользователь отказал в доступе

    # Обмениваем код на access_token
    token_response = requests.get(
        "https://oauth.vk.com/access_token",
        params={
            "client_id": settings.VK_CLIENT_ID,
            "client_secret": settings.VK_CLIENT_SECRET,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "code": code,
        }
    ).json()

    if "error" in token_response:
        return redirect('myapp:observation_list')

    vk_user_id = token_response.get("user_id")
    access_token = token_response.get("access_token")
    email = token_response.get("email")  # может отсутствовать

    # Получаем данные профиля (имя, фамилию)
    user_info = requests.get(
        "https://api.vk.com/method/users.get",
        params={
            "user_ids": vk_user_id,
            "access_token": access_token,
            "v": "5.199",
        }
    ).json()

    profile = user_info["response"][0]
    first_name = profile.get("first_name", "")
    last_name = profile.get("last_name", "")

    # Создаём или находим пользователя Django по vk_user_id
    username = f"vk_{vk_user_id}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
        }
    )

    login(request, user)  # логиним пользователя в Django-сессию
    return redirect('myapp:observation_list')