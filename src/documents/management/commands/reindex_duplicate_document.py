import logging
import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from click.core import batch
from django.core.management import BaseCommand
from django.db.models import Q
from numpy.ma.core import true_divide
from openpyxl.styles.builtins import title
from tqdm import tqdm

from documents.models import Document, Folder
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


def duplicate_documents_with_workers(duplicate_count=1, limit=None, num_workers=5, batch_size=10000, folder_id = None, owner_id = None, start_time=None, progress_bar_disable=False):
    """
    Duplicate documents and update their index using workers.
    """
    # Filter documents with non-empty content
    if start_time is None:
        start_time = datetime(2025, 4, 14, 8, 3, 17, 704503, tzinfo=timezone.utc)
    logger.info(f'start time: {start_time}')

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
    ).filter(~Q(content=""),created__gte=start_time, created__lte=datetime.now(timezone.utc))
    if limit:
        documents = documents[:limit]

    new_documents = []
    new_folders = []
    document_count = documents.count()
    num_batches = math.ceil(document_count / batch_size)
    dict_checksum_id_folder = dict()
    logger.info(f"Document count to process: {document_count} batch_size {batch_size}: {num_batches} batches")
    for batch_idx in range(num_batches):
        logger.info(f"Document count to process: {batch_idx}  batches")
        for document in documents[batch_idx * batch_size: (batch_idx + 1) * batch_size]:
            # create folder
            document:Document
            folder = Folder(
                name = document.title,
                checksum=document.checksum,
                type='file',
                created=document.created,
                updated=document.modified,
                parent_folder_id=folder_id,
                owner_id=owner_id,
                path='',
                is_insensitive=True,
                matching_algorithm=1,


            )
            new_folders.append(folder)
            new_documents.append(document)
            if len(new_documents) >= batch_size:
                created_folders = Folder.objects.bulk_create(new_folders, batch_size=batch_size)

                for folder in created_folders:
                    folder.path = f"{folder_id}/{folder.id}"
                    dict_checksum_id_folder[folder.checksum] = folder.id
                Folder.objects.bulk_update(created_folders, ['path'],batch_size=batch_size)
                logger.info('folder updated')
                for doc in new_documents:
                    doc.folder_id = dict_checksum_id_folder[doc.checksum]
                Document.objects.bulk_update(new_documents, ['folder_id'], batch_size=batch_size)
                # Bulk create new documents
                update_index_bulk_documents(new_documents, batch_size)
                logger.info("All documents have been indexed successfully.")
                dict_checksum_id_folder.clear()
                new_folders.clear()
                new_documents.clear()


    if len(new_documents) >= 0:
        # Bulk create new documents
        update_index_bulk_documents(new_documents, batch_size)
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

        parser.add_argument(
            "--folder-id",
            type=int,
            default=10000,
            help="Number of workers to use for parallel indexing.",
        )
        parser.add_argument(
            "--owner-id",
            type=int,
            default=10000,
            help="Number of workers to use for parallel indexing.",
        )
        parser.add_argument(
            "--start-time",
            type=str,
            default=None,
            help="Start time for filtering documents (format: YYYY-MM-DDTHH:MM:SSZ).",
        )

        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)

        limit = options["limit"]  # Limit the number of documents to process
        duplicate_count = options["duplicate_count"]  # Number of duplicates per document
        num_workers = options["num_workers"]  # Number of workers for parallel processing
        batch_size = options["batch_size"]  # Number of workers for parallel processing
        folder_id = options["folder_id"]  # Number of workers for parallel processing
        owner_id = options["owner_id"]  # Number of workers for parallel processing
        start_time_str = options["start_time"]

        start_time = None
        if start_time_str:
            try:
                start_time = datetime.strptime(start_time_str,
                                               "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                logger.error(
                    "Invalid start_time format. Use 'YYYY-MM-DDTHH:MM:SSZ'.")
                return

        if options["command"] == "duplicate":
            duplicate_documents_with_workers(
                duplicate_count=duplicate_count,
                limit=limit,
                num_workers=num_workers,
                batch_size=batch_size,
                folder_id=folder_id,
                owner_id=owner_id,
                start_time=start_time,
                progress_bar_disable=self.use_progress_bar,
            )

