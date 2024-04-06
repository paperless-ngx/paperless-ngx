import logging

import tqdm
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document


class Command(ProgressBarMixin, BaseCommand):
    help = "This will rename all documents to match the latest filename format."

    def add_arguments(self, parser):
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        logging.getLogger().handlers[0].level = logging.ERROR

        for document in tqdm.tqdm(
            Document.objects.all(),
            disable=self.no_progress_bar,
        ):
            post_save.send(Document, instance=document, created=False)
