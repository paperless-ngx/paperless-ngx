import logging

from django.conf import settings
from whoosh.writing import AsyncWriter

from documents import index
from documents.classifier import DocumentClassifier, \
    IncompatibleClassifierVersionError
from documents.consumer import Consumer, ConsumerError
from documents.mail import MailFetcher
from documents.models import Document


def consume_mail():
    MailFetcher().pull()


def index_optimize():
    index.open_index().optimize()


def index_reindex():
    documents = Document.objects.all()

    ix = index.open_index(recreate=True)

    with AsyncWriter(ix) as writer:
        for document in documents:
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


def consume_file(file,
                 original_filename=None,
                 force_title=None,
                 force_correspondent_id=None,
                 force_document_type_id=None,
                 force_tag_ids=None):

    document = Consumer().try_consume_file(
        file,
        original_filename=original_filename,
        force_title=force_title,
        force_correspondent_id=force_correspondent_id,
        force_document_type_id=force_document_type_id,
        force_tag_ids=force_tag_ids)

    if document:
        return "Success. New document id {} created".format(
            document.pk
        )
    else:
        raise ConsumerError("Unknown error: Returned document was null, but "
                            "no error message was given.")
