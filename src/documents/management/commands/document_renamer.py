from documents.file_moves import move_files_for_document
from documents.management.commands.base import PaperlessCommand
from documents.models import Document


class Command(PaperlessCommand):
    help = "Rename all documents"

    supports_progress_bar = True
    supports_multiprocessing = False

    def handle(self, *args, **options):
        for document in self.track(
            Document.objects.only("pk"),
            description="Renaming...",
        ):
            move_files_for_document(document.pk)
