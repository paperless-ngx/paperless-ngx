import hashlib
import logging
from pathlib import Path

from django.conf import settings
from django.db import migrations
from django.db import models

logger = logging.getLogger(__name__)


def recompute_checksums(apps, schema_editor):
    """Recompute all document checksums from MD5 to SHA256."""
    Document = apps.get_model("documents", "Document")

    for doc in Document.objects.all().iterator():
        updated_fields = []

        # Reconstruct source path the same way Document.source_path does
        fname = str(doc.filename) if doc.filename else f"{doc.pk:07}.pdf"
        source_path = (settings.ORIGINALS_DIR / Path(fname)).resolve()

        if source_path.exists():
            doc.checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
            updated_fields.append("checksum")
        else:
            logger.warning(
                "Document %s: original file %s not found, checksum not updated.",
                doc.pk,
                source_path,
            )

        # Mirror Document.has_archive_version: archive_filename is not None
        if doc.archive_filename is not None:
            archive_path = (
                settings.ARCHIVE_DIR / Path(str(doc.archive_filename))
            ).resolve()
            if archive_path.exists():
                doc.archive_checksum = hashlib.sha256(
                    archive_path.read_bytes(),
                ).hexdigest()
                updated_fields.append("archive_checksum")
            else:
                logger.warning(
                    "Document %s: archive file %s not found, checksum not updated.",
                    doc.pk,
                    archive_path,
                )

        if updated_fields:
            doc.save(update_fields=updated_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_document_version_index_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="checksum",
            field=models.CharField(
                editable=False,
                help_text="The checksum of the original document.",
                max_length=64,
                verbose_name="checksum",
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="archive_checksum",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="The checksum of the archived document.",
                max_length=64,
                null=True,
                verbose_name="archive checksum",
            ),
        ),
        migrations.RunPython(recompute_checksums, migrations.RunPython.noop),
    ]
