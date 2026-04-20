"""
Drop and recreate the PaperlessTask table with the new structured schema.

We intentionally drop all existing task data -- the old schema was
string-based and incompatible with the new JSONField result storage.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0018_saved_view_simple_search_rules"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="PaperlessTask"),
        migrations.CreateModel(
            name="PaperlessTask",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="owner",
                    ),
                ),
                (
                    "task_id",
                    models.CharField(
                        help_text="Celery task ID",
                        max_length=72,
                        unique=True,
                        verbose_name="Task ID",
                    ),
                ),
                (
                    "task_type",
                    models.CharField(
                        choices=[
                            ("consume_file", "Consume File"),
                            ("train_classifier", "Train Classifier"),
                            ("sanity_check", "Sanity Check"),
                            ("index_optimize", "Index Optimize"),
                            ("mail_fetch", "Mail Fetch"),
                            ("llm_index", "LLM Index"),
                            ("empty_trash", "Empty Trash"),
                            ("check_workflows", "Check Workflows"),
                            ("bulk_update", "Bulk Update"),
                            ("reprocess_document", "Reprocess Document"),
                            ("build_share_link", "Build Share Link"),
                            ("bulk_delete", "Bulk Delete"),
                        ],
                        db_index=True,
                        help_text="The kind of work being performed",
                        max_length=50,
                        verbose_name="Task Type",
                    ),
                ),
                (
                    "trigger_source",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("web_ui", "Web UI"),
                            ("api_upload", "API Upload"),
                            ("folder_consume", "Folder Consume"),
                            ("email_consume", "Email Consume"),
                            ("system", "System"),
                            ("manual", "Manual"),
                        ],
                        db_index=True,
                        help_text="What initiated this task",
                        max_length=50,
                        verbose_name="Trigger Source",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("started", "Started"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("revoked", "Revoked"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=30,
                        verbose_name="Status",
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Created",
                    ),
                ),
                (
                    "date_started",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Started",
                    ),
                ),
                (
                    "date_done",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Completed",
                    ),
                ),
                (
                    "duration_seconds",
                    models.FloatField(
                        blank=True,
                        help_text="Elapsed time from start to completion",
                        null=True,
                        verbose_name="Duration (seconds)",
                    ),
                ),
                (
                    "wait_time_seconds",
                    models.FloatField(
                        blank=True,
                        help_text="Time from task creation to worker pickup",
                        null=True,
                        verbose_name="Wait Time (seconds)",
                    ),
                ),
                (
                    "input_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Structured input parameters for the task",
                        verbose_name="Input Data",
                    ),
                ),
                (
                    "result_data",
                    models.JSONField(
                        blank=True,
                        help_text="Structured result data from task execution",
                        null=True,
                        verbose_name="Result Data",
                    ),
                ),
                (
                    "acknowledged",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        verbose_name="Acknowledged",
                    ),
                ),
            ],
            options={
                "verbose_name": "Task",
                "verbose_name_plural": "Tasks",
                "ordering": ["-date_created"],
            },
        ),
        migrations.AddIndex(
            model_name="paperlesstask",
            index=models.Index(
                fields=["status", "date_created"],
                name="documents_p_status_8aa687_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="paperlesstask",
            index=models.Index(
                fields=["task_type", "status"],
                name="documents_p_task_ty_e4a93f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="paperlesstask",
            index=models.Index(
                fields=["owner", "acknowledged", "date_created"],
                name="documents_p_owner_i_62c545_idx",
            ),
        ),
    ]
