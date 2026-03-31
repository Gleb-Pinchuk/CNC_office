from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0002_storagefile_schema_update"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FilePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file_type",
                    models.CharField(
                        choices=[("storage_file", "Файл"), ("section_table", "Таблица раздела"), ("document", "Документ")],
                        max_length=20,
                        verbose_name="Тип объекта",
                    ),
                ),
                ("file_id", models.IntegerField(verbose_name="ID объекта")),
                (
                    "permission",
                    models.CharField(
                        choices=[("read", "👁️ Только чтение"), ("write", "✏️ Чтение и запись")],
                        default="read",
                        max_length=10,
                        verbose_name="Разрешение",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата предоставления")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="file_permissions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Разрешение",
                "verbose_name_plural": "Разрешения",
                "unique_together": {("file_type", "file_id", "user")},
            },
        ),
        migrations.AddIndex(
            model_name="filepermission",
            index=models.Index(fields=["file_type", "file_id", "user"], name="files_filep_file_ty_1f2a3b_idx"),
        ),
        migrations.AddIndex(
            model_name="filepermission",
            index=models.Index(fields=["user", "file_type"], name="files_filep_user_fi_3c4d5e_idx"),
        ),
    ]

