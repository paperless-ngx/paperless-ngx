import logging
import os
from subprocess import Popen

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .. import index, matching
from ..models import Document, Tag


def logger(message, group):
    logging.getLogger(__name__).debug(message, extra={"group": group})


def add_inbox_tags(sender, document=None, logging_group=None, **kwargs):
    inbox_tags = Tag.objects.filter(is_inbox_tag=True)
    document.tags.add(*inbox_tags)


def set_correspondent(sender, document=None, logging_group=None, classifier=None, replace=False, use_first=True, **kwargs):
    if document.correspondent and not replace:
        return

    potential_correspondents = matching.match_correspondents(document.content, classifier)

    potential_count = len(potential_correspondents)
    if potential_correspondents:
        selected = potential_correspondents[0]
    else:
        selected = None
    if potential_count > 1:
        if use_first:
            message = "Detected {} potential correspondents, so we've opted for {}"
            logger(
                message.format(potential_count, selected),
                logging_group
            )
        else:
            message = "Detected {} potential correspondents, not assigning any correspondent"
            logger(
                message.format(potential_count),
                logging_group
            )
            return

    if selected or replace:
        logger(
            'Assigning correspondent "{}" to "{}" '.format(selected, document),
            logging_group
        )

        document.correspondent = selected
        document.save(update_fields=("correspondent",))


def set_document_type(sender, document=None, logging_group=None, classifier=None, replace=False, use_first=True, **kwargs):
    if document.document_type and not replace:
        return

    potential_document_type = matching.match_document_types(document.content, classifier)

    potential_count = len(potential_document_type)
    if potential_document_type:
        selected = potential_document_type[0]
    else:
        selected = None

    if potential_count > 1:
        if use_first:
            message = "Detected {} potential document types, so we've opted for {}"
            logger(
                message.format(potential_count, selected),
                logging_group
            )
        else:
            message = "Detected {} potential document types, not assigning any document type"
            logger(
                message.format(potential_count),
                logging_group
            )
            return

    if selected or replace:
        logger(
            'Assigning document type "{}" to "{}" '.format(selected, document),
            logging_group
        )

        document.document_type = selected
        document.save(update_fields=("document_type",))


def set_tags(sender, document=None, logging_group=None, classifier=None, replace=False, **kwargs):
    if replace:
        document.tags.clear()
        current_tags = set([])
    else:
        current_tags = set(document.tags.all())

    relevant_tags = set(matching.match_tags(document.content, classifier)) - current_tags

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


def cleanup_document_deletion(sender, instance, using, **kwargs):

    if not isinstance(instance, Document):
        return

    for f in (instance.source_path, instance.thumbnail_path):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass  # The file's already gone, so we're cool with it.


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
