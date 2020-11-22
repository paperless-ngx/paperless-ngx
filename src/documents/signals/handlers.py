import logging
import os
from subprocess import Popen

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models, DatabaseError
from django.dispatch import receiver
from django.utils import timezone

from .. import index, matching
from ..file_handling import delete_empty_directories, generate_filename, \
    create_source_path_directory
from ..models import Document, Tag


def logger(message, group):
    logging.getLogger(__name__).debug(message, extra={"group": group})


def add_inbox_tags(sender, document=None, logging_group=None, **kwargs):
    inbox_tags = Tag.objects.filter(is_inbox_tag=True)
    document.tags.add(*inbox_tags)


def set_correspondent(sender,
                      document=None,
                      logging_group=None,
                      classifier=None,
                      replace=False,
                      use_first=True,
                      **kwargs):
    if document.correspondent and not replace:
        return

    potential_correspondents = matching.match_correspondents(document.content,
                                                             classifier)

    potential_count = len(potential_correspondents)
    if potential_correspondents:
        selected = potential_correspondents[0]
    else:
        selected = None
    if potential_count > 1:
        if use_first:
            logger(
                f"Detected {potential_count} potential correspondents, "
                f"so we've opted for {selected}",
                logging_group
            )
        else:
            logger(
                f"Detected {potential_count} potential correspondents, "
                f"not assigning any correspondent",
                logging_group
            )
            return

    if selected or replace:
        logger(
            f"Assigning correspondent {selected} to {document}",
            logging_group
        )

        document.correspondent = selected
        document.save(update_fields=("correspondent",))


def set_document_type(sender,
                      document=None,
                      logging_group=None,
                      classifier=None,
                      replace=False,
                      use_first=True,
                      **kwargs):
    if document.document_type and not replace:
        return

    potential_document_type = matching.match_document_types(document.content,
                                                            classifier)

    potential_count = len(potential_document_type)
    if potential_document_type:
        selected = potential_document_type[0]
    else:
        selected = None

    if potential_count > 1:
        if use_first:
            logger(
                f"Detected {potential_count} potential document types, "
                f"so we've opted for {selected}",
                logging_group
            )
        else:
            logger(
                f"Detected {potential_count} potential document types, "
                f"not assigning any document type",
                logging_group
            )
            return

    if selected or replace:
        logger(
            f"Assigning document type {selected} to {document}",
            logging_group
        )

        document.document_type = selected
        document.save(update_fields=("document_type",))


def set_tags(sender,
             document=None,
             logging_group=None,
             classifier=None,
             replace=False,
             **kwargs):
    if replace:
        document.tags.clear()
        current_tags = set([])
    else:
        current_tags = set(document.tags.all())

    matched_tags = matching.match_tags(document.content, classifier)

    relevant_tags = set(matched_tags) - current_tags

    if not relevant_tags:
        return

    message = 'Tagging "{}" with "{}"'
    logger(
        message.format(document, ", ".join([t.slug for t in relevant_tags])),
        logging_group
    )

    document.tags.add(*relevant_tags)


def run_pre_consume_script(sender, filename, **kwargs):

    if not settings.PRE_CONSUME_SCRIPT:
        return

    Popen((settings.PRE_CONSUME_SCRIPT, filename)).wait()


def run_post_consume_script(sender, document, **kwargs):

    if not settings.POST_CONSUME_SCRIPT:
        return

    Popen((
        settings.POST_CONSUME_SCRIPT,
        str(document.pk),
        document.file_name,
        document.source_path,
        document.thumbnail_path,
        None,
        None,
        str(document.correspondent),
        str(",".join(document.tags.all().values_list("slug", flat=True)))
    )).wait()


@receiver(models.signals.post_delete, sender=Document)
def cleanup_document_deletion(sender, instance, using, **kwargs):
    for f in (instance.source_path, instance.thumbnail_path):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass  # The file's already gone, so we're cool with it.

    delete_empty_directories(os.path.dirname(instance.source_path))


@receiver(models.signals.m2m_changed, sender=Document.tags.through)
@receiver(models.signals.post_save, sender=Document)
def update_filename_and_move_files(sender, instance, **kwargs):

    if not instance.filename:
        # Can't update the filename if there is not filename to begin with
        # This happens after the consumer creates a new document.
        # The PK needs to be set first by saving the document once. When this
        # happens, the file is not yet in the ORIGINALS_DIR, and thus can't be
        # renamed anyway. In all other cases, instance.filename will be set.
        return

    old_filename = instance.filename
    old_path = instance.source_path
    new_filename = generate_filename(instance)

    if new_filename == instance.filename:
        # Don't do anything if its the same.
        return

    new_path = os.path.join(settings.ORIGINALS_DIR, new_filename)

    if not os.path.isfile(old_path):
        # Can't do anything if the old file does not exist anymore.
        logging.getLogger(__name__).fatal(
            f"Document {str(instance)}: File {old_path} has gone.")
        return

    if os.path.isfile(new_path):
        # Can't do anything if the new file already exists. Skip updating file.
        logging.getLogger(__name__).warning(
            f"Document {str(instance)}: Cannot rename file "
            f"since target path {new_path} already exists.")
        return

    create_source_path_directory(new_path)

    try:
        os.rename(old_path, new_path)
        instance.filename = new_filename
        instance.save()

    except OSError as e:
        instance.filename = old_filename
    except DatabaseError as e:
        os.rename(new_path, old_path)
        instance.filename = old_filename

    if not os.path.isfile(old_path):
        delete_empty_directories(os.path.dirname(old_path))


def set_log_entry(sender, document=None, logging_group=None, **kwargs):

    ct = ContentType.objects.get(model="document")
    user = User.objects.get(username="consumer")

    LogEntry.objects.create(
        action_flag=ADDITION,
        action_time=timezone.now(),
        content_type=ct,
        object_id=document.pk,
        user=user,
        object_repr=document.__str__(),
    )


def add_to_index(sender, document, **kwargs):
    index.add_or_update_document(document)
