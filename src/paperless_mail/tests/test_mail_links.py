import hashlib
from pathlib import Path
from unittest import mock

import pytest
from django.db import DatabaseError
from django.utils import timezone

from documents.file_handling import generate_filename
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from paperless_mail.document_links import MailDocumentLinkError
from paperless_mail.document_links import _refresh_documents
from paperless_mail.document_links import link_mail_documents
from paperless_mail.mail import apply_mail_action
from paperless_mail.mail import queue_consumption_tasks
from paperless_mail.models import ProcessedMail
from paperless_mail.tests.factories import MailRuleFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import StoragePathFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global

pytestmark = pytest.mark.django_db


@pytest.fixture
def link_field():
    return CustomField.objects.create(
        name="Email documents",
        data_type=CustomField.FieldDataType.DOCUMENTLINK,
    )


@pytest.fixture
def rule(link_field):
    return MailRuleFactory(owner=None, assign_document_link_field=link_field)


def link_batch(results, rule):
    link_mail_documents(
        results,
        rule,
        field_id=rule.assign_document_link_field_id,
    )


def linked_ids(document, field):
    return set(
        CustomFieldInstance.objects.get(
            document=document,
            field=field,
        ).value_document_ids,
    )


def success(document):
    return {"document_id": document.pk}


def duplicate(document):
    return {"duplicate_of": document.pk, "duplicate_in_trash": False}


def test_same_email_links_are_symmetric_and_preserve_other_metadata(rule, link_field):
    first, second, third, old = DocumentFactory.create_batch(4, owner=None)
    other_field = CustomField.objects.create(name="Unrelated", data_type="string")
    other_value = CustomFieldInstance.objects.create(
        document=first,
        field=other_field,
        value_text="Keep this",
    )
    CustomFieldInstance.objects.create(
        document=first,
        field=link_field,
        value_document_ids=[old.pk],
    )
    CustomFieldInstance.objects.create(
        document=old,
        field=link_field,
        value_document_ids=[first.pk],
    )

    link_batch([success(third), success(first), success(second)], rule)

    assert linked_ids(first, link_field) == {second.pk, third.pk, old.pk}
    assert linked_ids(second, link_field) == {first.pk, third.pk}
    assert linked_ids(third, link_field) == {first.pk, second.pk}
    assert linked_ids(old, link_field) == {first.pk}
    other_value.refresh_from_db()
    assert other_value.value_text == "Keep this"


def test_shared_duplicate_does_not_merge_other_email_members(rule, link_field):
    first, shared, second = DocumentFactory.create_batch(3, owner=None)
    link_batch([success(first), success(shared)], rule)
    link_batch([success(second), duplicate(shared)], rule)
    link_batch([duplicate(shared), duplicate(second)], rule)

    assert linked_ids(first, link_field) == {shared.pk}
    assert linked_ids(shared, link_field) == {first.pk, second.pk}
    assert linked_ids(second, link_field) == {shared.pk}
    assert CustomFieldInstance.objects.filter(field=link_field).count() == 3


def test_duplicate_occurrences_do_not_self_link(rule, link_field):
    first, second = DocumentFactory.create_batch(2, owner=None)
    link_batch([success(first), duplicate(first), success(second)], rule)
    assert linked_ids(first, link_field) == {second.pk}
    assert linked_ids(second, link_field) == {first.pk}


@pytest.mark.parametrize("results", [[], [{"reason": "split"}], [None]])
def test_disabled_linking_preserves_existing_behavior(results, rule):
    rule.assign_document_link_field = None
    link_batch(results, rule)
    assert not CustomFieldInstance.objects.exists()


def test_single_document_has_no_link(rule):
    document = DocumentFactory(owner=None)
    link_batch([success(document)], rule)
    assert not CustomFieldInstance.objects.exists()


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"reason": "barcode split dispatched"},
        {},
        {"document_id": True},
        {"document_id": "1"},
        {"document_id": -1},
        {"document_id": 1, "duplicate_of": 1},
        {"duplicate_of": 1, "duplicate_in_trash": True},
        {"duplicate_of": 1},
    ],
)
def test_incomplete_results_reject_the_whole_batch(result, rule):
    document = DocumentFactory(owner=None)
    with pytest.raises(MailDocumentLinkError):
        link_batch([success(document), result], rule)
    assert not CustomFieldInstance.objects.exists()


@pytest.mark.parametrize("trashed", [True, False])
def test_unavailable_document_rejects_the_whole_batch(trashed, rule):
    first, second = DocumentFactory.create_batch(2, owner=None)
    if trashed:
        Document.objects.filter(pk=second.pk).update(deleted_at=timezone.now())
        second_result = success(second)
    else:
        second_result = {"document_id": second.pk + 100000}
    with pytest.raises(MailDocumentLinkError, match="unavailable"):
        link_batch([success(first), second_result], rule)
    assert not CustomFieldInstance.objects.exists()


