from __future__ import annotations

import hashlib
import itertools
import logging
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

from celery import chain
from celery import chord
from celery import group
from celery import shared_task
from django.conf import settings
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
from documents.permissions import set_permissions_for_object
from documents.plugins.helpers import DocumentsStatusManager
from documents.tasks import bulk_update_documents
from documents.tasks import consume_file
from documents.tasks import update_document_content_maybe_archive_file

if TYPE_CHECKING:
    from django.contrib.auth.models import User

logger: logging.Logger = logging.getLogger("paperless.bulk_edit")


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
    qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(tags__id=tag)).only("pk")
    affected_docs = list(qs.values_list("pk", flat=True))

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.bulk_create(
        [DocumentTagRelationship(document_id=doc, tag_id=tag) for doc in affected_docs],
    )

    bulk_update_documents.delay(document_ids=affected_docs)

    return "OK"


def remove_tag(doc_ids: list[int], tag: int) -> Literal["OK"]:
    qs = Document.objects.filter(Q(id__in=doc_ids) & Q(tags__id=tag)).only("pk")
    affected_docs = list(qs.values_list("pk", flat=True))

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.filter(
        Q(document_id__in=affected_docs) & Q(tag_id=tag),
    ).delete()

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
    set_permissions,
    *,
    owner=None,
    merge=False,
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
        else:
            overrides = DocumentMetadataOverrides()
    else:
        overrides = DocumentMetadataOverrides()

    if user is not None:
        overrides.owner_id = user.id

    logger.info("Adding merged document to the task queue.")

    consume_task = consume_file.s(
        ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=filepath,
        ),
        overrides,
    )

    if delete_originals:
        logger.info(
            "Queueing removal of original documents after consumption of merged document",
        )
        chain(consume_task, delete.si(affected_docs)).delay()
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
                logger.info(
                    "Queueing removal of original document after consumption of the split documents",
                )
                chord(header=consume_tasks, body=delete.si([doc.id])).delay()
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


def reflect_doclinks(
    document: Document,
    field: CustomField,
    target_doc_ids: list[int],
):
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
):
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


def get_reorganized_title(original_title: str, suffix_word: str = "reorganized") -> str:
    """
    Generate a smart title for reorganized documents that handles incremental numbering.

    Args:
        original_title: The original document title
        suffix_word: The word to use for the suffix (default: "reorganized")

    Returns:
        A title with an appropriate reorganized suffix

    Examples:
        "Document" -> "Document (reorganized)"
        "Document (reorganized)" -> "Document (reorganized 1)"
        "Document (reorganized 1)" -> "Document (reorganized 2)"
        "Document (reorganized 5)" -> "Document (reorganized 6)"
    """
    # Create regex pattern to match existing reorganized suffixes
    pattern = rf"\s+\({re.escape(suffix_word)}(?:\s+(\d+))?\)$"

    match = re.search(pattern, original_title)

    if match:
        # Extract the base title without the suffix
        base_title = original_title[: match.start()]

        # Get the current number (None if no number exists)
        current_num_str = match.group(1)

        new_num = 1 if current_num_str is None else int(current_num_str) + 1

        return f"{base_title} ({suffix_word} {new_num})"
    else:
        # No existing suffix, add "(reorganized)"
        return f"{original_title} ({suffix_word})"


