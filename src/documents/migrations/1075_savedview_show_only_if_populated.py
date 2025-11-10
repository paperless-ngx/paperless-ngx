from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1074_workflowrun_deleted_at_workflowrun_restored_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedview",
            name="show_only_if_populated",
            field=models.BooleanField(
                verbose_name="Show only if populated",
                default=False,
                null=True,  # Now optional in DB
            ),
        ),
    ]
