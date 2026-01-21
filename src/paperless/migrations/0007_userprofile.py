# Generated migration for UserProfile model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_profiles_for_existing_users(apps, schema_editor):
    """
    Create UserProfile instances for existing users.
    Assign them to the default tenant.
    """
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('paperless', 'UserProfile')
    Tenant = apps.get_model('documents', 'Tenant')

    # Get or create default tenant
    default_tenant, _ = Tenant.objects.get_or_create(
        subdomain='default',
        defaults={
            'name': 'Default Tenant',
            'is_active': True,
        }
    )

    # Create profiles for all users except system users
    system_users = ['consumer', 'AnonymousUser']
    for user in User.objects.exclude(username__in=system_users):
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(
                user=user,
                tenant_id=default_tenant.id
            )


class Migration(migrations.Migration):

    dependencies = [
        ('paperless', '0005_applicationconfiguration_ai_enabled_and_more'),
        ('documents', '1079_create_default_tenant_and_backfill'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.UUIDField(db_index=True, null=False, blank=False, help_text='Tenant to which this user belongs', verbose_name='tenant')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'user profile',
                'verbose_name_plural': 'user profiles',
            },
        ),
        migrations.AddIndex(
            model_name='userprofile',
            index=models.Index(fields=['tenant_id'], name='userprofile_tenant_idx'),
        ),
        migrations.RunPython(create_profiles_for_existing_users, migrations.RunPython.noop),
    ]
