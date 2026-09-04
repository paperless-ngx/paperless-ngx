from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0015_applicationconfiguration_remote_ocr_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicationconfiguration",
            name="ai_enabled",
            field=models.BooleanField(
                null=True,
                verbose_name="Enables AI features",
            ),
        ),
    ]
