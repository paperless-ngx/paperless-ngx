# Migration to create TenantGroup model with tenant isolation

import uuid
from django.db import migrations, models
import django.db.models.deletion


def migrate_groups_to_tenant_groups(apps, schema_editor):
    """
    Migrate existing Django Group objects to TenantGroup.

    This function:
    1. Gets the default tenant (created in migration 1079)
    2. Creates TenantGroup instances for each existing Group
    3. Migrates permissions from Group to TenantGroup
    """
    Group = apps.get_model('auth', 'Group')
    TenantGroup = apps.get_model('documents', 'TenantGroup')
    Tenant = apps.get_model('documents', 'Tenant')

    # Get the default tenant (there should be one from migration 1079)
    try:
        default_tenant = Tenant.objects.first()
        if not default_tenant:
            # If no tenant exists, create a default one
            default_tenant = Tenant.objects.create(
                name='Default Tenant',
                subdomain='default',
                region='us',
            )
    except Exception:
        # If tenant model doesn't exist or other error, skip migration
        return

    # Migrate each existing Group to TenantGroup
    for group in Group.objects.all():
        # Create TenantGroup with same name
        tenant_group = TenantGroup.objects.create(
            name=group.name,
            tenant_id=default_tenant.id,
            owner=None,  # No owner for migrated groups
        )

        # Migrate permissions
        for permission in group.permissions.all():
            tenant_group.permissions.add(permission)


def reverse_migrate_groups(apps, schema_editor):
    """
    Reverse migration: Delete all TenantGroup instances.

    Note: This does NOT restore Group objects, as we want to keep
    the tenant-scoped architecture going forward.
    """
    TenantGroup = apps.get_model('documents', 'TenantGroup')
    TenantGroup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('documents', '1082_migrate_classifier_to_tenant_specific'),
    ]

    operations = [
        # Create TenantGroup model
        migrations.CreateModel(
            name='TenantGroup',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('tenant_id', models.UUIDField(
                    db_index=True,
                    verbose_name='tenant',
                )),
                ('name', models.CharField(
                    max_length=150,
                    verbose_name='name',
                    help_text='The name of the group within this tenant',
                )),
                ('owner', models.ForeignKey(
                    blank=True,
                    null=True,
                    default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='auth.user',
                    verbose_name='owner',
                )),
                ('permissions', models.ManyToManyField(
                    to='auth.permission',
                    verbose_name='permissions',
                    blank=True,
                    related_name='tenant_groups',
                )),
            ],
            options={
                'verbose_name': 'tenant group',
                'verbose_name_plural': 'tenant groups',
                'ordering': ['name'],
            },
        ),
        # Add unique constraint for (tenant_id, name)
        migrations.AddConstraint(
            model_name='tenantgroup',
            constraint=models.UniqueConstraint(
                fields=['tenant_id', 'name'],
                name='unique_tenant_group_name',
            ),
        ),
        # Add index for tenant_id lookups
        migrations.AddIndex(
            model_name='tenantgroup',
            index=models.Index(
                fields=['tenant_id', 'name'],
                name='tenantgroup_tenant_name_idx',
            ),
        ),
        # Migrate existing groups to TenantGroup
        migrations.RunPython(
            migrate_groups_to_tenant_groups,
            reverse_migrate_groups,
        ),
    ]
