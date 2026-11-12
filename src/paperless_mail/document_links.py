"""Link only documents returned by one email's consumption batch."""

from functools import partial

from django.db import transaction
from django.utils import timezone

from documents.caching import clear_document_caches
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.permissions import permitted_document_ids
from documents.search import get_backend
from paperless_mail.models import MailRule


class MailDocumentLinkError(ValueError):
    """The complete email batch cannot safely be linked."""


def _refresh_documents(document_ids: list[int]) -> None:
    # Do not emit document_updated: linking must not rerun user workflows.
    for document_id in document_ids:
        clear_document_caches(document_id)
    with get_backend().batch_update() as batch:
        batch.add_or_update_ids(document_ids)


def link_mail_documents(results: list, rule: MailRule) -> None:
    """Add direct, symmetric links without extending existing link groups.

    A duplicate belongs to this batch because the consumer identified its exact
    content. Existing neighbours of that document do not belong to this batch.
    Reject incomplete batches before the caller performs a destructive mail action.
    """
    field_id = rule.assign_document_link_field_id
    if field_id is None:
        return

    document_ids = set()
    for result in results:
        if not isinstance(result, dict):
            raise MailDocumentLinkError("Email consumption did not return a document.")
        if "document_id" in result and "duplicate_of" not in result:
            document_id = result["document_id"]
        elif "duplicate_of" in result and "document_id" not in result:
            if result.get("duplicate_in_trash") is not False:
                raise MailDocumentLinkError("Email duplicate is unavailable.")
            document_id = result["duplicate_of"]
        else:
            raise MailDocumentLinkError("Email consumption did not return a document.")
        if type(document_id) is not int or document_id <= 0:
            raise MailDocumentLinkError("Invalid email consumption result.")
        document_ids.add(document_id)

    if not document_ids:
        return

    owner = rule.owner
    if owner is not None and (
        not owner.is_active or not owner.has_perm("documents.change_document")
    ):
        raise MailDocumentLinkError("Insufficient permissions to link email documents.")

    with transaction.atomic():
        field = CustomField.objects.filter(
            pk=field_id,
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        ).first()
        if field is None:
            raise MailDocumentLinkError("The email Document Link field is unavailable.")

        # Lock in a stable order so overlapping email callbacks cannot lose links.
        documents = list(
            Document.objects.select_for_update()
            .filter(pk__in=document_ids)
            .order_by("pk")
            .defer("content"),
        )
        if len(documents) != len(document_ids):
            raise MailDocumentLinkError("An email document is unavailable or in trash.")
        permitted_ids = set(
            permitted_document_ids(owner, perm="change_document").filter(
                pk__in=document_ids,
            ),
        )
        if permitted_ids != document_ids:
            raise MailDocumentLinkError("Insufficient permissions for email links.")
        if len(document_ids) < 2:
            return

        existing = {
            instance.document_id: instance
            for instance in CustomFieldInstance.objects.select_for_update().filter(
                field=field,
                document_id__in=document_ids,
            )
        }
        changed_ids = []
        for document in documents:
            instance = existing.get(document.pk)
            previous = (instance.value_document_ids or []) if instance else []
            targets = sorted(set(previous) | (document_ids - {document.pk}))
            if instance is None:
                CustomFieldInstance.objects.create(
                    document=document,
                    field=field,
                    value_document_ids=targets,
                )
            elif targets != previous:
                instance.value_document_ids = targets
                instance.save(update_fields=["value_document_ids"])
            else:
                continue
            changed_ids.append(document.pk)

        if changed_ids:
            Document.objects.filter(pk__in=changed_ids).update(modified=timezone.now())
        # Refresh even on a retry whose database writes already committed but
        # whose cache/index refresh failed. Repeating the merge itself is safe.
        transaction.on_commit(partial(_refresh_documents, sorted(document_ids)))
