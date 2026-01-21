# Data migration to populate ShareLink.tenant_id from related Document

from django.db import migrations


def backfill_sharelink_tenant_id(apps, schema_editor):
    """
    Populate ShareLink.tenant_id from the related Document's tenant_id.
    All ShareLinks have a document (non-nullable FK), so we can always inherit tenant_id.
    """
    ShareLink = apps.get_model('documents', 'ShareLink')
    
    # Update all share links to inherit tenant_id from their document
    share_links = ShareLink.objects.filter(tenant_id__isnull=True)
    
    for share_link in share_links:
        share_link.tenant_id = share_link.document.tenant_id
        share_link.save(update_fields=['tenant_id'])


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
