# Generated migration to create Tenant model with UUID primary key

import re
import uuid
from django.core.exceptions import ValidationError
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def validate_subdomain(value):
    """
    Validate that subdomain contains only lowercase alphanumeric characters and hyphens.
    """
    if not re.match(r'^[a-z0-9-]+$', value):
        raise ValidationError(
            _('Subdomain must contain only lowercase alphanumeric characters and hyphens.'),
            code='invalid_subdomain',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1076_workflowaction_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    verbose_name='ID',
                )),
                ('name', models.CharField(
                    max_length=128,
                    verbose_name='name',
                    help_text='Organization name',
                )),
                ('subdomain', models.SlugField(
                    max_length=63,
                    unique=True,
                    validators=[validate_subdomain],
                    verbose_name='subdomain',
                    help_text='Subdomain for routing (e.g., "acme")',
                )),
                ('region', models.CharField(
                    max_length=10,
                    choices=[
                        ('eu', 'Europe'),
                        ('us', 'United States'),
                        ('asia', 'Asia'),
                    ],
                    default='us',
                    verbose_name='region',
                    help_text='Region for multi-region support',
                )),
                ('max_storage_gb', models.IntegerField(
                    default=10,
                    verbose_name='max storage GB',
                    help_text='Storage quota in GB',
                )),
                ('max_documents', models.IntegerField(
                    default=10000,
                    verbose_name='max documents',
                    help_text='Maximum number of documents',
                )),
                ('max_users', models.IntegerField(
                    default=10,
                    verbose_name='max users',
                    help_text='Maximum number of user seats',
                )),
                ('theme_color', models.CharField(
                    max_length=7,
                    default='#17541f',
                    verbose_name='theme color',
                    help_text='Branding theme color (hex format)',
                )),
                ('app_title', models.CharField(
                    max_length=128,
                    default='Paperless-ngx',
                    verbose_name='app title',
                    help_text='Application title for branding',
                )),
                ('logo_url', models.URLField(
                    blank=True,
                    verbose_name='logo URL',
                    help_text='Custom logo URL',
                )),
                ('custom_css', models.TextField(
                    blank=True,
                    verbose_name='custom CSS',
                    help_text='Custom CSS styling',
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    verbose_name='is active',
                    help_text='Enable or disable tenant',
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    verbose_name='created at',
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    verbose_name='updated at',
                )),
            ],
            options={
                'db_table': 'tenants',
                'verbose_name': 'tenant',
                'verbose_name_plural': 'tenants',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='tenant',
            index=models.Index(fields=['subdomain'], name='tenant_subdomain_idx'),
        ),
        migrations.AddIndex(
            model_name='tenant',
            index=models.Index(fields=['region'], name='tenant_region_idx'),
        ),
    ]
