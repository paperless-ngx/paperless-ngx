from django.conf import settings
from django.db import migrations
from django.db import models


def clear_implicit_ai_disabled(apps, schema_editor):
    if not settings.AI_ENABLED:
        return

    application_configuration = apps.get_model(
        "paperless",
        "ApplicationConfiguration",
    )
    application_configuration.objects.filter(ai_enabled=False).update(ai_enabled=None)


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0015_applicationconfiguration_remote_ocr_mode"),
    ]

    operations = [
        migrations.RunPython(clear_implicit_ai_disabled, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="applicationconfiguration",
            name="ai_enabled",
            field=models.BooleanField(
                null=True,
                verbose_name="Enables AI features",
            ),
        ),
    ]
