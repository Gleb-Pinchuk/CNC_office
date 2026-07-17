from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sections", "0003_sectiontablemonthlyarchive"),
    ]

    operations = [
        migrations.AddField(
            model_name="sectiontable",
            name="live_monitoring_month",
            field=models.CharField(
                blank=True,
                default="",
                help_text="После rollover: замечания текущего месяца не очищаются повторно.",
                max_length=7,
                verbose_name="Месяц живых колонок недель (YYYY-MM)",
            ),
        ),
    ]
