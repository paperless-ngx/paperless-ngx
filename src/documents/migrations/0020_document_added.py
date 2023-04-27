import django.utils.timezone
from django.db import migrations
from django.db import models


def set_added_time_to_created_time(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    for doc in Document.objects.all():
        doc.added = doc.created
        doc.save()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0019_add_consumer_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="added",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                editable=False,
            ),
        ),
        migrations.RunPython(set_added_time_to_created_time),
    ]
