import hashlib
import logging
from pathlib import Path

from django.conf import settings
from django.db import migrations
from django.db import models

logger = logging.getLogger("paperless.migrations")

_CHUNK_SIZE = 65536  # 64 KiB — avoids loading entire files into memory
_BATCH_SIZE = 500  # documents per bulk_update call
_PROGRESS_INTERVAL = 500  # log a progress line every N documents


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def recompute_checksums(apps, schema_editor):
    """Recompute all document checksums from MD5 to SHA256."""
    Document = apps.get_model("documents", "Document")

    total = Document.objects.count()
    if total == 0:
        return

    logger.info("Recomputing SHA-256 checksums for %d document(s)...", total)

    batch: list = []
    processed = 0

    for doc in Document.objects.only(
        "pk",
        "filename",
        "checksum",
        "archive_filename",
        "archive_checksum",
    ).iterator(chunk_size=_BATCH_SIZE):
        updated_fields: list[str] = []

        # Reconstruct source path the same way Document.source_path does
        fname = str(doc.filename) if doc.filename else f"{doc.pk:07}.pdf"
        source_path = (settings.ORIGINALS_DIR / Path(fname)).resolve()

        if source_path.exists():
            doc.checksum = _sha256(source_path)
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
                doc.archive_checksum = _sha256(archive_path)
                updated_fields.append("archive_checksum")
            else:
                logger.warning(
                    "Document %s: archive file %s not found, checksum not updated.",
                    doc.pk,
                    archive_path,
                )

        if updated_fields:
            batch.append(doc)

        processed += 1

        if len(batch) >= _BATCH_SIZE:
            Document.objects.bulk_update(batch, ["checksum", "archive_checksum"])
            batch.clear()

        if processed % _PROGRESS_INTERVAL == 0:
            logger.info(
                "SHA-256 checksum progress: %d/%d (%d%%)",
                processed,
                total,
                processed * 100 // total,
            )

    if batch:
        Document.objects.bulk_update(batch, ["checksum", "archive_checksum"])

    logger.info(
        "SHA-256 checksum recomputation complete: %d document(s) processed.",
        total,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0015_document_version_index_and_more"),
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
