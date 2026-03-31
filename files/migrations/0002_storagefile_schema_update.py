import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0001_initial"),
    ]

    operations = [
        # StorageFile: add missing columns used by current model code
        migrations.AddField(
            model_name="storagefile",
            name="file_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Имя файла"),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="mime_type",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="MIME тип"),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="size",
            field=models.BigIntegerField(default=0, verbose_name="Размер (байты)"),
        ),
        migrations.AlterField(
            model_name="storagefile",
            name="folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="files",
                to="files.storagefolder",
                verbose_name="Папка",
            ),
        ),
        migrations.AlterModelOptions(
            name="storagefile",
            options={"ordering": ["-uploaded_at"], "verbose_name": "Файл", "verbose_name_plural": "Файлы"},
        ),
        # StorageFolder: align model options/fields (safe no-op for existing DB)
        migrations.AlterModelOptions(
            name="storagefolder",
            options={
                "ordering": ["name"],
                "verbose_name": "Папка",
                "verbose_name_plural": "Папки",
                "unique_together": {("owner", "name", "parent")},
            },
        ),
        # AuditLog: update choices and file relation
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("upload", "📤 Загрузка"),
                    ("download", "⬇️ Скачивание"),
                    ("delete", "🗑️ Удаление"),
                    ("share", "🔗 Предоставление доступа"),
                    ("login", "🔑 Вход"),
                    ("logout", "🚪 Выход"),
                    ("create", "➕ Создание"),
                    ("update", "✏️ Обновление"),
                ],
                max_length=20,
                verbose_name="Действие",
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="file",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs",
                to="files.storagefile",
                verbose_name="Файл",
            ),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="details",
            field=models.TextField(blank=True, verbose_name="Детали"),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="timestamp",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Дата"),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="audit_logs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Пользователь",
            ),
        ),
        # Drop legacy models that are no longer used in code (safe for fresh CI DB)
        migrations.DeleteModel(name="FileAccessPermission"),
        migrations.DeleteModel(name="FileLock"),
        # file/updated_at/is_shared removed from current StorageFile model
        migrations.RemoveField(model_name="storagefile", name="updated_at"),
        migrations.RemoveField(model_name="storagefile", name="is_shared"),
        migrations.AlterField(
            model_name="storagefile",
            name="file",
            field=models.FileField(upload_to="files.models.file_upload_path", verbose_name="Файл"),
        ),
        # indexes to match current model
        migrations.RemoveIndex(model_name="storagefile", name="files_stora_is_shar_abe3ba_idx"),
        migrations.AddIndex(
            model_name="storagefile",
            index=models.Index(fields=["owner", "-uploaded_at"], name="files_stora_owner_upl_6d1d12_idx"),
        ),
        migrations.AddIndex(
            model_name="storagefile",
            index=models.Index(fields=["folder", "-uploaded_at"], name="files_stora_folder_upl_1a2b34_idx"),
        ),
        migrations.RunPython(_noop, reverse_code=_noop),
    ]

