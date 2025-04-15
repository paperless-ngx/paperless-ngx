import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from django.core.management import BaseCommand
from django.db.models import Q
from tqdm import tqdm

from documents.models import Document
from documents.index import update_index_document, update_index_bulk_documents
from documents.management.commands.mixins import ProgressBarMixin

logger = logging.getLogger("edoc.duplicate_document")


def process_document(document):
    """
    Process a single document: log and update its index.
    """
    try:
        logger.info(f'Add index for document {document.id}')
        update_index_document(document)
    except Exception as e:
        logger.error(f"Failed to index document {document.id}: {e}")


def duplicate_documents_with_workers(duplicate_count=1, limit=None, num_workers=5, batch_size=10000, progress_bar_disable=False):
    """
    Duplicate documents and update their index using workers.
    """
    # Filter documents with non-empty content
    documents = Document.objects.select_related(
        'document_type',
        'warehouse',
        'archive_font',
        'folder',
        'owner'
    ).prefetch_related(
        'tags',
        'custom_fields',
        'notes'
    ).filter(~Q(content=""))
    if limit:
        documents = documents[:limit]

    new_documents = []
    logger.info(f"Document count to process: {documents.count()} batch_size {batch_size}")

    for document in tqdm(documents, disable=progress_bar_disable):
        for _ in range(duplicate_count):
            new_document = Document(
                title=document.title,
                content=document.content,
                checksum=uuid.uuid4().hex,  # Generate a unique checksum
                archive_filename=f"{uuid.uuid4().hex}",  # Generate unique archive file
                filename=f"{uuid.uuid4().hex}",  # Generate unique filename
                mime_type=document.mime_type,
                storage_type=document.storage_type,
                owner_id=document.owner_id,
                page_count=document.page_count,
                indexed=True,
                file_id=document.file_id,
                folder_id=document.folder_id,
                original_filename=document.original_filename,
                archive_checksum=f"{uuid.uuid4().hex}",  # Generate new archive checksum
            )
            new_documents.append(new_document)
            if len(new_documents) >= batch_size:
                # Bulk create new documents
                created_documents = Document.objects.bulk_create(new_documents,
                                                                 batch_size=batch_size)
                logger.info(f"Created {len(created_documents)} new documents.")


                update_index_bulk_documents(created_documents, batch_size)
                logger.info("All documents have been indexed successfully.")

                new_documents.clear()

    if len(new_documents) >= 0:
        # Bulk create new documents
        created_documents = Document.objects.bulk_create(new_documents,
                                                         batch_size=batch_size)
        logger.info(f"Created {len(created_documents)} new documents.")

        update_index_bulk_documents(created_documents, batch_size)
        logger.info("All documents have been indexed successfully.")

        new_documents.clear()





class Command(ProgressBarMixin, BaseCommand):
    """
    Django management command to duplicate documents and update their index.
    """
    help = "Duplicate documents and manage their indexing using multiple workers."

    def add_arguments(self, parser):
        parser.add_argument(
            "command",
            choices=["duplicate"],
            help="Command to execute (only supports 'duplicate').",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of documents to process.",
        )
        parser.add_argument(
            "--duplicate-count",
            type=int,
            default=1,
            help="Number of duplicates to create for each document.",
        )
        parser.add_argument(
            "--num-workers",
            type=int,
            default=5,
            help="Number of workers to use for parallel indexing.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10000,
            help="Number of workers to use for parallel indexing.",
        )
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)

        limit = options["limit"]  # Limit the number of documents to process
        duplicate_count = options["duplicate_count"]  # Number of duplicates per document
        num_workers = options["num_workers"]  # Number of workers for parallel processing
        batch_size = options["batch_size"]  # Number of workers for parallel processing

        if options["command"] == "duplicate":
            duplicate_documents_with_workers(
                duplicate_count=duplicate_count,
                limit=limit,
                num_workers=num_workers,
                batch_size=batch_size,
                progress_bar_disable=self.use_progress_bar,
            )
