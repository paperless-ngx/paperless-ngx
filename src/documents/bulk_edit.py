from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

from celery import chord
from celery import group
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import set_permissions_for_object
from documents.plugins.helpers import DocumentsStatusManager
from documents.tasks import bulk_update_documents
from documents.tasks import consume_file
from documents.tasks import update_document_content_maybe_archive_file

if TYPE_CHECKING:
    from django.contrib.auth.models import User

logger: logging.Logger = logging.getLogger("paperless.bulk_edit")


@shared_task(bind=True)
def restore_archive_serial_numbers_task(
    self,
    backup: dict[int, int | None],
    *args,
    **kwargs,
) -> None:
    restore_archive_serial_numbers(backup)


def release_archive_serial_numbers(doc_ids: list[int]) -> dict[int, int | None]:
    """
    Clears ASNs on documents that are about to be replaced so new documents
    can be assigned ASNs without uniqueness collisions. Returns a backup map
    of doc_id -> previous ASN for potential restoration.
    """
    qs = Document.objects.filter(
        id__in=doc_ids,
        archive_serial_number__isnull=False,
    ).only("pk", "archive_serial_number")
    backup = dict(qs.values_list("pk", "archive_serial_number"))
    qs.update(archive_serial_number=None)
    logger.info(f"Released archive serial numbers for documents {list(backup.keys())}")
    return backup


def restore_archive_serial_numbers(backup: dict[int, int | None]) -> None:
    """
    Restores ASNs using the provided backup map, intended for
    rollback when replacement consumption fails.
    """
    for doc_id, asn in backup.items():
        Document.objects.filter(pk=doc_id).update(archive_serial_number=asn)
    logger.info(f"Restored archive serial numbers for documents {list(backup.keys())}")


def set_correspondent(
    doc_ids: list[int],
    correspondent: Correspondent,
) -> Literal["OK"]:
    if correspondent:
        correspondent = Correspondent.objects.only("pk").get(id=correspondent)

    qs = (
        Document.objects.filter(Q(id__in=doc_ids) & ~Q(correspondent=correspondent))
        .select_related("correspondent")
        .only("pk", "correspondent__id")
    )
    affected_docs = list(qs.values_list("pk", flat=True))
    qs.update(correspondent=correspondent)

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def set_storage_path(doc_ids: list[int], storage_path: StoragePath) -> Literal["OK"]:
    if storage_path:
        storage_path = StoragePath.objects.only("pk").get(id=storage_path)

    qs = (
        Document.objects.filter(
            Q(id__in=doc_ids) & ~Q(storage_path=storage_path),
        )
        .select_related("storage_path")
        .only("pk", "storage_path__id")
    )
    affected_docs = list(qs.values_list("pk", flat=True))
    qs.update(storage_path=storage_path)

    bulk_update_documents.delay(
        document_ids=affected_docs,
    )

    return "OK"


def set_document_type(doc_ids: list[int], document_type: DocumentType) -> Literal["OK"]:
    if document_type:
        document_type = DocumentType.objects.only("pk").get(id=document_type)

    qs = (
        Document.objects.filter(Q(id__in=doc_ids) & ~Q(document_type=document_type))
        .select_related("document_type")
        .only("pk", "document_type__id")
    )
    affected_docs = list(qs.values_list("pk", flat=True))
    qs.update(document_type=document_type)

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def add_tag(doc_ids: list[int], tag: int) -> Literal["OK"]:
    tag_obj = Tag.objects.get(pk=tag)
    tags_to_add = [tag_obj, *tag_obj.get_ancestors()]

    DocumentTagRelationship = Document.tags.through
    to_create = []
    affected_docs: set[int] = set()

    for t in tags_to_add:
        qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(tags__id=t.id)).only("pk")
        doc_ids_missing_tag = list(qs.values_list("pk", flat=True))
        affected_docs.update(doc_ids_missing_tag)
        to_create.extend(
            DocumentTagRelationship(document_id=doc, tag_id=t.id)
            for doc in doc_ids_missing_tag
        )

    if to_create:
        DocumentTagRelationship.objects.bulk_create(to_create)

    if affected_docs:
        bulk_update_documents.delay(document_ids=list(affected_docs))

    return "OK"


