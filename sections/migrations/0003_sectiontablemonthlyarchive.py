from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sections", "0002_sectiontable_nextcloud_sync"),
    ]

    operations = [
        migrations.CreateModel(
            name="SectionTableMonthlyArchive",
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
                ("year", models.PositiveSmallIntegerField(verbose_name="Год")),
                ("month", models.PositiveSmallIntegerField(verbose_name="Месяц")),
                (
                    "content",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Снимок таблицы",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="Дата создания",
                    ),
                ),
                (
                    "table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monthly_archives",
                        to="sections.sectiontable",
                        verbose_name="Исходная таблица",
                    ),
                ),
            ],
            options={
                "verbose_name": "Месячный архив таблицы",
                "verbose_name_plural": "Месячные архивы таблиц",
                "ordering": ["-year", "-month", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sectiontablemonthlyarchive",
            index=models.Index(
                fields=["table", "-year", "-month"],
                name="sections_se_table_i_40d7da_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="sectiontablemonthlyarchive",
            constraint=models.UniqueConstraint(
                fields=("table", "year", "month"),
                name="unique_section_table_monthly_archive",
            ),
        ),
    ]
