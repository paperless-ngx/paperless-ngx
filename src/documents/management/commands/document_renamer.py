from django.db.models.signals import post_save

from documents.management.commands.base import PaperlessCommand
from documents.models import Document


class Command(PaperlessCommand):
    help = "Rename all documents"

    def handle(self, *args, **options):
        for document in self.track(Document.objects.all(), description="Renaming..."):
            post_save.send(Document, instance=document, created=False)
