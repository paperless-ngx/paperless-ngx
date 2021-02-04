import logging

import tqdm
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from documents.models import Document


class Command(BaseCommand):

    help = """
        This will rename all documents to match the latest filename format.
    """.replace("    ", "")

    def handle(self, *args, **options):

        logging.getLogger().handlers[0].level = logging.ERROR

        for document in tqdm.tqdm(Document.objects.all()):
            post_save.send(Document, instance=document)
