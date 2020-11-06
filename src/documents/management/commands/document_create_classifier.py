import logging

from django.core.management.base import BaseCommand
from documents.classifier import DocumentClassifier, \
    IncompatibleClassifierVersionError
from paperless import settings
from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        Trains the classifier on your data and saves the resulting models to a
        file. The document consumer will then automatically use this new model.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
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
                    "Saving updated classifier model to {}...".format(settings.MODEL_FILE)
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
