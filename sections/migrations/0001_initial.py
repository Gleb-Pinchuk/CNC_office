import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SectionTable",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255, verbose_name="Название")),
                (
                    "section_type",
                    models.CharField(
                        choices=[
                            ("attendance", "📊 Посещаемость"),
                            ("rangers", "🤖 Цифровые рейнджеры"),
                            ("statements", "📋 Ведомости"),
                        ],
                        max_length=50,
                        verbose_name="Тип раздела",
                    ),
                ),
                (
                    "content",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Содержимое (Handsontable data)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Дата обновления"),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="section_tables",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Владелец",
                    ),
                ),
            ],
            options={
                "verbose_name": "Таблица раздела",
                "verbose_name_plural": "Таблицы разделов",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sectiontable",
            index=models.Index(
                fields=["section_type", "owner"], name="sections_se_section_8d7cc9_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="sectiontable",
            index=models.Index(
                fields=["owner", "-updated_at"], name="sections_se_owner_i_1b4f5a_idx"
            ),
        ),
    ]
