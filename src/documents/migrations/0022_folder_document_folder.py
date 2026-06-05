import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models


def create_default_folder_and_assign(apps, schema_editor):
    """
    Ensure a single default ("Inbox") folder exists and assign every existing
    document (including soft-deleted ones) that has no folder to it.

    This is a safe, idempotent backfill so that an existing installation can be
    upgraded without leaving any document without a folder.
    """
    Folder = apps.get_model("documents", "Folder")
    Document = apps.get_model("documents", "Document")

    default_folder = Folder.objects.filter(is_default=True).order_by("pk").first()
    if default_folder is None:
        default_folder = Folder.objects.create(name="Inbox", is_default=True)

    # The historical Document manager returns all rows (including soft-deleted),
    # which is exactly what we want here.
    Document.objects.filter(folder__isnull=True).update(folder=default_folder)


def reverse_assign(apps, schema_editor):
    # Nothing to undo for the data; the schema reversal drops the column.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0021_widen_workflow_integer_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Folder",
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
                ("name", models.CharField(max_length=128, verbose_name="name")),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Marks this folder as the default folder. Newly "
                            "consumed or unclassified documents are placed here."
                        ),
                        verbose_name="is default folder",
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
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="documents.folder",
                        verbose_name="parent folder",
                    ),
                ),
            ],
            options={
                "verbose_name": "folder",
                "verbose_name_plural": "folders",
                "ordering": ("name",),
            },
        ),
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                fields=("name", "parent", "owner"),
                name="documents_folder_unique_name_parent_owner",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documents",
                to="documents.folder",
                verbose_name="folder",
                help_text=(
                    "The folder this document is organized into. Every document "
                    "should belong to a folder; unclassified documents fall back "
                    "to the default folder."
                ),
            ),
        ),
        migrations.RunPython(
            create_default_folder_and_assign,
            reverse_assign,
        ),
    ]
