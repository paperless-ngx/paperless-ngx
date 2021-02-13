import hashlib
import os

from django.conf import settings
from tqdm import tqdm

from documents.models import Document


class SanityMessage:
    message = None


class SanityWarning(SanityMessage):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Warning: {self.message}"


class SanityError(SanityMessage):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"ERROR: {self.message}"


class SanityFailedError(Exception):

    def __init__(self, messages):
        self.messages = messages

    def __str__(self):
        message_string = "\n".join([str(m) for m in self.messages])
        return (
            f"The following issuse were found by the sanity checker:\n"
            f"{message_string}\n\n===============\n\n")


def check_sanity(progress=False):
    messages = []

    present_files = []
    for root, subdirs, files in os.walk(settings.MEDIA_ROOT):
        for f in files:
            present_files.append(os.path.normpath(os.path.join(root, f)))

    lockfile = os.path.normpath(settings.MEDIA_LOCK)
    if lockfile in present_files:
        present_files.remove(lockfile)

    if progress:
        docs = tqdm(Document.objects.all())
    else:
        docs = Document.objects.all()

    for doc in docs:
        # Check sanity of the thumbnail
        if not os.path.isfile(doc.thumbnail_path):
            messages.append(SanityError(
                f"Thumbnail of document {doc.pk} does not exist."))
        else:
            if os.path.normpath(doc.thumbnail_path) in present_files:
                present_files.remove(os.path.normpath(doc.thumbnail_path))
            try:
                with doc.thumbnail_file as f:
                    f.read()
            except OSError as e:
                messages.append(SanityError(
                    f"Cannot read thumbnail file of document {doc.pk}: {e}"
                ))

        # Check sanity of the original file
        # TODO: extract method
        if not os.path.isfile(doc.source_path):
            messages.append(SanityError(
                f"Original of document {doc.pk} does not exist."))
        else:
            if os.path.normpath(doc.source_path) in present_files:
                present_files.remove(os.path.normpath(doc.source_path))
            try:
                with doc.source_file as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
            except OSError as e:
                messages.append(SanityError(
                    f"Cannot read original file of document {doc.pk}: {e}"))
            else:
                if not checksum == doc.checksum:
                    messages.append(SanityError(
                        f"Checksum mismatch of document {doc.pk}. "
                        f"Stored: {doc.checksum}, actual: {checksum}."
                    ))

        # Check sanity of the archive file.
        if doc.archive_checksum and not doc.archive_filename:
            messages.append(SanityError(
                f"Document {doc.pk} has an archive file checksum, but no "
                f"archive filename."
            ))
        elif not doc.archive_checksum and doc.archive_filename:
            messages.append(SanityError(
                f"Document {doc.pk} has an archive file, but its checksum is "
                f"missing."
            ))
        elif doc.has_archive_version:
            if not os.path.isfile(doc.archive_path):
                messages.append(SanityError(
                    f"Archived version of document {doc.pk} does not exist."
                ))
            else:
                if os.path.normpath(doc.archive_path) in present_files:
                    present_files.remove(os.path.normpath(doc.archive_path))
                try:
                    with doc.archive_file as f:
                        checksum = hashlib.md5(f.read()).hexdigest()
                except OSError as e:
                    messages.append(SanityError(
                        f"Cannot read archive file of document {doc.pk}: {e}"
                    ))
                else:
                    if not checksum == doc.archive_checksum:
                        messages.append(SanityError(
                            f"Checksum mismatch of archived document "
                            f"{doc.pk}. "
                            f"Stored: {doc.checksum}, actual: {checksum}."
                        ))

        # other document checks
        if not doc.content:
            messages.append(SanityWarning(
                f"Document {doc.pk} has no content."
            ))

    for extra_file in present_files:
        messages.append(SanityWarning(
            f"Orphaned file in media dir: {extra_file}"
        ))

    return messages
