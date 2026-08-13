from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Observation

@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    # Настройки списка
    list_display = ('title', 'location', 'created_at', 'go_to_site_button')
    search_fields = ('title', 'description')
    list_filter = ('created_at',)

    # ДОБАВЛЯЕМ КНОПКУ В СПИСОК (в каждую строку таблицы)
    def go_to_site_button(self, obj):
        return format_html(
            '<a class="button" href="{}" style="background: #e2c044; color: #16213e; padding: 5px 12px; border-radius: 5px; text-decoration: none; font-weight: bold;">✏️ Создать</a>',
            reverse('myapp:observation_add')
        )
    go_to_site_button.short_description = 'Действие'

    # ДОБАВЛЯЕМ КНОПКУ НАВЕРХУ (рядом с "Добавить Observation")
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Передаём ссылку в контекст
        extra_context['add_button_url'] = reverse('myapp:observation_add')
        return super().changelist_view(request, extra_context=extra_context)