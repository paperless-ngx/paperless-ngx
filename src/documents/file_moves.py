"""
Document file moves, coalesced to once per unit of work.

Every save that can change a document's generated filename asks for a file
move through request_file_move(). Inside a scope opened by defer_file_moves()
(a request, a Celery task, the consumer, or a per-item command step) the
request is only recorded, and the outermost scope moves each recorded document
once, after its own writes have committed. Outside any scope the move happens
immediately.

The mover always takes media.lock first and then reads the document fresh, so
it starts from the latest committed state and never waits on media.lock while
its own transaction holds document rows.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Final

from django.conf import settings
from django.db import DatabaseError
from django.db import transaction
from django.utils import timezone
from filelock import Timeout

from documents.caching import clear_document_caches
from documents.file_handling import create_source_path_directory
from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.file_handling import generate_unique_filename
from documents.media_lock import media_lock
from documents.models import Document
from documents.utils import compute_checksum

logger = logging.getLogger("paperless.handlers")

MEDIA_LOCK_TIMEOUT_SECONDS: Final[int] = 300


class CannotMoveFilesException(Exception):
    pass


def in_user_transaction() -> bool:
    """
    True when the default connection is inside an atomic block that was not
    created by Django's test case machinery.

    Django marks the atomic blocks TestCase (and pytest-django) wrap around
    each test with _from_testcase, the same flag it uses for durable checks.
    Ignoring them keeps tests on the same path as production.
    """
    connection = transaction.get_connection()
    return any(not block._from_testcase for block in connection.atomic_blocks)


def _path_matches_checksum(path: Path, checksum: str | None) -> bool:
    if checksum is None or not path.is_file():
        return False

    return compute_checksum(path) == checksum


def move_files_for_document(pk: int) -> Document | None:
    """
    Move the document's original and archive to the paths its current
    committed state generates, then do the same for its versions.

    Returns the fresh instance with its final filename columns, or None when
    the document does not exist, has no filename yet, or the lock timed out.
    """
    # Cheap check without the lock: most saves during consumption happen
    # before the file is placed. filename, once set, is never cleared, so a
    # non-empty value here stays non-empty under the lock. This goes through
    # values_list() (not the manager's filter()) on purpose.
    filename = (
        Document.global_objects.values_list("filename", flat=True).filter(pk=pk).first()
    )
    if not filename:
        return None

    try:
        with media_lock(timeout=MEDIA_LOCK_TIMEOUT_SECONDS):
            try:
                document = Document.global_objects.get(pk=pk)
            except Document.DoesNotExist:
                logger.debug(f"Document {pk} no longer exists, skipping file move")
                return None
            _move_document_files(document)
    except Timeout:
        logger.error(
            f"Timed out after {MEDIA_LOCK_TIMEOUT_SECONDS}s waiting for "
            f"{settings.MEDIA_LOCK} to move files of document {pk}; the file "
            f"keeps its current name and will be renamed on its next save",
        )
        return None

    # Keep version files in sync with root
    if document.root_document_id is None:
        for version_pk in Document.objects.filter(root_document_id=pk).values_list(
            "pk",
            flat=True,
        ):
            move_files_for_document(version_pk)

    return document


def _validate_move(
    document: Document,
    old_path: Path,
    new_path: Path,
    root: Path,
) -> None:
    if not new_path.is_relative_to(root):
        msg = (
            f"Document {document!s}: Refusing to move file outside root {root}: "
            f"{new_path}."
        )
        logger.warning(msg)
        raise CannotMoveFilesException(msg)

    if not old_path.is_file():
        # Can't do anything if the old file does not exist anymore.
        msg = f"Document {document!s}: File {old_path} doesn't exist."
        logger.fatal(msg)
        raise CannotMoveFilesException(msg)

    if new_path.is_file():
        # Can't do anything if the new file already exists. Skip updating file.
        msg = f"Document {document!s}: Cannot rename file since target path {new_path} already exists."
        logger.warning(msg)
        raise CannotMoveFilesException(msg)


def _move_document_files(document: Document) -> None:
    try:
        old_filename = document.filename
        old_source_path = document.source_path
        move_original = False
        original_already_moved = False

        old_archive_filename = document.archive_filename
        old_archive_path = document.archive_path
        move_archive = False
        archive_already_moved = False

        candidate_filename = generate_filename(document)
        if len(str(candidate_filename)) > Document.MAX_STORED_FILENAME_LENGTH:
            msg = (
                f"Document {document!s}: Generated filename exceeds db path "
                f"limit ({len(str(candidate_filename))} > "
                f"{Document.MAX_STORED_FILENAME_LENGTH}): {candidate_filename!s}"
            )
            logger.warning(msg)
            raise CannotMoveFilesException(msg)

        candidate_source_path = (settings.ORIGINALS_DIR / candidate_filename).resolve()
        if candidate_filename == Path(old_filename):
            new_filename = Path(old_filename)
        elif (
            candidate_source_path.exists() and candidate_source_path != old_source_path
        ):
            if not old_source_path.is_file() and _path_matches_checksum(
                candidate_source_path,
                document.checksum,
            ):
                new_filename = candidate_filename
                original_already_moved = True
            else:
                # Only fall back to unique search when there is an actual conflict
                new_filename = generate_unique_filename(document)
        else:
            new_filename = candidate_filename

        # Need to convert to string to be able to save it to the db
        document.filename = str(new_filename)
        move_original = old_filename != document.filename and not original_already_moved

        if document.has_archive_version:
            archive_candidate = generate_filename(document, archive_filename=True)
            if len(str(archive_candidate)) > Document.MAX_STORED_FILENAME_LENGTH:
                msg = (
                    f"Document {document!s}: Generated archive filename exceeds "
                    f"db path limit ({len(str(archive_candidate))} > "
                    f"{Document.MAX_STORED_FILENAME_LENGTH}): {archive_candidate!s}"
                )
                logger.warning(msg)
                raise CannotMoveFilesException(msg)
            archive_candidate_path = (
                settings.ARCHIVE_DIR / archive_candidate
            ).resolve()
            if archive_candidate == Path(old_archive_filename):
                new_archive_filename = Path(old_archive_filename)
            elif (
                archive_candidate_path.exists()
                and archive_candidate_path != old_archive_path
            ):
                if not old_archive_path.is_file() and _path_matches_checksum(
                    archive_candidate_path,
                    document.archive_checksum,
                ):
                    new_archive_filename = archive_candidate
                    archive_already_moved = True
                else:
                    new_archive_filename = generate_unique_filename(
                        document,
                        archive_filename=True,
                    )
            else:
                new_archive_filename = archive_candidate

            document.archive_filename = str(new_archive_filename)

            move_archive = (
                old_archive_filename != document.archive_filename
                and not archive_already_moved
            )
        else:
            move_archive = False

        if not move_original and not move_archive:
            updates: dict[str, object] = {}
            if old_filename != document.filename:
                updates["filename"] = document.filename
            if old_archive_filename != document.archive_filename:
                updates["archive_filename"] = document.archive_filename
            if updates:
                # global_objects so a trashed document's path is fixed too.
                # modified only changes when a filename column changes.
                updates["modified"] = timezone.now()
                # Don't save() here to prevent infinite recursion.
                Document.global_objects.filter(pk=document.pk).update(**updates)
            return

        if move_original:
            _validate_move(
                document,
                old_source_path,
                document.source_path,
                settings.ORIGINALS_DIR,
            )
            create_source_path_directory(document.source_path)
            shutil.move(old_source_path, document.source_path)

        if move_archive:
            _validate_move(
                document,
                old_archive_path,
                document.archive_path,
                settings.ARCHIVE_DIR,
            )
            create_source_path_directory(document.archive_path)
            shutil.move(old_archive_path, document.archive_path)

        # Don't save() here to prevent infinite recursion.
        Document.global_objects.filter(pk=document.pk).update(
            filename=document.filename,
            archive_filename=document.archive_filename,
            modified=timezone.now(),
        )
        # Clear any caching for this document.  Slightly overkill, but not terrible
        clear_document_caches(document.pk)

    except (OSError, DatabaseError, CannotMoveFilesException) as e:
        logger.warning(f"Exception during file handling: {e}")
        # This happens when either:
        #  - moving the files failed due to file system errors
        #  - saving to the database failed due to database errors
        # In both cases, we need to revert to the original state.

        # Try to move files to their original location.
        try:
            if move_original and document.source_path.is_file():
                logger.info("Restoring previous original path")
                shutil.move(document.source_path, old_source_path)

            if move_archive and document.archive_path.is_file():
                logger.info("Restoring previous archive path")
                shutil.move(document.archive_path, old_archive_path)

        except Exception:
            # This is fine, since:
            # A: if we managed to move source from A to B, we will also
            #  manage to move it from B to A. If not, we have a serious
            #  issue that's going to get caught by the santiy checker.
            #  All files remain in place and will never be overwritten,
            #  so this is not the end of the world.
            # B: if moving the original file failed, nothing has changed
            #  anyway.
            pass

        # restore old values on the document
        document.filename = old_filename
        document.archive_filename = old_archive_filename

    # finally, remove any empty sub folders. This will do nothing if
    # something has failed above.
    if not old_source_path.is_file():
        delete_empty_directories(
            Path(old_source_path).parent,
            root=settings.ORIGINALS_DIR,
        )

    if document.has_archive_version and not old_archive_path.is_file():
        delete_empty_directories(
            Path(old_archive_path).parent,
            root=settings.ARCHIVE_DIR,
        )


def request_file_move(document: Document) -> None:
    """
    Ask for the document's files to follow its current committed state.

    Moves immediately and copies only the final filename columns onto the
    caller's instance, so code that saves and then reads source_path keeps
    working without any other in-memory field being touched.
    """
    moved = move_files_for_document(document.pk)
    if moved is not None:
        document.filename = moved.filename
        document.archive_filename = moved.archive_filename
