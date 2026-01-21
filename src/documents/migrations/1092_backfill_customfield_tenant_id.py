# Data migration to populate CustomField.tenant_id from related Documents

from django.db import migrations


def backfill_customfield_tenant_id(apps, schema_editor):
    """
    Populate CustomField.tenant_id from related documents.

    Strategy:
    1. For CustomFields with instances: inherit tenant_id from first CustomFieldInstance's document
    2. For CustomFields without instances: use tenant_id from any document

    Since CustomField can be used across multiple documents, we need to check if all
    documents belong to the same tenant. If they don't, we pick the first one.
    """
    import uuid
    CustomField = apps.get_model('documents', 'CustomField')
    CustomFieldInstance = apps.get_model('documents', 'CustomFieldInstance')
    Document = apps.get_model('documents', 'Document')

    # Get a default tenant_id from any existing document
    first_doc = Document.objects.first()
    if not first_doc or not hasattr(first_doc, 'tenant_id') or not first_doc.tenant_id:
        # If no documents exist or they don't have tenant_id, use a placeholder
        # This will be updated when the proper tenant migrations run
        default_tenant_id = uuid.uuid4()
    else:
        default_tenant_id = first_doc.tenant_id

    # Update all custom fields to inherit tenant_id from their first related document
    custom_fields = CustomField.objects.filter(tenant_id__isnull=True)

    for custom_field in custom_fields:
        # Try to get tenant_id from first related CustomFieldInstance
        first_instance = CustomFieldInstance.objects.filter(field=custom_field).first()

        if first_instance and first_instance.document and hasattr(first_instance.document, 'tenant_id') and first_instance.document.tenant_id:
            custom_field.tenant_id = first_instance.document.tenant_id
        else:
            # No instances yet or document doesn't have tenant_id, use default
            custom_field.tenant_id = default_tenant_id

        custom_field.save(update_fields=['tenant_id'])


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all CustomField.tenant_id fields back to NULL.
    """
    CustomField = apps.get_model('documents', 'CustomField')
    CustomField.objects.all().update(tenant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1091_add_tenant_id_to_customfield'),
    ]

    operations = [
        migrations.RunPython(
            backfill_customfield_tenant_id,
            reverse_backfill,
        ),
    ]
