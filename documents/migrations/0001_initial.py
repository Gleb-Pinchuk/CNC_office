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
            name="Document",
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
                    "doc_type",
                    models.CharField(
                        choices=[("spreadsheet", "📊 Таблица"), ("text", "📝 Текст")],
                        default="spreadsheet",
                        max_length=20,
                        verbose_name="Тип документа",
                    ),
                ),
                (
                    "content",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Содержимое"
                    ),
                ),
                (
                    "is_editable",
                    models.BooleanField(
                        default=True, verbose_name="Можно редактировать"
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
                        related_name="documents",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Владелец",
                    ),
                ),
            ],
            options={
                "verbose_name": "Документ",
                "verbose_name_plural": "Документы",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["owner", "-updated_at"], name="documents_do_owner_i_04d2b7_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["doc_type", "-updated_at"],
                name="documents_do_doc_ty_5f7a1b_idx",
            ),
        ),
    ]
