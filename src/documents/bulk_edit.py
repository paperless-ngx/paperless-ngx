import hashlib
import itertools
import logging
import os
from typing import Optional

from celery import chord
from django.conf import settings
from django.db.models import Q

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.permissions import set_permissions_for_object
from documents.tasks import bulk_update_documents
from documents.tasks import consume_file
from documents.tasks import update_document_archive_file

logger = logging.getLogger("paperless.bulk_edit")


def set_correspondent(doc_ids, correspondent):
    if correspondent:
        correspondent = Correspondent.objects.get(id=correspondent)

    qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(correspondent=correspondent))
    affected_docs = [doc.id for doc in qs]
    qs.update(correspondent=correspondent)

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def set_storage_path(doc_ids, storage_path):
    if storage_path:
        storage_path = StoragePath.objects.get(id=storage_path)

    qs = Document.objects.filter(
        Q(id__in=doc_ids) & ~Q(storage_path=storage_path),
    )
    affected_docs = [doc.id for doc in qs]
    qs.update(storage_path=storage_path)

    bulk_update_documents.delay(
        document_ids=affected_docs,
    )

    return "OK"


def set_document_type(doc_ids, document_type):
    if document_type:
        document_type = DocumentType.objects.get(id=document_type)

    qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(document_type=document_type))
    affected_docs = [doc.id for doc in qs]
    qs.update(document_type=document_type)

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def add_tag(doc_ids, tag):
    qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(tags__id=tag))
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.bulk_create(
        [DocumentTagRelationship(document_id=doc, tag_id=tag) for doc in affected_docs],
    )

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def remove_tag(doc_ids, tag):
    qs = Document.objects.filter(Q(id__in=doc_ids) & Q(tags__id=tag))
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.filter(
        Q(document_id__in=affected_docs) & Q(tag_id=tag),
    ).delete()

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def modify_tags(doc_ids, add_tags, remove_tags):
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.filter(
        document_id__in=affected_docs,
        tag_id__in=remove_tags,
    ).delete()

    DocumentTagRelationship.objects.bulk_create(
        [
            DocumentTagRelationship(document_id=doc, tag_id=tag)
            for (doc, tag) in itertools.product(affected_docs, add_tags)
        ],
        ignore_conflicts=True,
    )

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def delete(doc_ids):
    Document.objects.filter(id__in=doc_ids).delete()

    from documents import index

    with index.open_index_writer() as writer:
        for id in doc_ids:
            index.remove_document_by_id(writer, id)

    return "OK"


def redo_ocr(doc_ids):
    for document_id in doc_ids:
        update_document_archive_file.delay(
            document_id=document_id,
        )

    return "OK"


def set_permissions(doc_ids, set_permissions, owner=None, merge=False):
    qs = Document.objects.filter(id__in=doc_ids)

    if merge:
        # If merging, only set owner for documents that don't have an owner
        qs.filter(owner__isnull=True).update(owner=owner)
    else:
        qs.update(owner=owner)

    for doc in qs:
        set_permissions_for_object(permissions=set_permissions, object=doc, merge=merge)

    affected_docs = [doc.id for doc in qs]

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def rotate(doc_ids: list[int], degrees: int):
    logger.info(
        f"Attempting to rotate {len(doc_ids)} documents by {degrees} degrees.",
    )
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs = []
    import pikepdf

    rotate_tasks = []
    for doc in qs:
        if doc.mime_type != "application/pdf":
            logger.warning(
                f"Document {doc.id} is not a PDF, skipping rotation.",
            )
            continue
        try:
            with pikepdf.open(doc.source_path, allow_overwriting_input=True) as pdf:
                for page in pdf.pages:
                    page.rotate(degrees, relative=True)
                pdf.save()
                doc.checksum = hashlib.md5(doc.source_path.read_bytes()).hexdigest()
                doc.save()
                rotate_tasks.append(
                    update_document_archive_file.s(
                        document_id=doc.id,
                    ),
                )
                logger.info(
                    f"Rotated document {doc.id} by {degrees} degrees",
                )
                affected_docs.append(doc.id)
        except Exception as e:
            logger.exception(f"Error rotating document {doc.id}: {e}")

    if len(affected_docs) > 0:
        bulk_update_task = bulk_update_documents.s(document_ids=affected_docs)
        chord(header=rotate_tasks, body=bulk_update_task).delay()

    return "OK"


def merge(doc_ids: list[int], metadata_document_id: Optional[int] = None):
    logger.info(
        f"Attempting to merge {len(doc_ids)} documents into a single document.",
    )
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs = []
    import pikepdf

    merged_pdf = pikepdf.new()
    version = merged_pdf.pdf_version
    # use doc_ids to preserve order
    for doc_id in doc_ids:
        doc = qs.get(id=doc_id)
        try:
            with pikepdf.open(str(doc.source_path)) as pdf:
                version = max(version, pdf.pdf_version)
                merged_pdf.pages.extend(pdf.pages)
            affected_docs.append(doc.id)
        except Exception as e:
            logger.exception(
                f"Error merging document {doc.id}, it will not be included in the merge: {e}",
            )
    if len(affected_docs) == 0:
        logger.warning("No documents were merged")
        return "OK"

    filepath = os.path.join(
        settings.SCRATCH_DIR,
        f"{'_'.join([str(doc_id) for doc_id in doc_ids])[:100]}_merged.pdf",
    )
    merged_pdf.remove_unreferenced_resources()
    merged_pdf.save(filepath, min_version=version)
    merged_pdf.close()

    if metadata_document_id:
        metadata_document = qs.get(id=metadata_document_id)
        if metadata_document is not None:
            overrides = DocumentMetadataOverrides.from_document(metadata_document)
            overrides.title = metadata_document.title + " (merged)"
    else:
        overrides = DocumentMetadataOverrides()

    logger.info("Adding merged document to the task queue.")
    consume_file.delay(
        ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=filepath,
        ),
        overrides,
    )

    return "OK"


def split(doc_ids: list[int], pages: list[list[int]]):
    logger.info(
        f"Attempting to split document {doc_ids[0]} into {len(pages)} documents",
    )
    doc = Document.objects.get(id=doc_ids[0])
    import pikepdf

    try:
        with pikepdf.open(doc.source_path) as pdf:
            for idx, split_doc in enumerate(pages):
                dst = pikepdf.new()
                for page in split_doc:
                    dst.pages.append(pdf.pages[page - 1])
                filepath = os.path.join(
                    settings.SCRATCH_DIR,
                    f"{doc.id}_{split_doc[0]}-{split_doc[-1]}.pdf",
                )
                dst.remove_unreferenced_resources()
                dst.save(filepath)
                dst.close()

                overrides = DocumentMetadataOverrides().from_document(doc)
                overrides.title = f"{doc.title} (split {idx + 1})"
                logger.info(
                    f"Adding split document with pages {split_doc} to the task queue.",
                )
                consume_file.delay(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=filepath,
                    ),
                    overrides,
                )
    except Exception as e:
        logger.exception(f"Error splitting document {doc.id}: {e}")

    return "OK"
