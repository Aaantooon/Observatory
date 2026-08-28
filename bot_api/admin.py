from django.contrib import admin
from .models import User, Exercise, Result, ExerciseProgress, Notification, Review


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['vk_id', 'first_name', 'last_name', 'streak', 'registered_at']
    list_filter = ['streak']
    search_fields = ['vk_id', 'first_name', 'last_name']
    ordering = ['-registered_at']


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'order']
    list_filter = ['type']
    search_fields = ['title', 'description']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise', 'is_approved', 'completed_at']
    list_filter = ['is_approved', 'exercise']
    search_fields = ['user__vk_id', 'exercise__title']
    readonly_fields = ['completed_at']


@admin.register(ExerciseProgress)
class ExerciseProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise_type', 'updated_at']
    search_fields = ['user__vk_id', 'exercise_type']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise_type', 'schedule_type', 'is_active', 'last_sent']
    list_filter = ['is_active', 'schedule_type', 'exercise_type']
    search_fields = ['user__vk_id', 'exercise_type']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise_type', 'status', 'created_at']
    list_filter = ['status', 'exercise_type']
    readonly_fields = ['data', 'comments']