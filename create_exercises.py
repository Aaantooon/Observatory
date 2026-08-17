# create_exercises.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from bot_api.models import Exercise

# Удаляем все старые упражнения
Exercise.objects.all().delete()
print("🗑️ Старые упражнения удалены")

# Создаем 6 упражнений
exercises = [
    {
        "title": "Бесилки",
        "description": "Выяви, что тебя раздражает. Напиши, что бесит, и поставь оценку от 1 до 10.",
        "type": "besilki",
        "order": 1
    },
    {
        "title": "Дыхание",
        "description": "Сделай 10 глубоких вдохов и выдохов. Следи за дыханием.",
        "type": "breathing",
        "order": 2
    },
    {
        "title": "Эмоции",
        "description": "Запиши своё текущее чувство одним словом.",
        "type": "emotions",
        "order": 3
    },
    {
        "title": "Медитация",
        "description": "Посиди в тишине 30 секунд. Просто слушай тишину.",
        "type": "meditation",
        "order": 4
    },
    {
        "title": "Осознанность",
        "description": "Назови 3 предмета вокруг себя. Опиши их цвет и текстуру.",
        "type": "mindfulness",
        "order": 5
    },
    {
        "title": "Благодарность",
        "description": "Напиши, за что ты благодарен сегодня.",
        "type": "gratitude",
        "order": 6
    }
]

for ex in exercises:
    Exercise.objects.create(**ex)
    print(f"✅ {ex['title']} создано!")

print(f"\n📊 Всего упражнений: {Exercise.objects.count()}")
for ex in Exercise.objects.all():
    print(f"  {ex.order}. {ex.title} ({ex.type})")