# Data migration to populate Note.tenant_id from related Document

from django.db import migrations


def backfill_note_tenant_id(apps, schema_editor):
    """
    Populate Note.tenant_id from the related Document's tenant_id.
    For notes without a document, assign to the default tenant.
    """
    Note = apps.get_model('documents', 'Note')
    Tenant = apps.get_model('documents', 'Tenant')

    # Get default tenant
    default_tenant = Tenant.objects.filter(subdomain='default').first()
    if not default_tenant:
        # Create default tenant if it doesn't exist
        default_tenant = Tenant.objects.create(
            subdomain='default',
            name='Default Tenant'
        )

    default_tenant_id = default_tenant.id

    # Update notes that have a document - inherit tenant_id from document
    notes_with_document = Note.objects.filter(
        tenant_id__isnull=True,
        document__isnull=False
    )

    for note in notes_with_document:
        note.tenant_id = note.document.tenant_id
        note.save(update_fields=['tenant_id'])

    # Update notes without a document - assign to default tenant
    Note.objects.filter(
        tenant_id__isnull=True
    ).update(tenant_id=default_tenant_id)


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all Note.tenant_id fields back to NULL.
    """
    Note = apps.get_model('documents', 'Note')
    Note.objects.all().update(tenant_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1084_add_tenant_id_to_note'),
    ]

    operations = [
        migrations.RunPython(
            backfill_note_tenant_id,
            reverse_backfill,
        ),
    ]
