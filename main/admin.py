"""
admin.py — настройка панели администратора Django.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db import transaction
from django.utils import timezone
from .models import *
from .services import calculate_required_matches
from .constants import TriggerStatus


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'created_at')
    list_filter = ('level',)
    search_fields = ('user__username', 'user__email')


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1
    ordering = ['number']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'level', 'price', 'is_free', 'is_published')
    list_filter = ('category', 'level', 'is_free', 'is_published')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


class SeminarInline(admin.TabularInline):
    model = Seminar
    extra = 1
    ordering = ['number']


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    raw_id_fields = ('user',)


@admin.register(SeminarGroup)
class SeminarGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'min_participants', 'participants_count', 'is_active', 'is_full')
    list_filter = ('is_active', 'is_full', 'course')
    search_fields = ('name', 'description')
    inlines = [SeminarInline, ParticipationInline]

    def participants_count(self, obj):
        return obj.participants_count()
    participants_count.short_description = "Участников"


@admin.register(ObservationMap)
class ObservationMapAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'level', 'created_at')
    list_filter = ('level',)
    search_fields = ('title', 'author__username')


class MapNodeInline(admin.TabularInline):
    model = MapNode
    extra = 1
    ordering = ['order']


@admin.register(MapNode)
class MapNodeAdmin(admin.ModelAdmin):
    list_display = ('label', 'map', 'node_type', 'review_status', 'risk_type', 'weight')
    list_filter = ('node_type', 'review_status', 'risk_type')
    search_fields = ('label', 'content')


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}


class ForumPostInline(admin.TabularInline):
    model = ForumPost
    extra = 1
    ordering = ['created_at']


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'is_pinned', 'is_closed', 'post_count')
    list_filter = ('category', 'is_pinned', 'is_closed')
    search_fields = ('title', 'content')
    inlines = [ForumPostInline]

    def post_count(self, obj):
        return obj.post_count()
    post_count.short_description = "Сообщений"


@admin.register(SeminarSubmission)
class SeminarSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'seminar', 'is_submitted', 'review_status', 'submitted_at')
    list_filter = ('is_submitted', 'review_status')
    search_fields = ('user__username', 'seminar__title')
    raw_id_fields = ('user', 'seminar')


@admin.register(ReviewFeedback)
class ReviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ('submission', 'created_at')
    search_fields = ('submission__user__username',)


@admin.register(TriggerRule)
class TriggerRuleAdmin(admin.ModelAdmin):
    list_display = ('old_phrase', 'new_phrase', 'count', 'last_seen')
    search_fields = ('old_phrase', 'new_phrase')


@admin.register(AutoTriggerCandidate)
class AutoTriggerCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'old_phrase', 'new_phrase', 'count', 'rejection_count',
        'status_badge', 'last_rejected_at', 'expires_at'
    )
    list_filter = ('status',)
    actions = ['approve_selected', 'reject_selected']

    def status_badge(self, obj):
        colors = {
            TriggerStatus.PENDING.value: "warning",
            TriggerStatus.SUPPRESSED.value: "secondary",
            TriggerStatus.ACTIVE.value: "success",
        }
        color = colors.get(obj.status, "info")
        label = obj.get_status_display()

        tooltip_text = ""
        if obj.status == TriggerStatus.SUPPRESSED.value and obj.rejection_count:
            required = calculate_required_matches(obj.rejection_count)
            tooltip_text = f"В тихом режиме: отклонён {obj.rejection_count} раз. Нужно ещё {required} новых совпадений для возврата."

        return format_html(
            '<span class="badge bg-{}" title="{}" style="cursor:help;">{}</span>',
            color,
            tooltip_text,
            label,
        )
    status_badge.short_description = "Статус"

    @transaction.atomic
    def approve_selected(self, request, queryset):
        for candidate in queryset:
            rule, created = TriggerRule.objects.update_or_create(
                old_phrase=candidate.old_phrase,
                new_phrase=candidate.new_phrase,
                node_type=candidate.node_type,
                defaults={
                    'count': candidate.count,
                    'sample_node_ids': candidate.sample_data,
                }
            )
            candidate.status = TriggerStatus.ACTIVE.value
            candidate.save()
        self.message_user(request, f"Одобрено {queryset.count()} кандидатов")
    approve_selected.short_description = "Одобрить выбранные кандидатуры"

    @transaction.atomic
    def reject_selected(self, request, queryset):
        for candidate in queryset:
            rejected, created = RejectedTrigger.objects.get_or_create(
                old_phrase=candidate.old_phrase,
                new_phrase=candidate.new_phrase,
                node_type=candidate.node_type,
                defaults={'rejected_by': request.user}
            )
            rejected.rejection_count += 1
            rejected.rejected_by = request.user
            rejected.save()

            candidate.rejection_count += 1
            candidate.last_rejected_at = timezone.now()
            candidate.status = TriggerStatus.SUPPRESSED.value
            candidate.save()
        self.message_user(request, f"Отклонено {queryset.count()} кандидатов")
    reject_selected.short_description = "Отклонить выбранные кандидатуры"