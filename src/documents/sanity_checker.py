import hashlib
import logging
import os

from django.conf import settings
from tqdm import tqdm

from documents.models import Document


class SanityCheckMessages:

    def __init__(self):
        self._messages = []

    def error(self, message):
        self._messages.append({"level": logging.ERROR, "message": message})

    def warning(self, message):
        self._messages.append({"level": logging.WARNING, "message": message})

    def info(self, message):
        self._messages.append({"level": logging.INFO, "message": message})

    def log_messages(self):
        logger = logging.getLogger("paperless.sanity_checker")

        if len(self._messages) == 0:
            logger.info("Sanity checker detected no issues.")
        else:
            for msg in self._messages:
                logger.log(msg['level'], msg['message'])

    def __len__(self):
        return len(self._messages)

    def __getitem__(self, item):
        return self._messages[item]

    def has_error(self):
        return any([msg['level'] == logging.ERROR for msg in self._messages])

    def has_warning(self):
        return any([msg['level'] == logging.WARNING for msg in self._messages])


class SanityCheckFailedException(Exception):
    pass


def check_sanity(progress=False):
    messages = SanityCheckMessages()

    present_files = []
    for root, subdirs, files in os.walk(settings.MEDIA_ROOT):
        for f in files:
            present_files.append(os.path.normpath(os.path.join(root, f)))

    lockfile = os.path.normpath(settings.MEDIA_LOCK)
    if lockfile in present_files:
        present_files.remove(lockfile)

    for doc in tqdm(Document.objects.all(), disable=not progress):
        # Check sanity of the thumbnail
        if not os.path.isfile(doc.thumbnail_path):
            messages.error(f"Thumbnail of document {doc.pk} does not exist.")
        else:
            if os.path.normpath(doc.thumbnail_path) in present_files:
                present_files.remove(os.path.normpath(doc.thumbnail_path))
            try:
                with doc.thumbnail_file as f:
                    f.read()
            except OSError as e:
                messages.error(
                    f"Cannot read thumbnail file of document {doc.pk}: {e}"
                )

        # Check sanity of the original file
        # TODO: extract method
        if not os.path.isfile(doc.source_path):
            messages.error(f"Original of document {doc.pk} does not exist.")
        else:
            if os.path.normpath(doc.source_path) in present_files:
                present_files.remove(os.path.normpath(doc.source_path))
            try:
                with doc.source_file as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
            except OSError as e:
                messages.error(
                    f"Cannot read original file of document {doc.pk}: {e}")
            else:
                if not checksum == doc.checksum:
                    messages.error(
                        f"Checksum mismatch of document {doc.pk}. "
                        f"Stored: {doc.checksum}, actual: {checksum}."
                    )

        # Check sanity of the archive file.
        if doc.archive_checksum and not doc.archive_filename:
            messages.error(
                f"Document {doc.pk} has an archive file checksum, but no "
                f"archive filename."
            )
        elif not doc.archive_checksum and doc.archive_filename:
            messages.error(
                f"Document {doc.pk} has an archive file, but its checksum is "
                f"missing."
            )
        elif doc.has_archive_version:
            if not os.path.isfile(doc.archive_path):
                messages.error(
                    f"Archived version of document {doc.pk} does not exist."
                )
            else:
                if os.path.normpath(doc.archive_path) in present_files:
                    present_files.remove(os.path.normpath(doc.archive_path))
                try:
                    with doc.archive_file as f:
                        checksum = hashlib.md5(f.read()).hexdigest()
                except OSError as e:
                    messages.error(
                        f"Cannot read archive file of document {doc.pk}: {e}"
                    )
                else:
                    if not checksum == doc.archive_checksum:
                        messages.error(
                            f"Checksum mismatch of archived document "
                            f"{doc.pk}. "
                            f"Stored: {doc.archive_checksum}, "
                            f"actual: {checksum}."
                        )

        # other document checks
        if not doc.content:
            messages.info(f"Document {doc.pk} has no content.")

    for extra_file in present_files:
        messages.warning(f"Orphaned file in media dir: {extra_file}")

    return messages
