import requests
from django.core.files.base import ContentFile
from django.contrib.auth.models import User

try:
    from myapp.models import UserProfile
except ImportError:
    UserProfile = None


def save_vk_avatar(backend, user, response, *args, **kwargs):
    if backend.name == 'vk':
        photo_url = response.get('photo_max_orig')
        if photo_url and UserProfile:
            try:
                response_img = requests.get(photo_url, timeout=5)
                if response_img.status_code == 200:
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    profile.avatar.save(
                        f'vk_avatar_{user.id}.jpg',
                        ContentFile(response_img.content),
                        save=True
                    )
            except Exception:
                pass