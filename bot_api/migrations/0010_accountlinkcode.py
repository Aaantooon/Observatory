# Привязка одного человека к нескольким платформам (VK + Telegram) через
# одноразовый код — см. platform_bots/README.md, раздел «Модель
# пользователя», и bot_api/models.py::AccountLinkCode.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_api", "0009_user_telegram_id_alter_user_vk_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountLinkCode",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="link_codes",
                        to="bot_api.user",
                    ),
                ),
            ],
        ),
    ]
