from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0003_create_filepermission"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveCellPresence",
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
                    "file_type",
                    models.CharField(
                        choices=[
                            ("section_table", "Таблица раздела"),
                            ("document", "Документ"),
                        ],
                        max_length=20,
                        verbose_name="Тип объекта",
                    ),
                ),
                ("file_id", models.IntegerField(verbose_name="ID объекта")),
                ("sheet_name", models.CharField(blank=True, default="", max_length=120)),
                ("row", models.IntegerField(default=0)),
                ("col", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="live_cell_presence",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Онлайн-ячейка",
                "verbose_name_plural": "Онлайн-ячейки",
                "unique_together": {("file_type", "file_id", "user")},
            },
        ),
        migrations.AddIndex(
            model_name="livecellpresence",
            index=models.Index(
                fields=["file_type", "file_id", "-updated_at"],
                name="files_livece_file_ty_4d0e71_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="livecellpresence",
            index=models.Index(
                fields=["user", "-updated_at"], name="files_livece_user_id_0a8d6e_idx"
            ),
        ),
    ]
