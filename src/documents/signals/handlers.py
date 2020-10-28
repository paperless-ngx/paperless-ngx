import logging
import os
from subprocess import Popen

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from documents.classifier import DocumentClassifier
from .. import index
from ..models import Document, Tag


def logger(message, group):
    logging.getLogger(__name__).debug(message, extra={"group": group})


#TODO: global? really?
classifier = DocumentClassifier()


def index_document(sender, document=None, logging_group=None, **kwargs):
    index.add_document_to_index(sender, instance=document)


def classify_document(sender, document=None, logging_group=None, **kwargs):
    global classifier
    try:
        classifier.reload()
        classifier.classify_document(
            document,
            classify_correspondent=True,
            classify_tags=True,
            classify_document_type=True
        )
    except FileNotFoundError:
        logging.getLogger(__name__).fatal(
            "Cannot classify document, classifier model file was not found."
        )


def add_inbox_tags(sender, document=None, logging_group=None, **kwargs):
    inbox_tags = Tag.objects.filter(is_inbox_tag=True)
    document.tags.add(*inbox_tags)


def run_pre_consume_script(sender, filename, **kwargs):

    if not settings.PRE_CONSUME_SCRIPT:
        return

    Popen((settings.PRE_CONSUME_SCRIPT, filename)).wait()


def run_post_consume_script(sender, document, **kwargs):

    if not settings.POST_CONSUME_SCRIPT:
        return

    Popen((
        settings.POST_CONSUME_SCRIPT,
        str(document.id),
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
        object_id=document.id,
        user=user,
        object_repr=document.__str__(),
    )
