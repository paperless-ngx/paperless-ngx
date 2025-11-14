# Generated migration for AI Webhooks

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('documents', '1075_add_performance_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIWebhookEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('deletion_request_created', 'Deletion Request Created'),
                        ('suggestion_auto_applied', 'Suggestion Auto Applied'),
                        ('scan_completed', 'AI Scan Completed')
                    ],
                    help_text='Type of AI event that triggered this webhook',
                    max_length=50
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('webhook_url', models.CharField(
                    help_text='URL where the webhook was sent',
                    max_length=512
                )),
                ('payload', models.JSONField(help_text='Data sent in the webhook')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('success', 'Success'),
                        ('failed', 'Failed'),
                        ('retrying', 'Retrying')
                    ],
                    default='pending',
                    max_length=20
                )),
                ('attempts', models.PositiveIntegerField(
                    default=0,
                    help_text='Number of delivery attempts'
                )),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('response_status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('response_body', models.TextField(blank=True)),
                ('error_message', models.TextField(
                    blank=True,
                    help_text='Error message if delivery failed'
                )),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'AI webhook event',
                'verbose_name_plural': 'AI webhook events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AIWebhookConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text='Friendly name for this webhook configuration',
                    max_length=128,
                    unique=True
                )),
                ('enabled', models.BooleanField(
                    default=True,
                    help_text='Whether this webhook is active'
                )),
                ('url', models.CharField(
                    help_text='URL to send webhook notifications',
                    max_length=512
                )),
                ('events', models.JSONField(
                    default=list,
                    help_text='List of event types this webhook should receive'
                )),
                ('headers', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Custom HTTP headers to include in webhook requests'
                )),
                ('secret', models.CharField(
                    blank=True,
                    help_text='Secret key for signing webhook payloads (optional)',
                    max_length=256
                )),
                ('max_retries', models.PositiveIntegerField(
                    default=3,
                    help_text='Maximum number of retry attempts'
                )),
                ('retry_delay', models.PositiveIntegerField(
                    default=60,
                    help_text='Initial retry delay in seconds (will increase exponentially)'
                )),
                ('timeout', models.PositiveIntegerField(
                    default=10,
                    help_text='Request timeout in seconds'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ai_webhook_configs',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'AI webhook configuration',
                'verbose_name_plural': 'AI webhook configurations',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='aiwebhookevent',
            index=models.Index(fields=['event_type', 'status'], name='documents_a_event_t_8de562_idx'),
        ),
        migrations.AddIndex(
            model_name='aiwebhookevent',
            index=models.Index(fields=['created_at'], name='documents_a_created_a29f8c_idx'),
        ),
        migrations.AddIndex(
            model_name='aiwebhookevent',
            index=models.Index(fields=['status'], name='documents_a_status_9b9c6f_idx'),
        ),
    ]