def test_ownerless_rule_cannot_link_owned_document(rule):
    first = DocumentFactory(owner=None)
    second = DocumentFactory(owner=UserFactory())
    with pytest.raises(MailDocumentLinkError, match="permissions"):
        link_batch([success(first), duplicate(second)], rule)
    assert not CustomFieldInstance.objects.exists()


@pytest.mark.parametrize("active,global_permission", [(False, True), (True, False)])
def test_owner_requires_active_account_and_global_permission(
    active,
    global_permission,
    rule,
):
    owner = UserFactory(is_active=active)
    if global_permission:
        grant_global(owner, "change_document")
    rule.owner = owner
    documents = DocumentFactory.create_batch(2, owner=owner)
    with pytest.raises(MailDocumentLinkError, match="permissions"):
        link_batch([success(document) for document in documents], rule)
    assert not CustomFieldInstance.objects.exists()


def test_owner_requires_permission_on_every_document(rule):
    owner = UserFactory()
    grant_global(owner, "change_document")
    rule.owner = owner
    first = DocumentFactory(owner=owner)
    second = DocumentFactory(owner=UserFactory())
    with pytest.raises(MailDocumentLinkError, match="permissions"):
        link_batch([success(first), duplicate(second)], rule)
    assert not CustomFieldInstance.objects.exists()


def test_authorized_owner_can_link(rule, link_field):
    owner = UserFactory()
    grant_global(owner, "change_document")
    rule.owner = owner
    first, second = DocumentFactory.create_batch(2, owner=owner)
    link_batch([success(first), success(second)], rule)
    assert linked_ids(first, link_field) == {second.pk}


@pytest.fixture
def stored_documents(paperless_dirs, link_field):
    path = StoragePathFactory(
        path=(
            "{% if custom_fields|get_cf_value('Email documents') %}linked"
            "{% else %}unlinked{% endif %}/{{ title }}"
        ),
    )
    options = {"owner": None, "storage_path": path, "mime_type": "application/pdf"}
    documents = [
        DocumentFactory(title=title, **options) for title in ["first", "second"]
    ]
    # One update and one insertion exercise two database writes in the batch.
    CustomFieldInstance.objects.create(
        document=documents[0],
        field=link_field,
        value_document_ids=[],
    )
    for document in documents:
        payload = f"Original content of {document.title}".encode()
        filename = str(generate_filename(document))
        Document.objects.filter(pk=document.pk).update(
            filename=filename,
            checksum=hashlib.sha256(payload).hexdigest(),
        )
        document.refresh_from_db()
        document.source_path.parent.mkdir(parents=True, exist_ok=True)
        document.source_path.write_bytes(payload)
    return documents


@pytest.mark.django_db(transaction=True)
def test_link_write_failure_does_not_move_originals(rule, link_field, stored_documents):
    before = {
        document.pk: (document.source_path, document.source_path.read_bytes())
        for document in stored_documents
    }
    with (
        mock.patch.object(
            CustomFieldInstance.objects,
            "bulk_update",
            side_effect=DatabaseError("Second write failed"),
        ),
        mock.patch("paperless_mail.document_links._refresh_documents") as refresh,
        pytest.raises(DatabaseError),
    ):
        link_batch([success(document) for document in stored_documents], rule)
    refresh.assert_not_called()
    assert CustomFieldInstance.objects.filter(field=link_field).count() == 1
    assert linked_ids(stored_documents[0], link_field) == set()
    for document in stored_documents:
        document.refresh_from_db()
        old_path, payload = before[document.pk]
        assert document.source_path == old_path
        assert old_path.read_bytes() == payload


@pytest.mark.django_db(transaction=True)
def test_successful_commit_updates_custom_field_paths(rule, stored_documents):
    before = {
        document.pk: (document.source_path, document.source_path.read_bytes())
        for document in stored_documents
    }
    with mock.patch("paperless_mail.document_links.get_backend"):
        link_batch([success(document) for document in stored_documents], rule)
    for document in stored_documents:
        document.refresh_from_db()
        old_path, payload = before[document.pk]
        assert Path(document.filename) == Path("linked") / f"{document.title}.pdf"
        assert document.source_path != old_path
        assert not old_path.exists()
        assert document.source_path.read_bytes() == payload


def test_refresh_after_commit_repeats_on_idempotent_retry(
    rule,
    django_capture_on_commit_callbacks,
):
    documents = DocumentFactory.create_batch(2, owner=None)
    results = [success(document) for document in documents]
    with mock.patch("paperless_mail.document_links._refresh_documents") as refresh:
        for _ in range(2):
            with django_capture_on_commit_callbacks(execute=True):
                link_batch(results, rule)
        assert refresh.call_count == 2
    assert CustomFieldInstance.objects.count() == 2


def test_refresh_only_clears_caches_and_updates_search_index():
    with (
        mock.patch("paperless_mail.document_links.clear_document_caches") as clear,
        mock.patch("paperless_mail.document_links.get_backend") as backend,
        mock.patch("documents.signals.document_updated.send") as updated,
    ):
        _refresh_documents([10, 20], 1)
    assert clear.call_args_list == [mock.call(10), mock.call(20)]
    batch = backend.return_value.batch_update.return_value.__enter__.return_value
    batch.add_or_update_ids.assert_called_once_with([10, 20])
    updated.assert_not_called()