def remove_tag(doc_ids: list[int], tag: int) -> Literal["OK"]:
    tag_obj = Tag.objects.get(pk=tag)
    tag_ids = [tag_obj.id, *tag_obj.get_descendants_pks()]

    DocumentTagRelationship = Document.tags.through
    qs = DocumentTagRelationship.objects.filter(
        document_id__in=doc_ids,
        tag_id__in=tag_ids,
    )
    affected_docs = list(qs.values_list("document_id", flat=True).distinct())
    qs.delete()

    if affected_docs:
        bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def modify_tags(
    doc_ids: list[int],
    add_tags: list[int],
    remove_tags: list[int],
) -> Literal["OK"]:
    qs = Document.objects.filter(id__in=doc_ids).only("pk")
    affected_docs = list(qs.values_list("pk", flat=True))
    DocumentTagRelationship = Document.tags.through

    # add with all ancestors
    expanded_add_tags: set[int] = set()
    add_tag_objects = Tag.objects.filter(pk__in=add_tags)
    for t in add_tag_objects:
        expanded_add_tags.add(int(t.id))
        expanded_add_tags.update(int(pk) for pk in t.get_ancestors_pks())

    # remove with all descendants
    expanded_remove_tags: set[int] = set()
    remove_tag_objects = Tag.objects.filter(pk__in=remove_tags)
    for t in remove_tag_objects:
        expanded_remove_tags.add(int(t.id))
        expanded_remove_tags.update(int(pk) for pk in t.get_descendants_pks())

    try:
        with transaction.atomic():
            if expanded_remove_tags:
                DocumentTagRelationship.objects.filter(
                    document_id__in=affected_docs,
                    tag_id__in=expanded_remove_tags,
                ).delete()

            to_create = []
            if expanded_add_tags:
                existing_pairs = set(
                    DocumentTagRelationship.objects.filter(
                        document_id__in=affected_docs,
                        tag_id__in=expanded_add_tags,
                    ).values_list("document_id", "tag_id"),
                )

                to_create = [
                    DocumentTagRelationship(document_id=doc, tag_id=tag)
                    for doc in affected_docs
                    for tag in expanded_add_tags
                    if (doc, tag) not in existing_pairs
                ]

                if to_create:
                    DocumentTagRelationship.objects.bulk_create(
                        to_create,
                        ignore_conflicts=True,
                    )

            if affected_docs:
                bulk_update_documents.delay(document_ids=affected_docs)
    except Exception as e:
        logger.error(f"Error modifying tags: {e}")
        return "ERROR"

    return "OK"


def modify_custom_fields(
    doc_ids: list[int],
    add_custom_fields: list[int] | dict,
    remove_custom_fields: list[int],
) -> Literal["OK"]:
    qs = Document.objects.filter(id__in=doc_ids).only("pk")
    affected_docs = list(qs.values_list("pk", flat=True))
    # Ensure add_custom_fields is a list of tuples, supports old API
    add_custom_fields = (
        add_custom_fields.items()
        if isinstance(add_custom_fields, dict)
        else [(field, None) for field in add_custom_fields]
    )

    custom_fields = CustomField.objects.filter(
        id__in=[int(field) for field, _ in add_custom_fields],
    ).distinct()
    for field_id, value in add_custom_fields:
        for doc_id in affected_docs:
            defaults = {}
            custom_field = custom_fields.get(id=field_id)
            if custom_field:
                value_field = CustomFieldInstance.TYPE_TO_DATA_STORE_NAME_MAP[
                    custom_field.data_type
                ]
                defaults[value_field] = value
                if (
                    custom_field.data_type == CustomField.FieldDataType.DOCUMENTLINK
                    and value
                    and doc_id in value
                ):
                    # Prevent self-linking
                    continue
            CustomFieldInstance.objects.update_or_create(
                document_id=doc_id,
                field_id=field_id,
                defaults=defaults,
            )
            if custom_field.data_type == CustomField.FieldDataType.DOCUMENTLINK:
                doc = Document.objects.get(id=doc_id)
                reflect_doclinks(doc, custom_field, value)

    # For doc link fields that are being removed, remove symmetrical links
    for doclink_being_removed_instance in CustomFieldInstance.objects.filter(
        document_id__in=affected_docs,
        field__id__in=remove_custom_fields,
        field__data_type=CustomField.FieldDataType.DOCUMENTLINK,
        value_document_ids__isnull=False,
    ):
        for target_doc_id in doclink_being_removed_instance.value:
            remove_doclink(
                document=Document.objects.get(
                    id=doclink_being_removed_instance.document.id,
                ),
                field=doclink_being_removed_instance.field,
                target_doc_id=target_doc_id,
            )

    # Finally, remove the custom fields
    CustomFieldInstance.objects.filter(
        document_id__in=affected_docs,
        field_id__in=remove_custom_fields,
    ).hard_delete()

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


