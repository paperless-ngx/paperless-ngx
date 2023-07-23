from django.db import migrations, models
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1035_rename_comment_note"),
    ]

    operations = [
        migrations.CreateModel(
            name="Metadata",
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
                    "data",
                    models.JSONField(
                        blank=True,
                        help_text="JSON metadata",
                        verbose_name="data"
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="created",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metadatas",
                        to="documents.document",
                        verbose_name="document",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="metadatas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "metadata",
                "verbose_name_plural": "metadatas",
                "ordering": ("created",),
            },
        ),
    ]
