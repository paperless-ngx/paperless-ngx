import logging
import math
import os.path
import time

from django.core.management import BaseCommand

from documents.index import update_index_document
from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Folder
from documents.tasks import update_document_count_folder_path

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


def update_document_count_filesize(batch_size: object = 10000, ) -> object:
    """
    Duplicate documents and update their index using workers.
    """
    # Filter documents with non-empty content
    # if start_time is None:
    #     start_time = datetime(2025, 4, 14, 8, 3, 17, 704503, tzinfo=timezone.utc)
    # logger.info(f'start time: {start_time}')
    start_time = time.time()
    folders = Folder.objects.all().prefetch_related('documents')

    # new_folders = []
    folder_count = folders.count()
    num_batches = math.ceil(folder_count / batch_size)
    dict_checksum_id_folder = dict()
    logger.info(
        f"folder count to process: {folder_count} batch_size {batch_size}: {num_batches} batches")
    actions = []
    for batch_idx in range(num_batches):
        time_create_batch = time.time()
        # logger.info(f"Document count to process: {batch_idx}  batches")
        for folder in folders[
                      batch_idx * batch_size: (batch_idx + 1) * batch_size]:
            start_time_doc = time.time()
            try:
                if folder.type == Folder.FOLDER:
                    update_document_count_folder_path(folder.path)

                if folder.documents.count() == 0:
                    continue
                document = folder.documents.first()
                if os.path.exists(document.source_path):
                    folder.filesize = os.path.getsize(document.source_path)
                folder.archive_filename = document.archive_filename,
                folder.original_filename = document.original_filename,
                folder.filename = document.filename
                actions.append(folder)





            except Exception as e:
                raise e
                logger.error(f"Lỗi khi xử lý tài liệu {doc.id}: {e}")
            # logger.info(f'time parse doc {time.time()- start_time_doc:.6f}s')
            # new_documents.append(document)
            if len(actions) >= batch_size:
                # logger.info(f'time create batch {time.time()-time_create_batch}')
                time_create_batch_ = time.time() - time_create_batch
                time_create_batch = time.time()
                # Bulk create new documents
                time_reindex = time.time()
                try:
                    Folder.objects.bulk_update(actions,
                                               ['filesize', 'archive_filename',
                                                'original_filename',
                                                'filename'])


                except Exception as e:
                    logger.error(e)
                time_reindex_ = time.time() - time_reindex
                time_reindex = time.time()
                logger.info(
                    f"All documents in batch {batch_idx} have been update successfully.  time_create_batch: {time_create_batch_:.3f}s, index_time: {time_reindex_:.3f}s, total_time: {time_reindex_ + time_create_batch_:.3f}s")

                actions.clear()

    if len(actions) >= 0:
        # Bulk create new documents
        try:
            Folder.objects.bulk_update(actions,
                                       ['filesize', 'archive_filename',
                                        'original_filename', 'filename'])


        except Exception as e:
            logger.error(e)
        logger.info("All documents have been indexed successfully.")

        actions.clear()


class Command(ProgressBarMixin, BaseCommand):
    """
    Django management command to duplicate documents and update their index.
    """
    help = "Duplicate documents and manage their indexing using multiple workers."

    def add_arguments(self, parser):
        parser.add_argument(
            "command",
            choices=["update"],
            help="Command to execute (only supports 'update').",
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

        batch_size = options[
            "batch_size"]  # Number of workers for parallel processing

        if options["command"] == "update":
            update_document_count_filesize(
                batch_size=batch_size,
            )
