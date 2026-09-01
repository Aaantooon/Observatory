"""
sitemap.xml для поисковиков — django.contrib.sitemaps (без своих моделей
и миграций, добавлен в INSTALLED_APPS в config/settings.py).

Два раздела:
- StaticViewSitemap — статические страницы сайта;
- ModuleSitemap — опубликованные модули курса.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Module


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'

    def items(self):
        # 'home' и 'privacy_policy' зарегистрированы в config/urls.py,
        # 'course_index' — в myapp/urls.py (требует входа, но сам URL
        # публичный — незалогиненного посетителя редиректнёт на вход).
        return ['home', 'privacy_policy', 'terms_of_service', 'course_index']

    def location(self, item):
        return reverse(item)


class ModuleSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return Module.objects.filter(is_published=True).order_by('number')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('course_module', args=[obj.number])
