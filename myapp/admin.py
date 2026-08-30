from django.contrib import admin
from .models import Module, UserCourseProgress, ModuleComment


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'is_published', 'order', 'duration')
    list_editable = ('is_published', 'order')
    search_fields = ('title', 'subtitle', 'description')
    ordering = ('number',)


@admin.register(UserCourseProgress)
class UserCourseProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_module', 'started_at', 'completed_at')
    search_fields = ('user__username',)


@admin.register(ModuleComment)
class ModuleCommentAdmin(admin.ModelAdmin):
    list_display = ('module', 'user', 'created_at')
    search_fields = ('text', 'user__username')
