# Шаг 4 плана миграции ботов на несколько платформ (platform_bots/README.md):
# у User появляется telegram_id, а vk_id становится необязательным — теперь
# запись пользователя может представлять либо VK-, либо Telegram-аккаунт
# (см. комментарий в bot_api/models.py::User).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_api", "0008_channel_alter_post_platform_alter_post_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="telegram_id",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, null=True, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="vk_id",
            field=models.CharField(
                blank=True, db_index=True, max_length=50, null=True, unique=True
            ),
        ),
    ]
