# Generated migration for Tenant model

import uuid

import django.core.validators
from django.db import migrations, models

import documents.models.tenant


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1076_workflowaction_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Organization name', max_length=128, verbose_name='name')),
                ('subdomain', models.SlugField(help_text='Subdomain for routing (e.g., "acme")', max_length=63, unique=True, validators=[documents.models.tenant.validate_subdomain], verbose_name='subdomain')),
                ('region', models.CharField(choices=[('eu', 'Europe'), ('us', 'United States'), ('asia', 'Asia')], default='us', help_text='Region for multi-region support', max_length=10, verbose_name='region')),
                ('max_storage_gb', models.IntegerField(default=10, help_text='Storage quota in GB', verbose_name='max storage GB')),
                ('max_documents', models.IntegerField(default=10000, help_text='Maximum number of documents', verbose_name='max documents')),
                ('max_users', models.IntegerField(default=10, help_text='Maximum number of user seats', verbose_name='max users')),
                ('theme_color', models.CharField(default='#17541f', help_text='Branding theme color (hex format)', max_length=7, verbose_name='theme color')),
                ('app_title', models.CharField(default='Paperless-ngx', help_text='Application title for branding', max_length=128, verbose_name='app title')),
                ('logo_url', models.URLField(blank=True, help_text='Custom logo URL', verbose_name='logo URL')),
                ('custom_css', models.TextField(blank=True, help_text='Custom CSS styling', verbose_name='custom CSS')),
                ('is_active', models.BooleanField(default=True, help_text='Enable or disable tenant', verbose_name='is active')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
            ],
            options={
                'verbose_name': 'tenant',
                'verbose_name_plural': 'tenants',
                'db_table': 'tenants',
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
