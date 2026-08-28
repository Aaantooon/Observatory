from django.db import models

class User(models.Model):
    vk_id = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    streak = models.IntegerField(default=0, verbose_name="Серия дней")
    last_activity_date = models.DateField(null=True, blank=True, verbose_name="Последняя активность")

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ID: {self.vk_id})"


class Exercise(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=50, default='default')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Result(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='results')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    result_data = models.JSONField()
    is_approved = models.BooleanField(default=False)
    corrected_data = models.JSONField(null=True, blank=True)
    correction_comment = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user} - {self.exercise.title}"


class ExerciseProgress(models.Model):
    """Сохраняет прогресс упражнения для продолжения"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progresses')
    exercise_type = models.CharField(max_length=50, default='besilki')
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'exercise_type']

    def __str__(self):
        return f"{self.user} - {self.exercise_type}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    exercise_type = models.CharField(max_length=50)
    schedule_type = models.CharField(max_length=20)  # 'daily' или 'once'
    schedule_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)