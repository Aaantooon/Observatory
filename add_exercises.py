import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from bot_api.models import Exercise

ex = [
    {"title": "Бесилки", "description": "Упражнения для снятия раздражения"},
    {"title": "Дыхание 4-7-8", "description": "Вдох на 4, задержка на 7, выдох на 8"},
    {"title": "Наблюдение за телом", "description": "Сканируй тело от пальцев ног до макушки"},
    {"title": "Осознанное питание", "description": "Ешь медленно, чувствуй вкус"}
]

for e in ex:
    obj, created = Exercise.objects.get_or_create(
        title=e["title"],
        defaults={"description": e["description"]}
    )
    if created:
        print(f"✅ Добавлено: {e['title']}")
    else:
        print(f"⏳ Уже есть: {e['title']}")

print(f"🎉 Всего упражнений: {Exercise.objects.count()}")
