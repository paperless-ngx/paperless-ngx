import logging
import os.path
import pickle

from django.core.management.base import BaseCommand
from documents.classifier import  DocumentClassifier
from paperless import settings
from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        There is no help.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
        clf = DocumentClassifier()

        clf.train()


        logging.getLogger(__name__).info("Saving models to " + settings.MODEL_FILE + "...")

        clf.save_classifier()
