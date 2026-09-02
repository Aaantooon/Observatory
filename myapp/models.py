from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
from dotenv import load_dotenv

load_dotenv()

# ===== МОДУЛИ КУРСА =====
class Module(models.Model):
    number = models.PositiveIntegerField(unique=True, verbose_name="Номер модуля")
    title = models.CharField(max_length=200, verbose_name="Название")
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="Подзаголовок")
    description = models.TextField(verbose_name="Описание")
    content = models.TextField(verbose_name="Содержание лекции", blank=True)
    
    position_x = models.FloatField(default=0, verbose_name="Позиция X в 3D")
    position_z = models.FloatField(default=0, verbose_name="Позиция Z в 3D")
    color = models.CharField(max_length=7, default="#6cbfff", verbose_name="Цвет в 3D")
    
    key_concepts = models.JSONField(default=list, blank=True, verbose_name="Ключевые понятия")
    associations = models.JSONField(default=list, blank=True, verbose_name="Ассоциации")
    duration = models.PositiveIntegerField(default=30, verbose_name="Длительность (мин)")
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # НОВЫЕ ПОЛЯ
    video_url = models.URLField(blank=True, verbose_name="Ссылка на видео")
    pdf_file = models.FileField(upload_to='modules/pdfs/', blank=True, null=True, verbose_name="PDF-файл")
    test_questions = models.JSONField(default=list, blank=True, verbose_name="Вопросы для теста")
    allow_comments = models.BooleanField(default=True, verbose_name="Разрешить комментарии")
    
    class Meta:
        ordering = ['number']
        verbose_name = "Модуль"
        verbose_name_plural = "Модули курса"
    
    def __str__(self):
        return f"{self.number}. {self.title}"
    
    def get_next(self):
        return Module.objects.filter(number=self.number + 1, is_published=True).first()
    
    def get_prev(self):
        return Module.objects.filter(number=self.number - 1, is_published=True).first()


# ===== ПРОГРЕСС ПОЛЬЗОВАТЕЛЯ =====
class UserCourseProgress(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='course_progress')
    current_module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='users_at')
    completed_modules = models.ManyToManyField(Module, blank=True, related_name='completed_by')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Прогресс пользователя"
        verbose_name_plural = "Прогресс пользователей"
    
    def __str__(self):
        module = self.current_module
        return f"{self.user.username} - {module.title if module else 'Завершён'}"
    
    def get_progress_percent(self):
        total = Module.objects.filter(is_published=True).count()
        if total == 0:
            return 0
        return int((self.completed_modules.count() / total) * 100)
    
    def is_module_completed(self, module):
        return self.completed_modules.filter(id=module.id).exists()
    
    def complete_module(self, module):
        if not self.is_module_completed(module):
            self.completed_modules.add(module)
            next_module = module.get_next()
            if next_module:
                self.current_module = next_module
            else:
                self.completed_at = timezone.now()
            self.save()
            return True
        return False
    
    def get_game_state(self):
        modules = Module.objects.filter(is_published=True).order_by('number')
        completed_ids = list(self.completed_modules.values_list('id', flat=True))
        result = []
        for m in modules:
            if m.id in completed_ids:
                status = 'completed'
            elif self.current_module and m.id == self.current_module.id:
                status = 'unlocked'
            elif m.number == 1:
                status = 'unlocked'
            else:
                prev = m.get_prev()
                if prev and prev.id in completed_ids:
                    status = 'unlocked'
                else:
                    status = 'locked'
            result.append({
                'id': m.id,
                'number': m.number,
                'title': m.title,
                'subtitle': m.subtitle,
                'color': m.color,
                'x': m.position_x,
                'z': m.position_z,
                'status': status,
                'associations': m.associations
            })
        return {
            'modules': result, 
            'progress_percent': self.get_progress_percent(), 
            'current_module_id': self.current_module.id if self.current_module else None, 
            'is_finished': self.completed_at is not None
        }


# ===== АССОЦИАЦИИ ИЗ ИГРЫ =====
class GameAssociation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_associations')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='game_associations')
    object_name = models.CharField(max_length=100, verbose_name="Объект")
    association = models.TextField(verbose_name="Ассоциация")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Ассоциация"
        verbose_name_plural = "Ассоциации"
    
    def __str__(self):
        return f"{self.user.username}: {self.object_name} → {self.association[:30]}"