@shared_task
def delete(doc_ids: list[int]) -> Literal["OK"]:
    try:
        Document.objects.filter(id__in=doc_ids).delete()

        from documents import index

        with index.open_index_writer() as writer:
            for id in doc_ids:
                index.remove_document_by_id(writer, id)

        status_mgr = DocumentsStatusManager()
        status_mgr.send_documents_deleted(doc_ids)
    except Exception as e:
        if "Data too long for column" in str(e):
            logger.warning(
                "Detected a possible incompatible database column. See https://docs.paperless-ngx.com/troubleshooting/#convert-uuid-field",
            )
        logger.error(f"Error deleting documents: {e!s}")

    return "OK"


def reprocess(doc_ids: list[int]) -> Literal["OK"]:
    for document_id in doc_ids:
        update_document_content_maybe_archive_file.delay(
            document_id=document_id,
        )

    return "OK"


def set_permissions(
    doc_ids: list[int],
    set_permissions: dict,
    *,
    owner: User | None = None,
    merge: bool = False,
) -> Literal["OK"]:
    qs = Document.objects.filter(id__in=doc_ids).select_related("owner")

    if merge:
        # If merging, only set owner for documents that don't have an owner
        qs.filter(owner__isnull=True).update(owner=owner)
    else:
        qs.update(owner=owner)

    for doc in qs:
        set_permissions_for_object(permissions=set_permissions, object=doc, merge=merge)

    affected_docs = list(qs.values_list("pk", flat=True))

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def rotate(doc_ids: list[int], degrees: int) -> Literal["OK"]:
    logger.info(
        f"Attempting to rotate {len(doc_ids)} documents by {degrees} degrees.",
    )
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs: list[int] = []
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
                    update_document_content_maybe_archive_file.s(
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
        bulk_update_task = bulk_update_documents.si(document_ids=affected_docs)
        chord(header=rotate_tasks, body=bulk_update_task).delay()

    return "OK"


def merge(
    doc_ids: list[int],
    *,
    metadata_document_id: int | None = None,
    delete_originals: bool = False,
    archive_fallback: bool = False,
    user: User | None = None,
) -> Literal["OK"]:
    logger.info(
        f"Attempting to merge {len(doc_ids)} documents into a single document.",
    )
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs: list[int] = []
    import pikepdf

    merged_pdf = pikepdf.new()
    version: str = merged_pdf.pdf_version
    handoff_asn: int | None = None
    # use doc_ids to preserve order
    for doc_id in doc_ids:
        doc = qs.get(id=doc_id)
        try:
            doc_path = (
                doc.archive_path
                if archive_fallback
                and doc.mime_type != "application/pdf"
                and doc.has_archive_version
                else doc.source_path
            )
            with pikepdf.open(str(doc_path)) as pdf:
                version = max(version, pdf.pdf_version)
                merged_pdf.pages.extend(pdf.pages)
            affected_docs.append(doc.id)
            if handoff_asn is None and doc.archive_serial_number is not None:
                handoff_asn = doc.archive_serial_number
        except Exception as e:
            logger.exception(
                f"Error merging document {doc.id}, it will not be included in the merge: {e}",
            )
    if len(affected_docs) == 0:
        logger.warning("No documents were merged")
        return "OK"

    filepath = (
        Path(
            tempfile.mkdtemp(dir=settings.SCRATCH_DIR),
        )
        / f"{'_'.join([str(doc_id) for doc_id in affected_docs])[:100]}_merged.pdf"
    )
    merged_pdf.remove_unreferenced_resources()
    merged_pdf.save(filepath, min_version=version)
    merged_pdf.close()

    if metadata_document_id:
        metadata_document = qs.get(id=metadata_document_id)
        if metadata_document is not None:
            overrides: DocumentMetadataOverrides = (
                DocumentMetadataOverrides.from_document(metadata_document)
            )
            overrides.title = metadata_document.title + " (merged)"
            if metadata_document.archive_serial_number is not None:
                handoff_asn = metadata_document.archive_serial_number
        else:
            overrides = DocumentMetadataOverrides()
    else:
        overrides = DocumentMetadataOverrides()

    if user is not None:
        overrides.owner_id = user.id
    if not delete_originals:
        overrides.skip_asn_if_exists = True

    if delete_originals and handoff_asn is not None:
        overrides.asn = handoff_asn

    logger.info("Adding merged document to the task queue.")

    consume_task = consume_file.s(
        ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=filepath,
        ),
        overrides,
    )

    if delete_originals:
        backup = release_archive_serial_numbers(affected_docs)
        logger.info(
            "Queueing removal of original documents after consumption of merged document",
        )
        try:
            consume_task.apply_async(
                link=[delete.si(affected_docs)],
                link_error=[restore_archive_serial_numbers_task.s(backup)],
            )
        except Exception:
            restore_archive_serial_numbers(backup)
            raise
        else:
            consume_task.delay()

    return "OK"


