from django.contrib import admin
from .models import (
    Module, UserCourseProgress, ModuleComment, MindMapNodePosition,
    GameAssociation, UserStreak, UserProfile, Achievement, UserAchievement,
    ModuleTestResult,
)


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


@admin.register(MindMapNodePosition)
class MindMapNodePositionAdmin(admin.ModelAdmin):
    list_display = ('user', 'node_id', 'x', 'y', 'updated_at')
    search_fields = ('user__username', 'node_id')


@admin.register(GameAssociation)
class GameAssociationAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'object_name', 'created_at')
    search_fields = ('object_name', 'association', 'user__username')


@admin.register(UserStreak)
class UserStreakAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'max_streak', 'last_activity')
    search_fields = ('user__username',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'notifications_enabled', 'updated_at')
    search_fields = ('user__username', 'location')


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('icon', 'title', 'code', 'order')
    ordering = ('order',)
    search_fields = ('code', 'title', 'description')


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'unlocked_at')
    search_fields = ('user__username', 'achievement__title')
    list_filter = ('achievement',)


@admin.register(ModuleTestResult)
class ModuleTestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'best_score_percent', 'attempts', 'updated_at')
    search_fields = ('user__username', 'module__title')
