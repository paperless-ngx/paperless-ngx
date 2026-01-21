# Migration to add tenant_id field to ShareLink model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1086_make_note_tenant_id_non_nullable'),
    ]

    operations = [
        # Add tenant_id field to ShareLink (nullable initially for data migration)
        migrations.AddField(
            model_name='sharelink',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=True,
                blank=True,
                verbose_name='tenant'
            ),
        ),
        # Remove the explicit owner field from ShareLink model definition
        # since it's now inherited from ModelWithOwner
        # Note: This doesn't drop the column - it just removes the duplicate definition
        migrations.RemoveField(
            model_name='sharelink',
            name='owner',
        ),
        # Re-add owner field (inherited from ModelWithOwner)
        # This ensures proper migration state
        migrations.AddField(
            model_name='sharelink',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                default=None,
                on_delete=models.SET_NULL,
                to='auth.user',
                verbose_name='owner',
            ),
        ),
    ]
