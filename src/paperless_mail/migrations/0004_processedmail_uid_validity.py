from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0003_mailrule_stop_processing"),
    ]

    operations = [
        migrations.AddField(
            model_name="processedmail",
            name="uid_validity",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                verbose_name="uid validity",
            ),
        ),
    ]