def split(
    doc_ids: list[int],
    pages: list[list[int]],
    *,
    delete_originals: bool = False,
    user: User | None = None,
) -> Literal["OK"]:
    logger.info(
        f"Attempting to split document {doc_ids[0]} into {len(pages)} documents",
    )
    doc = Document.objects.get(id=doc_ids[0])
    import pikepdf

    consume_tasks = []

    try:
        with pikepdf.open(doc.source_path) as pdf:
            for idx, split_doc in enumerate(pages):
                dst: pikepdf.Pdf = pikepdf.new()
                for page in split_doc:
                    dst.pages.append(pdf.pages[page - 1])
                filepath: Path = (
                    Path(
                        tempfile.mkdtemp(dir=settings.SCRATCH_DIR),
                    )
                    / f"{doc.id}_{split_doc[0]}-{split_doc[-1]}.pdf"
                )
                dst.remove_unreferenced_resources()
                dst.save(filepath)
                dst.close()

                overrides: DocumentMetadataOverrides = (
                    DocumentMetadataOverrides().from_document(doc)
                )
                overrides.title = f"{doc.title} (split {idx + 1})"
                if user is not None:
                    overrides.owner_id = user.id
                if not delete_originals:
                    overrides.skip_asn_if_exists = True
                logger.info(
                    f"Adding split document with pages {split_doc} to the task queue.",
                )
                consume_tasks.append(
                    consume_file.s(
                        ConsumableDocument(
                            source=DocumentSource.ConsumeFolder,
                            original_file=filepath,
                        ),
                        overrides,
                    ),
                )

            if delete_originals:
                backup = release_archive_serial_numbers([doc.id])
                logger.info(
                    "Queueing removal of original document after consumption of the split documents",
                )
                try:
                    chord(
                        header=consume_tasks,
                        body=delete.si([doc.id]),
                    ).apply_async(
                        link_error=[restore_archive_serial_numbers_task.s(backup)],
                    )
                except Exception:
                    restore_archive_serial_numbers(backup)
                    raise
            else:
                group(consume_tasks).delay()

    except Exception as e:
        logger.exception(f"Error splitting document {doc.id}: {e}")

    return "OK"


def delete_pages(doc_ids: list[int], pages: list[int]) -> Literal["OK"]:
    logger.info(
        f"Attempting to delete pages {pages} from {len(doc_ids)} documents",
    )
    doc = Document.objects.get(id=doc_ids[0])
    pages = sorted(pages)  # sort pages to avoid index issues
    import pikepdf

    try:
        with pikepdf.open(doc.source_path, allow_overwriting_input=True) as pdf:
            offset = 1  # pages are 1-indexed
            for page_num in pages:
                pdf.pages.remove(pdf.pages[page_num - offset])
                offset += 1  # remove() changes the index of the pages
            pdf.remove_unreferenced_resources()
            pdf.save()
            doc.checksum = hashlib.md5(doc.source_path.read_bytes()).hexdigest()
            if doc.page_count is not None:
                doc.page_count = doc.page_count - len(pages)
            doc.save()
            update_document_content_maybe_archive_file.delay(document_id=doc.id)
            logger.info(f"Deleted pages {pages} from document {doc.id}")
    except Exception as e:
        logger.exception(f"Error deleting pages from document {doc.id}: {e}")

    return "OK"


