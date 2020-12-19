import logging

import tqdm
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from documents.models import Document
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

        logging.getLogger().handlers[0].level = logging.ERROR

        for document in tqdm.tqdm(Document.objects.all()):
            post_save.send(Document, instance=document)
