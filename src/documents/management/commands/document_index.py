from django.core.management import BaseCommand
from django.db import transaction

from documents.mixins import Renderable
from documents.tasks import index_reindex, index_optimize


class Command(Renderable, BaseCommand):

    help = "Manages the document index."

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("command", choices=['reindex', 'optimize'])

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]
        with transaction.atomic():
            if options['command'] == 'reindex':
                index_reindex()
            elif options['command'] == 'optimize':
                index_optimize()
