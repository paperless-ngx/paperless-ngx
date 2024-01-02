import logging
import os
from collections import defaultdict
from pathlib import PurePath

import pathvalidate
from django.conf import settings
from django.template.defaultfilters import slugify
from django.utils import timezone

from documents.models import Document

logger = logging.getLogger("paperless.filehandling")


class defaultdictNoStr(defaultdict):
    def __str__(self):
        raise ValueError("Don't use {tags} directly.")


def create_source_path_directory(source_path):
    os.makedirs(os.path.dirname(source_path), exist_ok=True)


def delete_empty_directories(directory, root):
    if not os.path.isdir(directory):
        return

    # Go up in the directory hierarchy and try to delete all directories
    directory = os.path.normpath(directory)
    root = os.path.normpath(root)

    if not directory.startswith(root + os.path.sep):
        # don't do anything outside our originals folder.

        # append os.path.set so that we avoid these cases:
        #   directory = /home/originals2/test
        #   root = /home/originals ("/" gets appended and startswith fails)
        return

    while directory != root:
        if not os.listdir(directory):
            # it's empty
            try:
                os.rmdir(directory)
            except OSError:
                # whatever. empty directories aren't that bad anyway.
                return
        else:
            # it's not empty.
            return

        # go one level up
        directory = os.path.normpath(os.path.dirname(directory))


def many_to_dictionary(field):
    # Converts ManyToManyField to dictionary by assuming, that field
    # entries contain an _ or - which will be used as a delimiter
    mydictionary = dict()

    for index, t in enumerate(field.all()):
        # Populate tag names by index
        mydictionary[index] = slugify(t.name)

        # Find delimiter
        delimiter = t.name.find("_")

        if delimiter == -1:
            delimiter = t.name.find("-")

        if delimiter == -1:
            continue

        key = t.name[:delimiter]
        value = t.name[delimiter + 1 :]

        mydictionary[slugify(key)] = slugify(value)

    return mydictionary


def generate_unique_filename(doc, archive_filename=False):
    """
    Generates a unique filename for doc in settings.ORIGINALS_DIR.

    The returned filename is guaranteed to be either the current filename
    of the document if unchanged, or a new filename that does not correspondent
    to any existing files. The function will append _01, _02, etc to the
    filename before the extension to avoid conflicts.

    If archive_filename is True, return a unique archive filename instead.

    """
    if archive_filename:
        old_filename = doc.archive_filename
        root = settings.ARCHIVE_DIR
    else:
        old_filename = doc.filename
        root = settings.ORIGINALS_DIR

    # If generating archive filenames, try to make a name that is similar to
    # the original filename first.

    if archive_filename and doc.filename:
        new_filename = os.path.splitext(doc.filename)[0] + ".pdf"
        if new_filename == old_filename or not os.path.exists(
            os.path.join(root, new_filename),
        ):
            return new_filename

    counter = 0

    while True:
        new_filename = generate_filename(
            doc,
            counter,
            archive_filename=archive_filename,
        )
        if new_filename == old_filename:
            # still the same as before.
            return new_filename

        if os.path.exists(os.path.join(root, new_filename)):
            counter += 1
        else:
            return new_filename


def generate_filename(
    doc: Document,
    counter=0,
    append_gpg=True,
    archive_filename=False,
):
    path = ""
    filename_format = settings.FILENAME_FORMAT

    try:
        if doc.storage_path is not None:
            logger.debug(
                f"Document has storage_path {doc.storage_path.id} "
                f"({doc.storage_path.path}) set",
            )
            filename_format = doc.storage_path.path

        if filename_format is not None:
            tags = defaultdictNoStr(
                lambda: slugify(None),
                many_to_dictionary(doc.tags),
            )

            tag_list = pathvalidate.sanitize_filename(
                ",".join(
                    sorted(tag.name for tag in doc.tags.all()),
                ),
                replacement_text="-",
            )

            no_value_default = "-none-"

            if doc.correspondent:
                correspondent = pathvalidate.sanitize_filename(
                    doc.correspondent.name,
                    replacement_text="-",
                )
            else:
                correspondent = no_value_default

            if doc.document_type:
                document_type = pathvalidate.sanitize_filename(
                    doc.document_type.name,
                    replacement_text="-",
                )
            else:
                document_type = no_value_default

            if doc.archive_serial_number:
                asn = str(doc.archive_serial_number)
            else:
                asn = no_value_default

            if doc.owner is not None:
                owner_username_str = str(doc.owner.username)
            else:
                owner_username_str = no_value_default

            if doc.original_filename is not None:
                # No extension
                original_name = PurePath(doc.original_filename).with_suffix("").name
            else:
                original_name = no_value_default

            # Convert UTC database datetime to localized date
            local_added = timezone.localdate(doc.added)
            local_created = timezone.localdate(doc.created)

            path = filename_format.format(
                title=pathvalidate.sanitize_filename(doc.title, replacement_text="-"),
                correspondent=correspondent,
                document_type=document_type,
                created=local_created.isoformat(),
                created_year=local_created.strftime("%Y"),
                created_year_short=local_created.strftime("%y"),
                created_month=local_created.strftime("%m"),
                created_month_name=local_created.strftime("%B"),
                created_month_name_short=local_created.strftime("%b"),
                created_day=local_created.strftime("%d"),
                added=local_added.isoformat(),
                added_year=local_added.strftime("%Y"),
                added_year_short=local_added.strftime("%y"),
                added_month=local_added.strftime("%m"),
                added_month_name=local_added.strftime("%B"),
                added_month_name_short=local_added.strftime("%b"),
                added_day=local_added.strftime("%d"),
                asn=asn,
                tags=tags,
                tag_list=tag_list,
                owner_username=owner_username_str,
                original_name=original_name,
                doc_pk=f"{doc.pk:07}",
            ).strip()

            if settings.FILENAME_FORMAT_REMOVE_NONE:
                path = path.replace("/-none-/", "/")  # remove empty directories
                path = path.replace(" -none-", "")  # remove when spaced, with space
                path = path.replace("-none-", "")  # remove rest of the occurences

            path = path.replace("-none-", "none")  # backward compatibility
            path = path.strip(os.sep)

    except (ValueError, KeyError, IndexError):
        logger.warning(
            f"Invalid filename_format '{filename_format}', falling back to default",
        )

    counter_str = f"_{counter:02}" if counter else ""

    filetype_str = ".pdf" if archive_filename else doc.file_type

    if len(path) > 0:
        filename = f"{path}{counter_str}{filetype_str}"
    else:
        filename = f"{doc.pk:07}{counter_str}{filetype_str}"

    # Append .gpg for encrypted files
    if append_gpg and doc.storage_type == doc.STORAGE_TYPE_GPG:
        filename += ".gpg"

    return filename
