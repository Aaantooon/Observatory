from django.contrib import admin
from .models import User, Exercise, Result, ExerciseProgress, Notification, Review, Channel, Post, PostChannelStatus


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


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'external_id', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active']
    search_fields = ['name', 'external_id']


class PostChannelStatusInline(admin.TabularInline):
    # M2M Post.channels использует through-модель с доп. полями (status и
    # т.д.) — Django admin не даёт редактировать такое через
    # filter_horizontal/filter_vertical, поэтому каналы поста добавляются
    # и убираются только здесь, инлайном. status/published_at и т.п.
    # выставляет publish_due_posts, руками их не трогаем.
    model = PostChannelStatus
    extra = 1
    fields = ['channel', 'status', 'published_at', 'external_post_id', 'error_message']
    readonly_fields = ['status', 'published_at', 'external_post_id', 'error_message']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'publish_date', 'status', 'channel_list']
    list_filter = ['status']
    search_fields = ['text']
    exclude = ['channels']
    inlines = [PostChannelStatusInline]

    def channel_list(self, obj):
        return ", ".join(c.name for c in obj.channels.all())
    channel_list.short_description = "Каналы"