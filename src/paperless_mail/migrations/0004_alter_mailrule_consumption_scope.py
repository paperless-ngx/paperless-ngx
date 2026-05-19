# Generated to add ConsumptionScope.COMBINED choice.

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0003_mailrule_stop_processing"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mailrule",
            name="consumption_scope",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Only process attachments."),
                    (
                        2,
                        "Process full Mail (with embedded attachments in file) as .eml",
                    ),
                    (
                        3,
                        "Process full Mail (with embedded attachments in file) as .eml + process attachments as separate documents",
                    ),
                    (
                        4,
                        "Process body + attachments merged into a single document (parser is expected to merge attachments into the body)",
                    ),
                ],
                default=1,
                verbose_name="consumption scope",
            ),
        ),
    ]
