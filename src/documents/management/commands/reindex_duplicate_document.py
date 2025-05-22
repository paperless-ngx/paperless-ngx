import logging
import math
import time
from datetime import datetime, timezone

from django.core.management import BaseCommand
from django.db.models import Q
from elasticsearch.helpers import bulk

from documents.documents import DocumentDocument
from documents.index import update_index_document
from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document
from edoc.settings import ELASTIC_SEARCH_DOCUMENT_INDEX

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
def delete_index(index_name):
    """
    Delete the specified Elasticsearch index if it exists.
    """
    client = Elasticsearch(
        ELASTIC_SEARCH_HOST)  # Replace with your Elasticsearch host
    if client.indices.exists(index=index_name):
        try:
            client.indices.delete(index=index_name)
            logger.info(f"Index '{index_name}' deleted successfully.")
        except Exception as e:
            logger.info(f"Failed to delete index '{index_name}': {e}")
    else:
        logger.error(f"Index '{index_name}' does not exist.")

def duplicate_documents_with_workers(duplicate_count: object = 1,
                                     limit: object = None,
                                     num_workers: object = 5,
                                     batch_size: object = 10000,
                                     folder_id: object = None,
                                     owner_id: object = None,
                                     start_time: object = None,
                                     progress_bar_disable: object = False) -> object:
    """
    Duplicate documents and update their index using workers.
    """
    # Filter documents with non-empty content
    # if start_time is None:
    #     start_time = datetime(2025, 4, 14, 8, 3, 17, 704503, tzinfo=timezone.utc)
    # logger.info(f'start time: {start_time}')
    start_time = time.time()

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
    logger.info(f'time query: {time.time()-start_time}')
    # new_documents = []
    # new_folders = []

    document_count = documents.count()
    num_batches = math.ceil(document_count / batch_size)
    dict_checksum_id_folder = dict()
    delete_index(ELASTIC_SEARCH_DOCUMENT_INDEX)
    logger.info(f"Document count to process: {document_count} batch_size {batch_size}: {num_batches} batches")
    actions = []
    for batch_idx in range(num_batches):
        time_create_batch = time.time()
        # logger.info(f"Document count to process: {batch_idx}  batches")
        for doc in documents[batch_idx * batch_size: (batch_idx + 1) * batch_size]:
            start_time_doc = time.time()
            try:


                parsed_document = DocumentDocument.prepare_document_data(doc)
                actions.append({
                    "_index": DocumentDocument.Index.name,
                    "_id": str(doc.id),
                    "_source": parsed_document,
                })
                # logger.info(
                #     f"Tài liệu {doc.id} đã được chuẩn bị để chỉ mục trong batch {i // batch_size + 1}.")
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
                    # Perform bulk indexing for the current batch
                    client = DocumentDocument._get_connection()
                    bulk(client, actions)
                    # logger.info(
                        # f"Batch {i // batch_size + 1}: Đã chỉ mục thành công {len(actions)} tài liệu.")
                except Exception as e:
                    logger.error(e)
                time_reindex_ = time.time()-time_reindex
                time_reindex = time.time()
                logger.info(f"All documents in batch {batch_idx} have been indexed successfully.  time_create_batch: {time_create_batch_:.3f}s, index_time: {time_reindex_:.3f}s, total_time: {time_reindex_+time_create_batch_:.3f}s")

                actions.clear()


    if len(actions) >= 0:
        # Bulk create new documents
        try:
            # Perform bulk indexing for the current batch
            client = DocumentDocument._get_connection()
            bulk(client, actions)
            # logger.info(
            #     f"Batch {i // batch_size + 1}: Đã chỉ mục thành công {len(actions)} tài liệu.")
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

