# Migration to add users ManyToManyField to TenantGroup

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('documents', '1099_merge_20260122_0811'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantgroup',
            name='users',
            field=models.ManyToManyField(
                to='auth.user',
                verbose_name='users',
                blank=True,
                related_name='tenant_groups',
                help_text='Users in this tenant group',
            ),
        ),
    ]
