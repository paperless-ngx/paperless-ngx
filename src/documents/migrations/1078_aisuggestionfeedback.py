# Generated manually for AI Suggestions API

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    """
    Add AISuggestionFeedback model for tracking user feedback on AI suggestions.
    
    This model enables:
    - Tracking of applied vs rejected AI suggestions
    - Accuracy statistics and improvement of AI models
    - User feedback analysis
    """

    dependencies = [
        ("documents", "1077_add_deletionrequest_performance_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AISuggestionFeedback",
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
                    "suggestion_type",
                    models.CharField(
                        choices=[
                            ("tag", "Tag"),
                            ("correspondent", "Correspondent"),
                            ("document_type", "Document Type"),
                            ("storage_path", "Storage Path"),
                            ("custom_field", "Custom Field"),
                            ("workflow", "Workflow"),
                            ("title", "Title"),
                        ],
                        max_length=50,
                        verbose_name="suggestion type",
                    ),
                ),
                (
                    "suggested_value_id",
                    models.IntegerField(
                        blank=True,
                        help_text="ID of the suggested object (tag, correspondent, etc.)",
                        null=True,
                        verbose_name="suggested value ID",
                    ),
                ),
                (
                    "suggested_value_text",
                    models.TextField(
                        blank=True,
                        help_text="Text representation of the suggested value",
                        verbose_name="suggested value text",
                    ),
                ),
                (
                    "confidence",
                    models.FloatField(
                        help_text="AI confidence score (0.0 to 1.0)",
                        validators=[
                            django.core.validators.MinValueValidator(0.0),
                            django.core.validators.MaxValueValidator(1.0),
                        ],
                        verbose_name="confidence",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("applied", "Applied"),
                            ("rejected", "Rejected"),
                        ],
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="created at",
                    ),
                ),
                (
                    "applied_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="applied/rejected at",
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional metadata about the suggestion",
                        verbose_name="metadata",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_suggestion_feedbacks",
                        to="documents.document",
                        verbose_name="document",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who applied or rejected the suggestion",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_suggestion_feedbacks",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI suggestion feedback",
                "verbose_name_plural": "AI suggestion feedbacks",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="aisuggestionfeedback",
            index=models.Index(
                fields=["document", "suggestion_type"],
                name="documents_a_documen_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="aisuggestionfeedback",
            index=models.Index(
                fields=["status", "created_at"],
                name="documents_a_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="aisuggestionfeedback",
            index=models.Index(
                fields=["suggestion_type", "status"],
                name="documents_a_suggest_idx",
            ),
        ),
    ]
