# Generated by Django 5.1.1 on 2024-10-01 20:42


from django.db import migrations
from django.db import transaction


def convert_from_format_to_template(apps, schema_editor):
    # TODO: Is there a signal to disable?  I don't want documents getting moved while this is running

    StoragePath = apps.get_model("documents", "StoragePath")

    from documents.templatetags import convert_to_django_template_format

    with transaction.atomic():
        for storage_path in StoragePath.objects.all():
            storage_path.path = convert_to_django_template_format(storage_path.path)
            storage_path.save()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1053_document_page_count"),
    ]

    operations = [
        migrations.RunPython(
            convert_from_format_to_template,
            # This is a one way migration
            migrations.RunPython.noop,
        ),
    ]