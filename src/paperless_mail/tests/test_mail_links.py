from unittest import mock

import pytest
from django.db import DatabaseError
from django.utils import timezone

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from paperless_mail.document_links import MailDocumentLinkError
from paperless_mail.document_links import _refresh_documents
from paperless_mail.document_links import link_mail_documents
from paperless_mail.mail import apply_mail_action
from paperless_mail.models import ProcessedMail
from paperless_mail.tests.factories import MailRuleFactory
from paperless_testing.factories import DocumentFactory
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

    link_mail_documents([success(third), success(first), success(second)], rule)

    assert linked_ids(first, link_field) == {second.pk, third.pk, old.pk}
    assert linked_ids(second, link_field) == {first.pk, third.pk}
    assert linked_ids(third, link_field) == {first.pk, second.pk}
    assert linked_ids(old, link_field) == {first.pk}
    other_value.refresh_from_db()
    assert other_value.value_text == "Keep this"


def test_shared_duplicate_does_not_merge_other_email_members(rule, link_field):
    first, shared, second = DocumentFactory.create_batch(3, owner=None)
    link_mail_documents([success(first), success(shared)], rule)
    link_mail_documents([success(second), duplicate(shared)], rule)
    link_mail_documents([duplicate(shared), duplicate(second)], rule)

    assert linked_ids(first, link_field) == {shared.pk}
    assert linked_ids(shared, link_field) == {first.pk, second.pk}
    assert linked_ids(second, link_field) == {shared.pk}
    assert CustomFieldInstance.objects.filter(field=link_field).count() == 3


def test_duplicate_occurrences_do_not_self_link(rule, link_field):
    first, second = DocumentFactory.create_batch(2, owner=None)
    link_mail_documents([success(first), duplicate(first), success(second)], rule)
    assert linked_ids(first, link_field) == {second.pk}
    assert linked_ids(second, link_field) == {first.pk}


@pytest.mark.parametrize("results", [[], [{"reason": "split"}], [None]])
def test_disabled_linking_preserves_existing_behavior(results, rule):
    rule.assign_document_link_field = None
    link_mail_documents(results, rule)
    assert not CustomFieldInstance.objects.exists()


def test_single_document_has_no_link(rule):
    document = DocumentFactory(owner=None)
    link_mail_documents([success(document)], rule)
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
        link_mail_documents([success(document), result], rule)
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
        link_mail_documents([success(first), second_result], rule)
    assert not CustomFieldInstance.objects.exists()


def test_ownerless_rule_cannot_link_owned_document(rule):
    first = DocumentFactory(owner=None)
    second = DocumentFactory(owner=UserFactory())
    with pytest.raises(MailDocumentLinkError, match="permissions"):
        link_mail_documents([success(first), duplicate(second)], rule)
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
        link_mail_documents([success(document) for document in documents], rule)
    assert not CustomFieldInstance.objects.exists()


def test_owner_requires_permission_on_every_document(rule):
    owner = UserFactory()
    grant_global(owner, "change_document")
    rule.owner = owner
    first = DocumentFactory(owner=owner)
    second = DocumentFactory(owner=UserFactory())
    with pytest.raises(MailDocumentLinkError, match="permissions"):
        link_mail_documents([success(first), duplicate(second)], rule)
    assert not CustomFieldInstance.objects.exists()


def test_authorized_owner_can_link(rule, link_field):
    owner = UserFactory()
    grant_global(owner, "change_document")
    rule.owner = owner
    first, second = DocumentFactory.create_batch(2, owner=owner)
    link_mail_documents([success(first), success(second)], rule)
    assert linked_ids(first, link_field) == {second.pk}


def test_link_failure_rolls_back_all_changes(rule):
    documents = DocumentFactory.create_batch(2, owner=None)
    original_create = CustomFieldInstance.objects.create
    calls = 0

    def fail_second_create(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise DatabaseError("Cannot write links")
        return original_create(**kwargs)

    manager = CustomFieldInstance.objects
    patcher = mock.patch.object(manager, "create", side_effect=fail_second_create)
    with patcher, pytest.raises(DatabaseError):
        link_mail_documents([success(document) for document in documents], rule)
    assert not CustomFieldInstance.objects.exists()


def test_refresh_after_commit_repeats_on_idempotent_retry(
    rule,
    django_capture_on_commit_callbacks,
):
    documents = DocumentFactory.create_batch(2, owner=None)
    results = [success(document) for document in documents]
    with mock.patch("paperless_mail.document_links._refresh_documents") as refresh:
        for _ in range(2):
            with django_capture_on_commit_callbacks(execute=True):
                link_mail_documents(results, rule)
        assert refresh.call_count == 2
    assert CustomFieldInstance.objects.count() == 2


def test_refresh_only_clears_caches_and_updates_search_index():
    with (
        mock.patch("paperless_mail.document_links.clear_document_caches") as clear,
        mock.patch("paperless_mail.document_links.get_backend") as backend,
        mock.patch("documents.signals.document_updated.send") as updated,
    ):
        _refresh_documents([10, 20])
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
        )
    mailbox.assert_not_called()
    assert ProcessedMail.objects.get(rule=rule, uid="42").status == "FAILED"