def edit_pdf(
    doc_ids: list[int],
    operations: list[dict[str, int]],
    *,
    delete_original: bool = False,
    update_document: bool = False,
    include_metadata: bool = True,
    user: User | None = None,
) -> Literal["OK"]:
    """
    Operations is a list of dictionaries describing the final PDF pages.
    Each entry must contain the original page number in `page` and may
    specify `rotate` in degrees and `doc` indicating the output
    document index (for splitting). Pages omitted from the list are
    discarded.
    """

    logger.info(
        f"Editing PDF of document {doc_ids[0]} with {len(operations)} operations",
    )
    doc = Document.objects.get(id=doc_ids[0])
    import pikepdf

    pdf_docs: list[pikepdf.Pdf] = []

    try:
        with pikepdf.open(doc.source_path) as src:
            # prepare output documents
            max_idx = max(op.get("doc", 0) for op in operations)
            pdf_docs = [pikepdf.new() for _ in range(max_idx + 1)]

            if update_document and len(pdf_docs) > 1:
                logger.error(
                    "Update requested but multiple output documents specified",
                )
                raise ValueError("Multiple output documents specified")

            for op in operations:
                dst = pdf_docs[op.get("doc", 0)]
                page = src.pages[op["page"] - 1]
                dst.pages.append(page)
                if op.get("rotate"):
                    dst.pages[-1].rotate(op["rotate"], relative=True)

        if update_document:
            temp_path = doc.source_path.with_suffix(".tmp.pdf")
            pdf = pdf_docs[0]
            pdf.remove_unreferenced_resources()
            # save the edited PDF to a temporary file in case of errors
            pdf.save(temp_path)
            # replace the original document with the edited one
            temp_path.replace(doc.source_path)
            doc.checksum = hashlib.md5(doc.source_path.read_bytes()).hexdigest()
            doc.page_count = len(pdf.pages)
            doc.save()
            update_document_content_maybe_archive_file.delay(document_id=doc.id)
        else:
            consume_tasks = []
            overrides = (
                DocumentMetadataOverrides().from_document(doc)
                if include_metadata
                else DocumentMetadataOverrides()
            )
            if user is not None:
                overrides.owner_id = user.id
            if not delete_original:
                overrides.skip_asn_if_exists = True
            if delete_original and len(pdf_docs) == 1:
                overrides.asn = doc.archive_serial_number
            for idx, pdf in enumerate(pdf_docs, start=1):
                filepath: Path = (
                    Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR))
                    / f"{doc.id}_edit_{idx}.pdf"
                )
                pdf.remove_unreferenced_resources()
                pdf.save(filepath)
                consume_tasks.append(
                    consume_file.s(
                        ConsumableDocument(
                            source=DocumentSource.ConsumeFolder,
                            original_file=filepath,
                        ),
                        overrides,
                    ),
                )

            if delete_original:
                backup = release_archive_serial_numbers([doc.id])
                try:
                    chord(
                        header=consume_tasks,
                        body=delete.si([doc.id]),
                    ).apply_async(
                        link_error=[restore_archive_serial_numbers_task.s(backup)],
                    )
                except Exception:
                    restore_archive_serial_numbers(backup)
                    raise
            else:
                group(consume_tasks).delay()

    except Exception as e:
        logger.exception(f"Error editing document {doc.id}: {e}")
        raise ValueError(
            f"An error occurred while editing the document: {e}",
        ) from e

    return "OK"


