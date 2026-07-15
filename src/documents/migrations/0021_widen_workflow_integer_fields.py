import django.core.validators
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0020_drop_celery_results"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflow",
            name="order",
            field=models.IntegerField(default=0, verbose_name="order"),
        ),
        migrations.AlterField(
            model_name="workflowaction",
            name="order",
            field=models.PositiveIntegerField(default=0, verbose_name="order"),
        ),
        migrations.AlterField(
            model_name="workflowtrigger",
            name="schedule_offset_days",
            field=models.IntegerField(
                default=0,
                help_text="The number of days to offset the schedule trigger by.",
                verbose_name="schedule offset days",
            ),
        ),
        migrations.AlterField(
            model_name="workflowtrigger",
            name="schedule_recurring_interval_days",
            field=models.PositiveIntegerField(
                default=1,
                help_text="The number of days between recurring schedule triggers.",
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="schedule recurring delay in days",
            ),
        ),
    ]
