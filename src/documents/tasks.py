import logging

import tqdm
from django.conf import settings
from django.db.models.signals import post_save
from whoosh.writing import AsyncWriter

from documents import index, sanity_checker
from documents.classifier import DocumentClassifier, \
    IncompatibleClassifierVersionError
from documents.consumer import Consumer, ConsumerError
from documents.models import Document
from documents.sanity_checker import SanityFailedError


def index_optimize():
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)


def index_reindex():
    documents = Document.objects.all()

    ix = index.open_index(recreate=True)

    with AsyncWriter(ix) as writer:
        for document in tqdm.tqdm(documents):
            index.update_document(writer, document)


def train_classifier():
    classifier = DocumentClassifier()

    try:
        # load the classifier, since we might not have to train it again.
        classifier.reload()
    except (FileNotFoundError, IncompatibleClassifierVersionError):
        # This is what we're going to fix here.
        pass

    try:
        if classifier.train():
            logging.getLogger(__name__).info(
                "Saving updated classifier model to {}...".format(
                    settings.MODEL_FILE)
            )
            classifier.save_classifier()
        else:
            logging.getLogger(__name__).debug(
                "Training data unchanged."
            )

    except Exception as e:
        logging.getLogger(__name__).error(
            "Classifier error: " + str(e)
        )


def consume_file(path,
                 override_filename=None,
                 override_title=None,
                 override_correspondent_id=None,
                 override_document_type_id=None,
                 override_tag_ids=None):

    document = Consumer().try_consume_file(
        path,
        override_filename=override_filename,
        override_title=override_title,
        override_correspondent_id=override_correspondent_id,
        override_document_type_id=override_document_type_id,
        override_tag_ids=override_tag_ids)

    if document:
        return "Success. New document id {} created".format(
            document.pk
        )
    else:
        raise ConsumerError("Unknown error: Returned document was null, but "
                            "no error message was given.")


def sanity_check():
    messages = sanity_checker.check_sanity()

    if len(messages) > 0:
        raise SanityFailedError(messages)
    else:
        return "No issues detected."


def bulk_update_documents(document_ids):
    documents = Document.objects.filter(id__in=document_ids)

    ix = index.open_index()
    with AsyncWriter(ix) as writer:
        for doc in documents:
            index.update_document(writer, doc)
            post_save.send(Document, instance=doc, created=False)
