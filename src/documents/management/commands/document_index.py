from django.core.management import BaseCommand
from django.db import transaction

from documents.tasks import index_reindex, index_optimize


class Command(BaseCommand):

    help = "Manages the document index."

    def add_arguments(self, parser):
        parser.add_argument("command", choices=['reindex', 'optimize'])

    def handle(self, *args, **options):
        with transaction.atomic():
            if options['command'] == 'reindex':
                index_reindex()
            elif options['command'] == 'optimize':
                index_optimize()