def test_link_failure_does_not_perform_mail_action(rule):
    with (
        mock.patch("paperless_mail.mail.get_mailbox") as mailbox,
        pytest.raises(MailDocumentLinkError),
    ):
        apply_mail_action(
            result=[None],
            rule_id=rule.pk,
            message_uid="42",
            message_subject="Private source",
            message_date=timezone.now(),
            document_link_field_id=rule.assign_document_link_field_id,
        )
    mailbox.assert_not_called()
    assert ProcessedMail.objects.get(rule=rule, uid="42").status == "FAILED"


@pytest.mark.django_db(transaction=True)
def test_committed_links_retry_after_refresh_failure_without_deleting_mail(rule):
    first, second = DocumentFactory.create_batch(2, owner=None)
    callback_args = {
        "rule_id": rule.pk,
        "message_uid": "retry-42",
        "message_subject": "Retry source",
        "message_date": timezone.now(),
        "document_link_field_id": rule.assign_document_link_field_id,
    }
    with (
        mock.patch("paperless_mail.document_links._refresh_documents") as refresh,
        mock.patch("paperless_mail.mail.get_mailbox") as mailbox,
        mock.patch("paperless_mail.mail.mailbox_login"),
        mock.patch("paperless_mail.mail.get_rule_action") as action,
    ):
        refresh.side_effect = [OSError("Index unavailable"), None]
        with pytest.raises(OSError):
            apply_mail_action([success(first), success(second)], **callback_args)
        mailbox.assert_not_called()
        failed = ProcessedMail.objects.get(rule=rule, uid="retry-42")
        assert failed.status == "FAILED"
        assert CustomFieldInstance.objects.count() == 2

        # As documented, the user clears the failed processing log before refetch.
        failed.delete()
        apply_mail_action([duplicate(first), duplicate(second)], **callback_args)
        assert refresh.call_count == 2
        mailbox.assert_called_once()
        action.return_value.post_consume.assert_called_once()
    assert ProcessedMail.objects.get(rule=rule, uid="retry-42").status == "SUCCESS"
    assert CustomFieldInstance.objects.count() == 2


def test_bulk_link_writes_remain_audited(rule, link_field, settings):
    from auditlog.models import LogEntry

    settings.AUDIT_LOG_ENABLED = True
    first, second = DocumentFactory.create_batch(2, owner=None)
    link_batch([success(first), success(second)], rule)
    instances = CustomFieldInstance.objects.filter(field=link_field)
    entries = LogEntry.objects.filter(
        content_type__model="customfieldinstance",
        object_pk__in=[str(instance.pk) for instance in instances],
    )
    assert entries.count() == 2
    assert all(entry.action == LogEntry.Action.CREATE for entry in entries)
    assert all("value_document_ids" in entry.changes for entry in entries)
    link_batch([duplicate(first), duplicate(second)], rule)
    assert entries.count() == 2


@pytest.mark.parametrize("enabled", [False, True])
def test_queue_snapshots_the_selected_link_field(rule, enabled):
    if not enabled:
        rule.assign_document_link_field = None
    message = mock.Mock(uid="42", subject="Example", date=timezone.now())
    with mock.patch("paperless_mail.mail.chord") as queued:
        queue_consumption_tasks(
            consume_tasks=[],
            rule=rule,
            message=message,
            uid_validity="1",
        )
    callback = queued.call_args.kwargs["body"]
    assert (
        callback.kwargs["document_link_field_id"] == rule.assign_document_link_field_id
    )


def test_deleted_snapshotted_field_prevents_mail_action(rule, link_field):
    document = DocumentFactory(owner=None)
    queued_field_id = link_field.pk
    link_field.delete()
    rule.refresh_from_db()
    assert rule.assign_document_link_field_id is None
    with (
        mock.patch("paperless_mail.mail.get_mailbox") as mailbox,
        pytest.raises(MailDocumentLinkError, match="field is unavailable"),
    ):
        apply_mail_action(
            [success(document)],
            rule_id=rule.pk,
            message_uid="deleted-field",
            message_subject="Example",
            message_date=timezone.now(),
            document_link_field_id=queued_field_id,
        )
    mailbox.assert_not_called()
    assert ProcessedMail.objects.get(rule=rule).status == "FAILED"


def test_callback_without_link_snapshot_keeps_legacy_behavior(rule):
    with (
        mock.patch("paperless_mail.mail.get_mailbox") as mailbox,
        mock.patch("paperless_mail.mail.mailbox_login"),
        mock.patch("paperless_mail.mail.get_rule_action"),
    ):
        apply_mail_action(
            [None],
            rule_id=rule.pk,
            message_uid="old-queue",
            message_subject="Example",
            message_date=timezone.now(),
        )
    mailbox.assert_called_once()
    assert not CustomFieldInstance.objects.exists()
