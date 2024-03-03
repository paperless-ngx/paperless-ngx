import hashlib
import itertools
import logging
import os
from typing import Optional

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
from paperless import settings

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
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs = []
    import pikepdf

    for doc in qs:
        try:
            with pikepdf.open(doc.source_path, allow_overwriting_input=True) as pdf:
                for page in pdf.pages:
                    page.rotate(degrees, relative=True)
                pdf.save()
                doc.checksum = hashlib.md5(doc.source_file.read()).hexdigest()
                doc.save()
                update_document_archive_file.delay(
                    document_id=doc.id,
                )
                logger.info(f"Rotated document {doc.id} ({path}) by {degrees} degrees")
                affected_docs.append(doc.id)
        except Exception as e:
            logger.exception(f"Error rotating document {doc.id}", e)

    if len(affected_docs) > 0:
        bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def merge(doc_ids: list[int], metadata_document_id: Optional[int] = None):
    qs = Document.objects.filter(id__in=doc_ids)
    import pikepdf

    merged_pdf = pikepdf.new()
    # use doc_ids to preserve order
    for doc_id in doc_ids:
        doc = qs.get(id=doc_id)
        if doc is None:
            continue
        path = os.path.join(settings.ORIGINALS_DIR, str(doc.filename))
        try:
            with pikepdf.open(path, allow_overwriting_input=True) as pdf:
                merged_pdf.pages.extend(pdf.pages)
        except Exception as e:
            logger.exception(
                f"Error merging document {doc.id}, it will not be included in the merge",
                e,
            )

    filepath = os.path.join(
        settings.CONSUMPTION_DIR,
        f"merged_{('_'.join([str(doc_id) for doc_id in doc_ids]))[:100]}.pdf",
    )
    merged_pdf.save(filepath)

    overrides = DocumentMetadataOverrides()

    if metadata_document_id:
        metadata_document = qs.get(id=metadata_document_id)
        if metadata_document is not None:
            overrides.title = metadata_document.title + " (merged)"
            overrides.correspondent_id = (
                metadata_document.correspondent.pk
                if metadata_document.correspondent
                else None
            )
            overrides.document_type_id = (
                metadata_document.document_type.pk
                if metadata_document.document_type
                else None
            )
            overrides.storage_path_id = (
                metadata_document.storage_path.pk
                if metadata_document.storage_path
                else None
            )
            overrides.tag_ids = list(
                metadata_document.tags.values_list("id", flat=True),
            )
            # Include owner and permissions?

    logger.info("Adding merged document to the task queue.")
    consume_file.delay(
        ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=filepath,
        ),
        overrides,
    )

    return "OK"
