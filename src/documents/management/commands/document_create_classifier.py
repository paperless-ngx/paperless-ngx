import logging

from django.core.management.base import BaseCommand
from documents.classifier import DocumentClassifier
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
        clf = DocumentClassifier()
        clf.train()
        logging.getLogger(__name__).info(
            "Saving models to {}...".format(settings.MODEL_FILE)
        )
        clf.save_classifier()
