# Generated manually for RemarkEvidence

import django.db.models.deletion
from django.db import migrations, models

import bot_api.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sections", "0003_sectiontablemonthlyarchive"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemarkEvidence",
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
                ("remark_date", models.DateField(verbose_name="Дата замечания")),
                (
                    "image",
                    models.FileField(
                        upload_to=bot_api.models.remark_evidence_upload_to,
                        verbose_name="Скрин",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remark_evidences",
                        to="sections.sectiontable",
                        verbose_name="Таблица",
                    ),
                ),
            ],
            options={
                "verbose_name": "Доказательство замечания",
                "verbose_name_plural": "Доказательства замечаний",
            },
        ),
        migrations.AddIndex(
            model_name="remarkevidence",
            index=models.Index(
                fields=["table", "sheet_name", "student_fio"],
                name="bot_api_rem_table_i_7a1c01_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="remarkevidence",
            index=models.Index(
                fields=["table", "sheet_name", "remark_date"],
                name="bot_api_rem_table_i_9f2d02_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="remarkevidence",
            constraint=models.UniqueConstraint(
                fields=("table", "sheet_name", "student_fio", "remark_date"),
                name="unique_remark_evidence_per_student_date",
            ),
        ),
    ]
