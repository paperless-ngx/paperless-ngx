# Migration to reassign users from default tenant to acme tenant

from django.db import migrations


def reassign_users_to_acme(apps, schema_editor):
    """
    Reassign all user profiles from default tenant to acme tenant.
    This is for multi-tenant testing where users should belong to acme.
    """
    UserProfile = apps.get_model('paperless', 'UserProfile')
    Tenant = apps.get_model('documents', 'Tenant')

    # Get acme tenant
    try:
        acme_tenant = Tenant.objects.get(subdomain='acme')
    except Tenant.DoesNotExist:
        # If acme tenant doesn't exist, skip this migration
        print("Acme tenant not found, skipping user reassignment")
        return

    # Update all user profiles to point to acme tenant
    updated_count = UserProfile.objects.all().update(tenant_id=acme_tenant.id)
    print(f"Reassigned {updated_count} user profile(s) to acme tenant")


def reverse_to_default(apps, schema_editor):
    """
    Reverse operation: reassign users back to default tenant.
    """
    UserProfile = apps.get_model('paperless', 'UserProfile')
    Tenant = apps.get_model('documents', 'Tenant')

    try:
        default_tenant = Tenant.objects.get(subdomain='default')
        UserProfile.objects.all().update(tenant_id=default_tenant.id)
    except Tenant.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('paperless', '0007_userprofile'),
        ('documents', '1077_create_tenant_model'),
    ]

    operations = [
        migrations.RunPython(reassign_users_to_acme, reverse_to_default),
    ]
