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
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict

from django.conf import settings

from documents.models import Document
from documents.utils import IterWrapper
from documents.utils import compute_checksum
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
        self.has_error: bool = False
        self.has_warning: bool = False
        self.has_info: bool = False
        self.document_count: int = 0
        self.document_error_count: int = 0
        self.document_warning_count: int = 0
        self.document_info_count: int = 0
        self.global_warning_count: int = 0

    # -- Recording ----------------------------------------------------------

    def error(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.ERROR, "message": message})
        self.has_error = True
        if doc_pk is not None:
            self.document_count += 1
            self.document_error_count += 1

    def warning(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.WARNING, "message": message})
        self.has_warning = True

        if doc_pk is not None:
            self.document_count += 1
            self.document_warning_count += 1
        else:
            # This is the only type of global message we do right now
            self.global_warning_count += 1

    def info(self, doc_pk: int | None, message: str) -> None:
        self._messages[doc_pk].append({"level": logging.INFO, "message": message})
        self.has_info = True

        if doc_pk is not None:
            self.document_count += 1
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
            self.document_error_count
            + self.document_warning_count
            + self.global_warning_count
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


def _build_present_files() -> set[Path]:
    """Collect all files in MEDIA_ROOT, excluding directories and ignorable files."""
    present_files = {
        x.resolve()
        for x in Path(settings.MEDIA_ROOT).glob("**/*")
        if not x.is_dir() and x.name not in settings.IGNORABLE_FILES
    }

    lockfile = Path(settings.MEDIA_LOCK).resolve()
    present_files.discard(lockfile)

    general_config = GeneralConfig()
    app_logo = general_config.app_logo or settings.APP_LOGO
    if app_logo:
        logo_file = Path(settings.MEDIA_ROOT / Path(app_logo.lstrip("/"))).resolve()
        present_files.discard(logo_file)

    return present_files


def _check_thumbnail(
    doc: Document,
    messages: SanityCheckMessages,
    present_files: set[Path],
) -> None:
    """Verify the thumbnail exists and is readable."""
    # doc.thumbnail_path already returns a resolved Path; no need to re-resolve.
    thumbnail_path: Final[Path] = doc.thumbnail_path
    if not thumbnail_path.is_file():
        messages.error(doc.pk, "Thumbnail of document does not exist.")
        return

    present_files.discard(thumbnail_path)
    try:
        _ = thumbnail_path.read_bytes()
    except OSError as e:
        messages.error(doc.pk, f"Cannot read thumbnail file of document: {e}")


def _check_original(
    doc: Document,
    messages: SanityCheckMessages,
    present_files: set[Path],
) -> None:
    """Verify the original file exists, is readable, and has matching checksum."""
    # doc.source_path already returns a resolved Path; no need to re-resolve.
    source_path: Final[Path] = doc.source_path
    if not source_path.is_file():
        messages.error(doc.pk, "Original of document does not exist.")
        return

    present_files.discard(source_path)
    try:
        checksum = compute_checksum(source_path)
    except OSError as e:
        messages.error(doc.pk, f"Cannot read original file of document: {e}")
    else:
        if checksum != doc.checksum:
            messages.error(
                doc.pk,
                f"Checksum mismatch. Stored: {doc.checksum}, actual: {checksum}.",
            )


def _check_archive(
    doc: Document,
    messages: SanityCheckMessages,
    present_files: set[Path],
) -> None:
    """Verify archive file consistency: checksum/filename pairing and file integrity."""
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
    elif doc.has_archive_version:
        if TYPE_CHECKING:
            assert isinstance(doc.archive_path, Path)
        # doc.archive_path already returns a resolved Path; no need to re-resolve.
        archive_path: Final[Path] = doc.archive_path  # type: ignore[assignment]
        if not archive_path.is_file():
            messages.error(doc.pk, "Archived version of document does not exist.")
            return

        present_files.discard(archive_path)
        try:
            checksum = compute_checksum(archive_path)
        except OSError as e:
            messages.error(
                doc.pk,
                f"Cannot read archive file of document: {e}",
            )
        else:
            if checksum != doc.archive_checksum:
                messages.error(
                    doc.pk,
                    "Checksum mismatch of archived document. "
                    f"Stored: {doc.archive_checksum}, actual: {checksum}.",
                )


def _check_content(doc: Document, messages: SanityCheckMessages) -> None:
    """Flag documents with no OCR content."""
    if not doc.content:
        messages.info(doc.pk, "Document contains no OCR data")


def _check_document(
    doc: Document,
    messages: SanityCheckMessages,
    present_files: set[Path],
) -> None:
    """Run all checks for a single document."""
    _check_thumbnail(doc, messages, present_files)
    _check_original(doc, messages, present_files)
    _check_archive(doc, messages, present_files)
    _check_content(doc, messages)


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
    present_files = _build_present_files()

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
        _check_document(doc, messages, present_files)

    for extra_file in present_files:
        messages.warning(None, f"Orphaned file in media dir: {extra_file}")

    return messages
