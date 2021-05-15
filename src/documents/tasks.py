import logging

import tqdm
from django.conf import settings
from django.db.models.signals import post_save
from whoosh.writing import AsyncWriter

from documents import index, sanity_checker
from documents.classifier import DocumentClassifier, load_classifier
from documents.consumer import Consumer, ConsumerError
from documents.models import Document, Tag, DocumentType, Correspondent
from documents.sanity_checker import SanityCheckFailedException

logger = logging.getLogger("paperless.tasks")


def index_optimize():
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)


def index_reindex(progress_bar_disable=False):
    documents = Document.objects.all()

    ix = index.open_index(recreate=True)

    with AsyncWriter(ix) as writer:
        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            index.update_document(writer, document)


def train_classifier():
    if (not Tag.objects.filter(
                matching_algorithm=Tag.MATCH_AUTO).exists() and
        not DocumentType.objects.filter(
            matching_algorithm=Tag.MATCH_AUTO).exists() and
        not Correspondent.objects.filter(
            matching_algorithm=Tag.MATCH_AUTO).exists()):

        return

    classifier = load_classifier()

    if not classifier:
        classifier = DocumentClassifier()

    try:
        if classifier.train():
            logger.info(
                "Saving updated classifier model to {}...".format(
                    settings.MODEL_FILE)
            )
            classifier.save()
        else:
            logger.debug(
                "Training data unchanged."
            )

    except Exception as e:
        logger.warning(
            "Classifier error: " + str(e)
        )


def consume_file(path,
                 override_filename=None,
                 override_title=None,
                 override_correspondent_id=None,
                 override_document_type_id=None,
                 override_tag_ids=None,
                 task_id=None):

    document = Consumer().try_consume_file(
        path,
        override_filename=override_filename,
        override_title=override_title,
        override_correspondent_id=override_correspondent_id,
        override_document_type_id=override_document_type_id,
        override_tag_ids=override_tag_ids,
        task_id=task_id
    )

    if document:
        return "Success. New document id {} created".format(
            document.pk
        )
    else:
        raise ConsumerError("Unknown error: Returned document was null, but "
                            "no error message was given.")


def sanity_check():
    messages = sanity_checker.check_sanity()

    messages.log_messages()

    if messages.has_error():
        raise SanityCheckFailedException(
            "Sanity check failed with errors. See log.")
    elif messages.has_warning():
        return "Sanity check exited with warnings. See log."
    elif len(messages) > 0:
        return "Sanity check exited with infos. See log."
    else:
        return "No issues detected."


def bulk_update_documents(document_ids):
    documents = Document.objects.filter(id__in=document_ids)

    ix = index.open_index()

    for doc in documents:
        post_save.send(Document, instance=doc, created=False)

    with AsyncWriter(ix) as writer:
        for doc in documents:
            index.update_document(writer, doc)