def remove_password(
    doc_ids: list[int],
    password: str,
    *,
    update_document: bool = False,
    delete_original: bool = False,
    include_metadata: bool = True,
    user: User | None = None,
) -> Literal["OK"]:
    """
    Remove password protection from PDF documents.
    """
    import pikepdf

    for doc_id in doc_ids:
        doc = Document.objects.get(id=doc_id)
        try:
            logger.info(
                f"Attempting password removal from document {doc_ids[0]}",
            )
            with pikepdf.open(doc.source_path, password=password) as pdf:
                temp_path = doc.source_path.with_suffix(".tmp.pdf")
                pdf.remove_unreferenced_resources()
                pdf.save(temp_path)

                if update_document:
                    # replace the original document with the unprotected one
                    temp_path.replace(doc.source_path)
                    doc.checksum = hashlib.md5(doc.source_path.read_bytes()).hexdigest()
                    doc.page_count = len(pdf.pages)
                    doc.save()
                    update_document_content_maybe_archive_file.delay(document_id=doc.id)
                else:
                    consume_tasks = []
                    overrides = (
                        DocumentMetadataOverrides().from_document(doc)
                        if include_metadata
                        else DocumentMetadataOverrides()
                    )
                    if user is not None:
                        overrides.owner_id = user.id

                    filepath: Path = (
                        Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR))
                        / f"{doc.id}_unprotected.pdf"
                    )
                    temp_path.replace(filepath)
                    consume_tasks.append(
                        consume_file.s(
                            ConsumableDocument(
                                source=DocumentSource.ConsumeFolder,
                                original_file=filepath,
                            ),
                            overrides,
                        ),
                    )

                    if delete_original:
                        chord(header=consume_tasks, body=delete.si([doc.id])).delay()
                    else:
                        group(consume_tasks).delay()

        except Exception as e:
            logger.exception(f"Error removing password from document {doc.id}: {e}")
            raise ValueError(
                f"An error occurred while removing the password: {e}",
            ) from e

    return "OK"


def reflect_doclinks(
    document: Document,
    field: CustomField,
    target_doc_ids: list[int],
) -> None:
    """
    Add or remove 'symmetrical' links to `document` on all `target_doc_ids`
    """

    if target_doc_ids is None:
        target_doc_ids = []

    # Check if any documents are going to be removed from the current list of links and remove the symmetrical links
    current_field_instance = CustomFieldInstance.objects.filter(
        field=field,
        document=document,
    ).first()
    if current_field_instance is not None and current_field_instance.value is not None:
        for doc_id in current_field_instance.value:
            if doc_id not in target_doc_ids:
                remove_doclink(
                    document=document,
                    field=field,
                    target_doc_id=doc_id,
                )

    # Create an instance if target doc doesn't have this field or append it to an existing one
    existing_custom_field_instances = {
        custom_field.document_id: custom_field
        for custom_field in CustomFieldInstance.objects.filter(
            field=field,
            document_id__in=target_doc_ids,
        )
    }
    custom_field_instances_to_create = []
    custom_field_instances_to_update = []
    for target_doc_id in target_doc_ids:
        target_doc_field_instance = existing_custom_field_instances.get(
            target_doc_id,
        )
        if target_doc_field_instance is None:
            custom_field_instances_to_create.append(
                CustomFieldInstance(
                    document_id=target_doc_id,
                    field=field,
                    value_document_ids=[document.id],
                ),
            )
        elif target_doc_field_instance.value is None:
            target_doc_field_instance.value_document_ids = [document.id]
            custom_field_instances_to_update.append(target_doc_field_instance)
        elif document.id not in target_doc_field_instance.value:
            target_doc_field_instance.value_document_ids.append(document.id)
            custom_field_instances_to_update.append(target_doc_field_instance)

    CustomFieldInstance.objects.bulk_create(custom_field_instances_to_create)
    CustomFieldInstance.objects.bulk_update(
        custom_field_instances_to_update,
        ["value_document_ids"],
    )
    Document.objects.filter(id__in=target_doc_ids).update(modified=timezone.now())


def remove_doclink(
    document: Document,
    field: CustomField,
    target_doc_id: int,
) -> None:
    """
    Removes a 'symmetrical' link to `document` from the target document's existing custom field instance
    """
    target_doc_field_instance = CustomFieldInstance.objects.filter(
        document_id=target_doc_id,
        field=field,
    ).first()
    if (
        target_doc_field_instance is not None
        and document.id in target_doc_field_instance.value
    ):
        target_doc_field_instance.value.remove(document.id)
        target_doc_field_instance.save()
    Document.objects.filter(id=target_doc_id).update(modified=timezone.now())
