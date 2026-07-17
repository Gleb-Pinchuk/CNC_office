import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_api", "0001_initial"),
        ("sections", "0003_sectiontablemonthlyarchive"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentTrash",
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
                (
                    "sheet_name",
                    models.CharField(max_length=255, verbose_name="Лист / направление"),
                ),
                (
                    "student_fio",
                    models.CharField(max_length=255, verbose_name="ФИО студента"),
                ),
                (
                    "group_name",
                    models.CharField(
                        blank=True, default="", max_length=255, verbose_name="Группа"
                    ),
                ),
                ("row_data", models.JSONField(default=list, verbose_name="Строка листа")),
                (
                    "original_row_index",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Исходный индекс строки"
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Удалён"),
                ),
                (
                    "expires_at",
                    models.DateTimeField(verbose_name="Удалить навсегда после"),
                ),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trashed_students",
                        to="sections.sectiontable",
                        verbose_name="Таблица",
                    ),
                ),
            ],
            options={
                "verbose_name": "Студент в корзине",
                "verbose_name_plural": "Корзина студентов",
                "ordering": ["-deleted_at"],
            },
        ),
        migrations.AddIndex(
            model_name="studenttrash",
            index=models.Index(
                fields=["table", "sheet_name", "expires_at"],
                name="bot_api_stu_table_i_a1b201_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="studenttrash",
            index=models.Index(
                fields=["expires_at"],
                name="bot_api_stu_expires_b2c302_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="studenttrash",
            index=models.Index(
                fields=["table", "sheet_name", "student_fio"],
                name="bot_api_stu_table_i_c3d403_idx",
            ),
        ),
    ]
