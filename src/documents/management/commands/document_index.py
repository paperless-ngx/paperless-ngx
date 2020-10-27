from django.core.management import BaseCommand
from whoosh.writing import AsyncWriter

import documents.index as index
from documents.mixins import Renderable
from documents.models import Document


class Command(Renderable, BaseCommand):

    help = "Manages the document index."

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("command", choices=['reindex', 'optimize'])

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        if options['command'] == 'reindex':
            documents = Document.objects.all()

            ix = index.open_index(recreate=True)

            with AsyncWriter(ix) as writer:
                for document in documents:
                    index.update_document(writer, document)

        elif options['command'] == 'optimize':
            index.open_index().optimize()
