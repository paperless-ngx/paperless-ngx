from django.core.management.base import BaseCommand

from documents.models import Document, Tag

from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        This will rename all documents to match the latest filename format.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        for document in Document.objects.all():
            # Saving the document again will generate a new filename and rename
            document.save()