def reorganize(
    doc_ids: list[int],
    processing_instruction: dict,
    *,
    delete_original: bool = False,
    user: User | None = None,
) -> Literal["OK"]:
    """
    Reorganize a PDF document according to pdf-reorganizer processing instructions.

    The processing_instruction should have the format:
    {
        "src": ["filename.pdf"],
        "docs": [
            [1, 2],  # Simple page numbers
            [3, {"p": 5, "r": 90}],  # Page with rotation
            [{"p": 6, "c": "Comment"}]  # Page with comment
        ]
    }

    Where each doc in "docs" represents a new document to be created,
    and each page can be either a simple number or an object with:
    - p: page number (required)
    - r: rotation in degrees (optional, 90/180/270)
    - c: comment (optional, currently not used)
    - s: source document index (optional, defaults to 0)
    """
    if len(doc_ids) != 1:
        raise ValueError("Reorganize method only supports one document")

    logger.info(
        f"Attempting to reorganize document {doc_ids[0]} with processing instruction",
    )
    doc = Document.objects.get(id=doc_ids[0])

    import pikepdf

    # Validate processing instruction format
    if not isinstance(processing_instruction, dict):
        raise ValueError("Processing instruction must be a dictionary")
    if "docs" not in processing_instruction:
        raise ValueError("Processing instruction must contain 'docs' array")
    if not isinstance(processing_instruction["docs"], list):
        raise ValueError("'docs' must be an array")
    if len(processing_instruction["docs"]) == 0:
        raise ValueError("'docs' array cannot be empty")

    docs_to_create = processing_instruction["docs"]
    consume_tasks = []

    try:
        # Use archive version if available (contains already processed content),
        # otherwise fall back to source path
        doc_path = doc.archive_path if doc.has_archive_version else doc.source_path
        with pikepdf.open(doc_path) as source_pdf:
            total_pages = len(source_pdf.pages)

            # Process each document to be created
            for doc_idx, doc_pages in enumerate(docs_to_create):
                if not isinstance(doc_pages, list) or len(doc_pages) == 0:
                    logger.warning(
                        f"Skipping empty or invalid document at index {doc_idx}",
                    )
                    continue

                # Create new PDF for this document
                dst_pdf = pikepdf.new()
                doc_title_pages = []

                for page_spec in doc_pages:
                    # Handle both simple page numbers and page objects
                    if isinstance(page_spec, int):
                        page_num = page_spec
                        rotation = 0
                        # comment = None
                    elif isinstance(page_spec, dict):
                        if "p" not in page_spec:
                            logger.warning(
                                f"Page specification missing 'p' field: {page_spec}",
                            )
                            continue
                        page_num = page_spec["p"]
                        rotation = page_spec.get("r", 0)
                        # comment = page_spec.get("c", None)
                        # source_idx = page_spec.get("s", 0)  # Currently unused, assumes single source
                    else:
                        logger.warning(f"Invalid page specification: {page_spec}")
                        continue

                    # Validate page number
                    if (
                        not isinstance(page_num, int)
                        or page_num < 1
                        or page_num > total_pages
                    ):
                        logger.warning(
                            f"Invalid page number {page_num}, total pages: {total_pages}",
                        )
                        continue

                    # Copy the page from source
                    source_page = source_pdf.pages[
                        page_num - 1
                    ]  # Convert to 0-based index
                    dst_pdf.pages.append(source_page)

                    # Apply rotation if specified
                    if rotation and rotation in [90, 180, 270]:
                        dst_pdf.pages[-1].rotate(rotation, relative=False)
                        logger.debug(f"Applied rotation {rotation}° to page {page_num}")
                    elif rotation != 0:
                        logger.warning(
                            f"Invalid rotation {rotation}° for page {page_num}, skipping rotation",
                        )

                    # Store page info for filename generation
                    doc_title_pages.append(str(page_num))

                    # Note: comments are not currently processed but could be added as metadata
                    # if comment:
                    #    logger.debug(f"Page {page_num} has comment: {comment}")

                if len(dst_pdf.pages) == 0:
                    logger.warning(
                        f"No valid pages found for document {doc_idx}, skipping",
                    )
                    dst_pdf.close()
                    continue

                # Generate filename and save
                page_range = (
                    f"{doc_title_pages[0]}-{doc_title_pages[-1]}"
                    if len(doc_title_pages) > 1
                    else doc_title_pages[0]
                )
                filepath = (
                    Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR))
                    / f"{doc.id}_{page_range}_reorganized.pdf"
                )

                dst_pdf.remove_unreferenced_resources()
                dst_pdf.save(filepath)
                dst_pdf.close()

                # Prepare metadata for new document
                overrides = DocumentMetadataOverrides().from_document(doc)
                if len(docs_to_create) == 1:
                    # Single document - keep original title with suffix if reorganized differently
                    overrides.title = get_reorganized_title(doc.title)
                else:
                    # Multiple documents - add part number
                    overrides.title = f"{doc.title} (part {doc_idx + 1})"

                if user is not None:
                    overrides.owner_id = user.id

                logger.info(
                    f"Adding reorganized document part {doc_idx + 1} with pages {doc_title_pages} to the task queue",
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

        # Execute all consume tasks
        if consume_tasks:
            if delete_original:
                logger.info(
                    "Queueing removal of original document after consumption of the reorganized documents",
                )
                chord(header=consume_tasks, body=delete.si([doc.id])).delay()
            else:
                for task in consume_tasks:
                    task.delay()

            logger.info(
                f"Successfully reorganized document {doc.id} into {len(consume_tasks)} new documents",
            )
        else:
            logger.warning(
                f"No valid documents were created from reorganization of document {doc.id}",
            )

    except Exception as e:
        logger.exception(f"Error reorganizing document {doc.id}: {e}")
        raise

    return "OK"
