import logging
import os
from collections import defaultdict

from django.conf import settings
from django.template.defaultfilters import slugify


def create_source_path_directory(source_path):
    os.makedirs(os.path.dirname(source_path), exist_ok=True)


def delete_empty_directories(directory):
    # Go up in the directory hierarchy and try to delete all directories
    directory = os.path.normpath(directory)
    root = os.path.normpath(settings.ORIGINALS_DIR)

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
        delimiter = t.name.find('_')

        if delimiter == -1:
            delimiter = t.name.find('-')

        if delimiter == -1:
            continue

        key = t.name[:delimiter]
        value = t.name[delimiter + 1:]

        mydictionary[slugify(key)] = slugify(value)

    return mydictionary


def generate_filename(doc):
    path = ""

    try:
        if settings.PAPERLESS_FILENAME_FORMAT is not None:
            tags = defaultdict(lambda: slugify(None),
                               many_to_dictionary(doc.tags))
            path = settings.PAPERLESS_FILENAME_FORMAT.format(
                correspondent=slugify(doc.correspondent),
                title=slugify(doc.title),
                created=slugify(doc.created),
                created_year=doc.created.year if doc.created else "none",
                created_month=doc.created.month if doc.created else "none",
                created_day=doc.created.day if doc.created else "none",
                added=slugify(doc.added),
                added_year=doc.added.year if doc.added else "none",
                added_month=doc.added.month if doc.added else "none",
                added_day=doc.added.day if doc.added else "none",
                tags=tags,
            )
    except (ValueError, KeyError, IndexError):
        logging.getLogger(__name__).warning(
            f"Invalid PAPERLESS_FILENAME_FORMAT: "
            f"{settings.PAPERLESS_FILENAME_FORMAT}, falling back to default")

    # Always append the primary key to guarantee uniqueness of filename
    if len(path) > 0:
        filename = "%s-%07i%s" % (path, doc.pk, doc.file_type)
    else:
        filename = "%07i%s" % (doc.pk, doc.file_type)

    # Append .gpg for encrypted files
    if doc.storage_type == doc.STORAGE_TYPE_GPG:
        filename += ".gpg"

    return filename
