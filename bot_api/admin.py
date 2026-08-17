from django.contrib import admin
from .models import User, Exercise, Result

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['vk_id', 'first_name', 'last_name', 'registered_at']
    search_fields = ['vk_id', 'first_name', 'last_name']
    list_filter = ['registered_at']

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'order']
    list_filter = ['type']
    ordering = ['order']

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise', 'completed_at', 'is_approved']
    list_filter = ['is_approved', 'completed_at']
    search_fields = ['user__vk_id', 'user__first_name']