# Data migration to populate ShareLink.tenant_id from related Document

from django.db import migrations


def backfill_sharelink_tenant_id(apps, schema_editor):
    """
    Populate ShareLink.tenant_id from the related Document's tenant_id.
    All ShareLinks must have a document, so no default tenant assignment needed.
    """
    ShareLink = apps.get_model('documents', 'ShareLink')

    # Update share links - inherit tenant_id from document
    sharelinks_to_update = ShareLink.objects.filter(tenant_id__isnull=True)

    for sharelink in sharelinks_to_update:
        if sharelink.document:
            sharelink.tenant_id = sharelink.document.tenant_id
            sharelink.save(update_fields=['tenant_id'])


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all ShareLink.tenant_id fields back to NULL.
    """
    ShareLink = apps.get_model('documents', 'ShareLink')
    ShareLink.objects.all().update(tenant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1087_add_tenant_id_to_sharelink'),
    ]

    operations = [
        migrations.RunPython(
            backfill_sharelink_tenant_id,
            reverse_backfill,
        ),
    ]
