"""
Sanity checker for the Paperless-ngx document archive.

Verifies that all documents have valid files, correct checksums,
and consistent metadata. Reports orphaned files in the media directory.

Progress display is the caller's responsibility -- pass an ``iter_wrapper``
to wrap the document queryset (e.g., with a progress bar). The default
is an identity function that adds no overhead.
"""

import logging
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict

from django.conf import settings

from documents.integrity import ExpectedFile
from documents.integrity import Manifest
from documents.integrity import scan_files
from documents.models import Document
from documents.utils import IterWrapper
from documents.utils import identity
from paperless.config import GeneralConfig

logger = logging.getLogger("paperless.sanity_checker")


class MessageEntry(TypedDict):
    """A single sanity check message with its severity level."""

    level: int
    message: str


class SanityCheckMessages:
    """Collects sanity check messages grouped by document primary key.

    Messages are categorized as error, warning, or info. ``None`` is used
    as the key for messages not associated with a specific document
    (e.g., orphaned files).
    """

    def __init__(self) -> None:
        self._messages: dict[int | None, list[MessageEntry]] = defaultdict(list)
        self._document_pks: set[int] = set()
        self._document_error_pks: set[int] = set()
        self._document_warning_pks: set[int] = set()
        self._document_info_pks: set[int] = set()
        self._document_error_issue_count: int = 0
        self._document_warning_issue_count: int = 0
        self.has_error: bool = False
        self.has_warning: bool = False
        self.has_info: bool = False
        self.document_count: int = 0
        self.document_error_count: int = 0
        self.document_warning_count: int = 0
        self.document_info_count: int = 0
        self.global_warning_count: int = 0
        self.global_error_count: int = 0

    # -- Recording ----------------------------------------------------------

    def _add_document_issue(self, doc_pk: int, document_pks: set[int]) -> bool:
        if doc_pk not in self._document_pks:
            self._document_pks.add(doc_pk)
            self.document_count += 1

        if doc_pk in document_pks:
            return False

        document_pks.add(doc_pk)
        return True

    def error(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.ERROR, "message": message})
        self.has_error = True
        if doc_pk is not None:
            self._document_error_issue_count += 1
            if self._add_document_issue(doc_pk, self._document_error_pks):
                self.document_error_count += 1
        else:
            self.global_error_count += 1

    def warning(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.WARNING, "message": message})
        self.has_warning = True

        if doc_pk is not None:
            self._document_warning_issue_count += 1
            if self._add_document_issue(doc_pk, self._document_warning_pks):
                self.document_warning_count += 1
        else:
            # This is the only type of global message we do right now
            self.global_warning_count += 1

    def info(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.INFO, "message": message})
        self.has_info = True

        if doc_pk is not None and self._add_document_issue(
            doc_pk,
            self._document_info_pks,
        ):
            self.document_info_count += 1

    # -- Iteration / query --------------------------------------------------

    def document_pks(self) -> list[int | None]:
        """Return all document PKs (including None for global messages)."""
        return list(self._messages.keys())

    def iter_messages(self) -> Iterator[tuple[int | None, list[MessageEntry]]]:
        """Iterate over (doc_pk, messages) pairs."""
        yield from self._messages.items()

    def __getitem__(self, item: int | None) -> list[MessageEntry]:
        return self._messages[item]

    # -- Summarize Helpers --------------------------------------------------

    @property
    def has_global_issues(self) -> bool:
        return None in self._messages

    @property
    def total_issue_count(self) -> int:
        """Total number of error and warning messages across all documents and global."""
        return (
            self._document_error_issue_count
            + self._document_warning_issue_count
            + self.global_warning_count
            + self.global_error_count
        )

    # -- Logging output (used by Celery task path) --------------------------

    def log_messages(self) -> None:
        """Write all messages to the ``paperless.sanity_checker`` logger.

        This is the output path for headless / Celery execution.
        Management commands use Rich rendering instead.
        """
        if len(self._messages) == 0:
            logger.info("Sanity checker detected no issues.")
            return

        doc_pks = [pk for pk in self._messages if pk is not None]
        titles: dict[int, str] = {}
        if doc_pks:
            titles = dict(
                Document.global_objects.filter(pk__in=doc_pks)
                .only("pk", "title")
                .values_list("pk", "title"),
            )

        for doc_pk, entries in self._messages.items():
            if doc_pk is not None:
                title = titles.get(doc_pk, "Unknown")
                logger.info(
                    "Detected following issue(s) with document #%s, titled %s",
                    doc_pk,
                    title,
                )
            for msg in entries:
                logger.log(msg["level"], msg["message"])


