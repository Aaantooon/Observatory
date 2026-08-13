from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Exercise, Result

# --- НАСТРОЙКИ АДМИНКИ ---
admin.site.site_header = "Путь Наблюдателя"
admin.site.site_title = "Путь Наблюдателя"
admin.site.index_title = "Панель управления"


# --- USER PROFILE ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['vk_id', 'first_name', 'last_name', 'registered_at']
    list_filter = ['registered_at']
    search_fields = ['vk_id', 'first_name', 'last_name']
    readonly_fields = ['registered_at']


# --- EXERCISE ---
@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['title', 'description']
    ordering = ['order']


# --- RESULT ---
@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['user_profile', 'exercise', 'result_data', 'is_approved', 'completed_at']
    list_filter = ['is_approved', 'completed_at', 'exercise']
    search_fields = ['user_profile__vk_id', 'user_profile__first_name', 'user_profile__last_name']
    readonly_fields = ['completed_at']
    ordering = ['-completed_at']


# --- USERS ---
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff']


if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# --- TOKENS ---
try:
    from rest_framework.authtoken.models import Token
    from rest_framework.authtoken.admin import TokenAdmin


    class CustomTokenAdmin(TokenAdmin):
        list_display = ['user', 'created']


    if admin.site.is_registered(Token):
        admin.site.unregister(Token)
    admin.site.register(Token, CustomTokenAdmin)
except:
    pass