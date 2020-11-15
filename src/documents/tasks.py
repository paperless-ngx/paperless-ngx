import logging

from django.conf import settings
from whoosh.writing import AsyncWriter

from documents import index
from documents.classifier import DocumentClassifier, \
    IncompatibleClassifierVersionError
from documents.models import Document


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
