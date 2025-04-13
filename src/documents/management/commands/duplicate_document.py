import logging
from operator import index

import tqdm
from django.core.management import BaseCommand
from nltk.corpus.reader import documents
from pymupdf.extra import page_count

from documents.index import update_index_document
from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document
import datetime
import uuid
from django.db import transaction
logger = logging.getLogger("edoc.duplicate_document")
def duplicate_documents_with_changes(progress_bar_disable=False):
    documents = Document.objects.all()
    new_documents = []
    logger.info(f"document {documents.count()}")

    for document in tqdm.tqdm(documents, disable=progress_bar_disable):
        for _ in range(5):  # Create 5 new records for each document
            document:Document
            new_document = Document(
                title=document.title,
                content=document.content,
                checksum=uuid.uuid4().hex,  # Generate a new checksum
                archive_filename=f"{uuid.uuid4().hex}",  # Generate a new archive file
                filename=f"{uuid.uuid4().hex}",  # Generate a new archive file
                mime_type=document.mime_type,
                storage_type=document.storage_type,
                owner_id=document.owner_id,
                page_count=document.page_count,
                indexed=True,
                file_id=document.file_id,
                folder_id=document.folder_id,
                original_filename=document.original_filename,
                archive_checksum=f"{uuid.uuid4().hex}"
                # Copy other fields as needed
            )
            new_documents.append(new_document)
    logger.info(f'new_documents {len(new_documents)}')
    # Save all new documents in bulk
    with transaction.atomic():
        created_documents = Document.objects.bulk_create(new_documents, batch_size=1000)
        for document in created_documents:
            logger.info(f'add index for document{document.id}')
            update_index_document(document)

    logger.info(f"Created {len(new_documents)} new documents.")

class Command(ProgressBarMixin, BaseCommand):
    help = "Manages the document index elastic search."

    def add_arguments(self, parser):
        parser.add_argument("command", choices=["duplicate"])
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)

        duplicate_documents_with_changes(progress_bar_disable=self.use_progress_bar)
