import hashlib
import logging
import os
from collections import defaultdict

from django.conf import settings
from documents.models import Document
from tqdm import tqdm


class SanityCheckMessages:
    def __init__(self):
        self._messages = defaultdict(list)
        self.has_error = False
        self.has_warning = False

    def error(self, doc_pk, message):
        self._messages[doc_pk].append({"level": logging.ERROR, "message": message})
        self.has_error = True

    def warning(self, doc_pk, message):
        self._messages[doc_pk].append({"level": logging.WARNING, "message": message})
        self.has_warning = True

    def info(self, doc_pk, message):
        self._messages[doc_pk].append({"level": logging.INFO, "message": message})

    def log_messages(self):
        logger = logging.getLogger("paperless.sanity_checker")

        if len(self._messages) == 0:
            logger.info("Sanity checker detected no issues.")
        else:

            # Query once
            all_docs = Document.objects.all()

            for doc_pk in self._messages:
                if doc_pk is not None:
                    doc = all_docs.get(pk=doc_pk)
                    logger.info(f"Document: {doc.pk}, title: {doc.title}")
                for msg in self._messages[doc_pk]:
                    logger.log(msg["level"], msg["message"])

    def __len__(self):
        return len(self._messages)

    def __getitem__(self, item):
        return self._messages[item]


class SanityCheckFailedException(Exception):
    pass


def check_sanity(progress=False) -> SanityCheckMessages:
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
            messages.error(doc.pk, "Thumbnail of document does not exist.")
        else:
            if os.path.normpath(doc.thumbnail_path) in present_files:
                present_files.remove(os.path.normpath(doc.thumbnail_path))
            try:
                with doc.thumbnail_file as f:
                    f.read()
            except OSError as e:
                messages.error(doc.pk, f"Cannot read thumbnail file of document: {e}")

        # Check sanity of the original file
        # TODO: extract method
        if not os.path.isfile(doc.source_path):
            messages.error(doc.pk, "Original of document does not exist.")
        else:
            if os.path.normpath(doc.source_path) in present_files:
                present_files.remove(os.path.normpath(doc.source_path))
            try:
                with doc.source_file as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
            except OSError as e:
                messages.error(doc.pk, f"Cannot read original file of document: {e}")
            else:
                if not checksum == doc.checksum:
                    messages.error(
                        doc.pk,
                        "Checksum mismatch. "
                        f"Stored: {doc.checksum}, actual: {checksum}.",
                    )

        # Check sanity of the archive file.
        if doc.archive_checksum and not doc.archive_filename:
            messages.error(
                doc.pk,
                "Document has an archive file checksum, but no archive filename.",
            )
        elif not doc.archive_checksum and doc.archive_filename:
            messages.error(
                doc.pk,
                "Document has an archive file, but its checksum is missing.",
            )
        elif doc.has_archive_version:
            if not os.path.isfile(doc.archive_path):
                messages.error(doc.pk, "Archived version of document does not exist.")
            else:
                if os.path.normpath(doc.archive_path) in present_files:
                    present_files.remove(os.path.normpath(doc.archive_path))
                try:
                    with doc.archive_file as f:
                        checksum = hashlib.md5(f.read()).hexdigest()
                except OSError as e:
                    messages.error(
                        doc.pk,
                        f"Cannot read archive file of document : {e}",
                    )
                else:
                    if not checksum == doc.archive_checksum:
                        messages.error(
                            doc.pk,
                            "Checksum mismatch of archived document. "
                            f"Stored: {doc.archive_checksum}, "
                            f"actual: {checksum}.",
                        )

        # other document checks
        if not doc.content:
            messages.info(doc.pk, "Document has no content.")

    for extra_file in present_files:
        messages.warning(None, f"Orphaned file in media dir: {extra_file}")

    return messages
