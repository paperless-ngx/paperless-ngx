from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0004_applicationconfiguration_barcode_asn_prefix_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationconfiguration",
            name="language_code_workflow",
            field=models.CharField(
                blank=True,
                max_length=6,
                null=True,
                verbose_name="Language settings for workflows (language code)",
            ),
        ),
    ]
