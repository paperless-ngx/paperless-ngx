# Generated manually for DeletionRequest model
# Based on model definition in documents/models.py

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Add DeletionRequest model for AI-initiated deletion requests.
    
    This model tracks deletion requests that require user approval,
    implementing the safety requirement from agents.md to ensure
    no documents are deleted without explicit user consent.
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("documents", "1075_add_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeletionRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "requested_by_ai",
                    models.BooleanField(default=True),
                ),
                (
                    "ai_reason",
                    models.TextField(
                        help_text="Detailed explanation from AI about why deletion is recommended"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("cancelled", "Cancelled"),
                            ("completed", "Completed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "impact_summary",
                    models.JSONField(
                        default=dict,
                        help_text="Summary of what will be affected by this deletion",
                    ),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "review_comment",
                    models.TextField(
                        blank=True,
                        help_text="User's comment when reviewing",
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "completion_details",
                    models.JSONField(
                        default=dict,
                        help_text="Details about the deletion execution",
                    ),
                ),
                (
                    "documents",
                    models.ManyToManyField(
                        help_text="Documents that would be deleted if approved",
                        related_name="deletion_requests",
                        to="documents.document",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who reviewed and approved/rejected",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_deletion_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User who must approve this deletion",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deletion_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "deletion request",
                "verbose_name_plural": "deletion requests",
                "ordering": ["-created_at"],
            },
        ),
    ]
