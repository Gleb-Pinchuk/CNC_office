# Generated manually for Nextcloud sync flags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sections", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sectiontable",
            name="needs_nextcloud_push",
            field=models.BooleanField(
                default=False,
                verbose_name="Есть несинхронизированные изменения для Nextcloud",
            ),
        ),
        migrations.AddField(
            model_name="sectiontable",
            name="last_nextcloud_push_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Последняя отправка в Nextcloud",
            ),
        ),
    ]
