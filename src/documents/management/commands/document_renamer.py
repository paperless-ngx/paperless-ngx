import logging

import tqdm
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from documents.models import Document


class Command(BaseCommand):

    help = """
        This will rename all documents to match the latest filename format.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown"
        )

    def handle(self, *args, **options):

        logging.getLogger().handlers[0].level = logging.ERROR

        for document in tqdm.tqdm(
            Document.objects.all(),
            disable=options['no_progress_bar']
        ):
            post_save.send(Document, instance=document)