# ===== СЕРИЯ ПОЛЬЗОВАТЕЛЯ =====
class UserStreak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0, verbose_name="Текущая серия")
    max_streak = models.IntegerField(default=0, verbose_name="Максимальная серия")
    last_activity = models.DateField(null=True, blank=True, verbose_name="Последняя активность")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Серия пользователя"
        verbose_name_plural = "Серии пользователей"
    
    def __str__(self):
        return f"{self.user.username}: {self.current_streak} дней"
    
    def update_streak(self):
        from datetime import date, timedelta
        today = date.today()
        
        if not self.last_activity:
            self.current_streak = 1
            self.max_streak = max(self.max_streak, self.current_streak)
            self.last_activity = today
            self.save()
            return True
        
        if self.last_activity == today:
            return False
        
        if self.last_activity == today - timedelta(days=1):
            self.current_streak += 1
        else:
            self.current_streak = 1
        
        self.max_streak = max(self.max_streak, self.current_streak)
        self.last_activity = today
        self.save()
        return True


# ===== КОММЕНТАРИИ К МОДУЛЯМ =====
class ModuleComment(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='module_comments')
    text = models.TextField(verbose_name="Текст комментария")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Комментарий к модулю"
        verbose_name_plural = "Комментарии к модулям"
    
    def __str__(self):
        return f"{self.user.username} — {self.module.title} ({self.created_at.strftime('%d.%m.%Y')})"


# ===== ПОЗИЦИИ УЗЛОВ МЕНТАЛЬНОЙ КАРТЫ =====
class MindMapNodePosition(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mindmap_positions')
    node_id = models.CharField(max_length=100, verbose_name="ID узла")
    x = models.FloatField()
    y = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'node_id')
        verbose_name = "Позиция узла карты"
        verbose_name_plural = "Позиции узлов карты"

    def __str__(self):
        return f"{self.user.username} — {self.node_id}"


# ===== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватарка")
    bio = models.TextField(blank=True, verbose_name="О себе")
    location = models.CharField(max_length=200, blank=True, verbose_name="Город")
    website = models.URLField(blank=True, verbose_name="Сайт")
    telegram = models.CharField(max_length=100, blank=True, verbose_name="Telegram")
    notifications_enabled = models.BooleanField(default=True, verbose_name="Уведомления")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
    
    def __str__(self):
        return f"Профиль {self.user.username}"


# ===== ЗАКЛАДКИ =====
class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'module']

    def __str__(self):
        return f"{self.user.username} → {self.module.title}"


# ===== ДОСТИЖЕНИЯ ("стать Наблюдателем") =====
# Заготовка геймификации — числилась в СВОДКА_ПРОЕКТА.md как "не начато".
# Код достижения — стабильный идентификатор из myapp/achievements.py
# (ACHIEVEMENTS ниже), а не первичный ключ — так список достижений можно
# менять/дополнять в коде, не трогая уже выданные записи в БД.
class Achievement(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Код")
    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.CharField(max_length=300, verbose_name="Описание")
    icon = models.CharField(max_length=10, default="🏆", verbose_name="Иконка (эмодзи)")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок показа")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Достижение"
        verbose_name_plural = "Достижения"

    def __str__(self):
        return f"{self.icon} {self.title}"


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='unlocked_by')
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-unlocked_at']
        verbose_name = "Полученное достижение"
        verbose_name_plural = "Полученные достижения"

    def __str__(self):
        return f"{self.user.username} — {self.achievement.title}"


# ===== РЕЗУЛЬТАТЫ ТЕСТОВ МОДУЛЕЙ =====
# Тест на странице модуля (module.test_questions) раньше проверялся только
# в браузере (JS) — результат нигде не сохранялся, поэтому его нельзя было
# ни увидеть в CRM/статистике, ни использовать как условие достижения.
class ModuleTestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_results')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='test_results')
    score_percent = models.PositiveIntegerField(verbose_name="Результат (%)")
    attempts = models.PositiveIntegerField(default=1, verbose_name="Попыток")
    best_score_percent = models.PositiveIntegerField(verbose_name="Лучший результат (%)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'module']
        verbose_name = "Результат теста"
        verbose_name_plural = "Результаты тестов"

    def __str__(self):
        return f"{self.user.username} — {self.module.title}: {self.best_score_percent}%"