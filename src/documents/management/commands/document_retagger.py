import logging

from django.core.management.base import BaseCommand

from documents.classifier import DocumentClassifier
from documents.models import Document, Tag

from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        There is no help. #TODO
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "-c", "--correspondent",
            action="store_true"
        )
        parser.add_argument(
            "-T", "--tags",
            action="store_true"
        )
        parser.add_argument(
            "-t", "--type",
            action="store_true"
        )
        parser.add_argument(
            "-i", "--inbox-only",
            action="store_true"
        )
        parser.add_argument(
            "-r", "--replace-tags",
            action="store_true"
        )

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        if options['inbox_only']:
            documents = Document.objects.filter(tags__is_inbox_tag=True).distinct()
        else:
            documents = Document.objects.all().exclude(tags__is_archived_tag=True).distinct()

        logging.getLogger(__name__).info("Loading classifier")
        try:
            clf = DocumentClassifier.load_classifier()
        except FileNotFoundError:
            logging.getLogger(__name__).fatal("Cannot classify documents, classifier model file was not found.")
            return

        for document in documents:
            logging.getLogger(__name__).info("Processing document {}".format(document.title))
            clf.classify_document(document, classify_document_type=options['type'], classify_tags=options['tags'], classify_correspondent=options['correspondent'], replace_tags=options['replace_tags'])
