import datetime
import logging
import os
from collections import defaultdict

import pathvalidate
from django.conf import settings
from django.template.defaultfilters import slugify


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
        delimiter = t.name.find('_')

        if delimiter == -1:
            delimiter = t.name.find('-')

        if delimiter == -1:
            continue

        key = t.name[:delimiter]
        value = t.name[delimiter + 1:]

        mydictionary[slugify(key)] = slugify(value)

    return mydictionary


def generate_unique_filename(doc, root):
    counter = 0

    while True:
        new_filename = generate_filename(doc, counter)
        if new_filename == doc.filename:
            # still the same as before.
            return new_filename

        if os.path.exists(os.path.join(root, new_filename)):
            counter += 1
        else:
            return new_filename


def generate_filename(doc, counter=0, append_gpg=True):
    path = ""

    try:
        if settings.PAPERLESS_FILENAME_FORMAT is not None:
            tags = defaultdictNoStr(lambda: slugify(None),
                                    many_to_dictionary(doc.tags))

            tag_list = pathvalidate.sanitize_filename(
                ",".join(sorted(
                    [tag.name for tag in doc.tags.all()]
                )),
                replacement_text="-"
            )

            if doc.correspondent:
                correspondent = pathvalidate.sanitize_filename(
                    doc.correspondent.name, replacement_text="-"
                )
            else:
                correspondent = "none"

            if doc.document_type:
                document_type = pathvalidate.sanitize_filename(
                    doc.document_type.name, replacement_text="-"
                )
            else:
                document_type = "none"

            path = settings.PAPERLESS_FILENAME_FORMAT.format(
                title=pathvalidate.sanitize_filename(
                    doc.title, replacement_text="-"),
                correspondent=correspondent,
                document_type=document_type,
                created=datetime.date.isoformat(doc.created),
                created_year=doc.created.year if doc.created else "none",
                created_month=f"{doc.created.month:02}" if doc.created else "none",  # NOQA: E501
                created_day=f"{doc.created.day:02}" if doc.created else "none",
                added=datetime.date.isoformat(doc.added),
                added_year=doc.added.year if doc.added else "none",
                added_month=f"{doc.added.month:02}" if doc.added else "none",
                added_day=f"{doc.added.day:02}" if doc.added else "none",
                tags=tags,
                tag_list=tag_list
            ).strip()

            path = path.strip(os.sep)

    except (ValueError, KeyError, IndexError):
        logging.getLogger(__name__).warning(
            f"Invalid PAPERLESS_FILENAME_FORMAT: "
            f"{settings.PAPERLESS_FILENAME_FORMAT}, falling back to default")

    counter_str = f"_{counter:02}" if counter else ""
    if len(path) > 0:
        filename = f"{path}{counter_str}{doc.file_type}"
    else:
        filename = f"{doc.pk:07}{counter_str}{doc.file_type}"

    # Append .gpg for encrypted files
    if append_gpg and doc.storage_type == doc.STORAGE_TYPE_GPG:
        filename += ".gpg"

    return filename


def archive_name_from_filename(filename):

    return os.path.splitext(filename)[0] + ".pdf"
