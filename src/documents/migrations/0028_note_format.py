from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0027_documentbarcode"),
    ]

    operations = [
        migrations.AddField(
            model_name="note",
            name="format",
            field=models.CharField(
                choices=[("plain", "Plain"), ("markdown", "Markdown")],
                default="plain",
                max_length=16,
            ),
        ),
    ]