class SanityCheckFailedException(Exception):
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_archive_metadata(doc: Document, messages: SanityCheckMessages) -> bool:
    """Check archive metadata; return whether the archive file should be scanned."""
    if doc.archive_checksum is not None and doc.archive_filename is None:
        messages.error(
            doc.pk,
            "Document has an archive file checksum, but no archive filename.",
        )
    elif doc.archive_checksum is None and doc.archive_filename is not None:
        messages.error(
            doc.pk,
            "Document has an archive file, but its checksum is missing.",
        )
    else:
        return doc.has_archive_version
    return False


def _check_content(doc: Document, messages: SanityCheckMessages) -> None:
    """Flag documents with no OCR content."""
    if not doc.content:
        messages.info(doc.pk, "Document contains no OCR data")


def _record_findings(manifest: Manifest, messages: SanityCheckMessages) -> None:
    for finding in scan_files(manifest):
        index = finding["file_index"]
        code = finding["code"]
        if index is None:
            if code == "orphan":
                messages.warning(None, f"Orphaned file in media dir: {finding['path']}")
            else:
                messages.error(
                    None,
                    f"Unsafe path in media dir: {finding['path']}: {finding['detail']}",
                )
            continue
        file = manifest["files"][index]
        kind = file["kind"]
        doc_pk = file["document_id"]
        if code == "missing":
            label = {
                "original": "Original",
                "archive": "Archived version",
                "thumbnail": "Thumbnail",
            }[kind]
            messages.error(doc_pk, f"{label} of document does not exist.")
        elif code == "unreadable":
            messages.error(
                doc_pk,
                f"Cannot read {kind} file of document: {finding['detail']}",
            )
        elif code == "unsafe_path":
            messages.error(
                doc_pk,
                f"Unsafe path for {kind} file of document: {finding['path']}: {finding['detail']}",
            )
        else:
            prefix = (
                "Checksum mismatch of archived document"
                if kind == "archive"
                else "Checksum mismatch"
            )
            messages.error(
                doc_pk,
                f"{prefix}. Stored: {file['checksum']}, actual: {finding['actual_checksum']}.",
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def check_sanity(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
) -> SanityCheckMessages:
    """Run a full sanity check on the document archive.

    Args:
        iter_wrapper: A callable that wraps the document iterable, e.g.,
            for progress bar display. Defaults to identity (no wrapping).

    Returns:
        A SanityCheckMessages instance containing all detected issues.
    """
    messages = SanityCheckMessages()
    files: list[ExpectedFile] = []

    documents = Document.global_objects.only(
        "pk",
        "filename",
        "mime_type",
        "checksum",
        "archive_checksum",
        "archive_filename",
        "content",
    ).iterator(chunk_size=500)
    for doc in iter_wrapper(documents):
        # Do not resolve model paths in Python: the scanner owns symlink safety.
        files.extend(
            [
                ExpectedFile(
                    document_id=doc.pk,
                    kind="thumbnail",
                    path=str((settings.THUMBNAIL_DIR / f"{doc.pk:07}.webp").absolute()),
                    checksum="",
                ),
                ExpectedFile(
                    document_id=doc.pk,
                    kind="original",
                    path=str(
                        (
                            settings.ORIGINALS_DIR
                            / (doc.filename or f"{doc.pk:07}{doc.file_type}")
                        ).absolute(),
                    ),
                    checksum=doc.checksum,
                ),
            ],
        )
        if _check_archive_metadata(doc, messages):
            files.append(
                ExpectedFile(
                    document_id=doc.pk,
                    kind="archive",
                    path=str(
                        (settings.ARCHIVE_DIR / str(doc.archive_filename)).absolute(),
                    ),
                    checksum=doc.archive_checksum or "",
                ),
            )
        _check_content(doc, messages)

    exclusions = [str(Path(settings.MEDIA_LOCK).absolute())]
    app_logo = GeneralConfig().app_logo or settings.APP_LOGO
    if app_logo:
        exclusions.append(
            str((Path(settings.MEDIA_ROOT) / app_logo.lstrip("/")).absolute()),
        )
    manifest = Manifest(
        version=1,
        media_root=str(Path(settings.MEDIA_ROOT).absolute()),
        checksum_algorithm="sha256",
        files=files,
        ignored_filenames=list(settings.IGNORABLE_FILES),
        excluded_paths=exclusions,
    )
    _record_findings(manifest, messages)

    return messages
