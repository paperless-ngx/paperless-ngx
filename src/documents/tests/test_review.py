import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Event
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import close_old_connections
from django.db import connection
from django.db import transaction
from guardian.shortcuts import remove_perm
from rest_framework.test import APIClient

from documents.models import Document
from documents.models import DocumentReview
from documents.models import DocumentReviewEvent
from documents.review import review_actor_context
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global
from paperless_testing.permissions import grant_object


@pytest.fixture
def review_setup(db, paperless_dirs):
    submitter = UserFactory()
    reviewer = UserFactory()
    document = DocumentFactory(owner=submitter, content="Synthetic review content")
    for user in [submitter, reviewer]:
        grant_global(user, "documents.view_document", "documents.change_document")
    grant_object(reviewer, document, "view_document", "change_document")
    client = APIClient()
    client.force_authenticate(submitter)
    return client, document, submitter, reviewer


def url(document):
    return f"/api/documents/{document.pk}/review/"


def payload(action="submit", revision=0, reviewer=None, **extra):
    data = {
        "action": action,
        "expected_revision": revision,
        "request_id": str(uuid.uuid4()),
    }
    if reviewer is not None:
        data["reviewer"] = reviewer.pk
    return data | extra


def submit(setup):
    client, document, _, reviewer = setup
    response = client.post(url(document), payload(reviewer=reviewer), format="json")
    assert response.status_code == 200, response.data
    return response.data


def approve(setup):
    client, document, _, reviewer = setup
    submit(setup)
    client.force_authenticate(reviewer)
    response = client.post(url(document), payload("approve", 1), format="json")
    assert response.status_code == 200, response.data
    return response.data


def test_default_is_sparse_and_persistent(review_setup):
    client, document, _, _ = review_setup
    expected = {
        "document": document.pk,
        "state": "unreviewed",
        "revision": 0,
        "reviewer": None,
        "submitted_by": None,
        "history": [],
    }
    assert client.get(url(document)).data == expected
    assert not DocumentReview.objects.exists()
    response = submit(review_setup)
    assert response["state"] == "pending"
    assert client.get(url(Document.objects.get(pk=document.pk))).data == response
    assert response["history"][0]["at"].endswith("Z")


def test_retry_keeps_original_response_after_invalidation(review_setup):
    client, document, _, reviewer = review_setup
    submit(review_setup)
    client.force_authenticate(reviewer)
    data = payload("approve", 1)
    original = client.post(url(document), data, format="json").data
    Document.objects.filter(pk=document.pk).update(content="Later content")
    assert client.post(url(document), data, format="json").data == original
    changed = {**data, "expected_revision": 3}
    assert client.post(url(document), changed, format="json").status_code == 409
    current = client.get(url(document)).data
    assert current["revision"] == 3
    assert current["state"] == "unreviewed"
    assert len(current["history"]) == 3


def test_version_access_uses_root_permissions(review_setup):
    client, document, _, reviewer = review_setup
    version = DocumentFactory(
        root_document=document,
        owner=UserFactory(),
        version_index=1,
    )
    assert client.get(url(version)).status_code == 200
    assert (
        client.post(url(version), payload(reviewer=reviewer), format="json").status_code
        == 200
    )
    assert client.get("/api/review_queue/").data["results"][0]["document"] == version.pk
    document.owner = UserFactory()
    document.save(update_fields=["owner"])
    assert client.get(url(version)).status_code == 404
    assert client.get("/api/review_queue/").data["count"] == 0


def test_approval_racing_an_observed_content_change_conflicts(review_setup):
    client, document, _, reviewer = review_setup
    submit(review_setup)
    Document.objects.filter(pk=document.pk).update(
        content="New content awaiting review",
    )
    client.force_authenticate(reviewer)
    response = client.post(url(document), payload("approve", 1), format="json")
    assert response.status_code in {403, 409}
    current = client.get(url(document)).data
    assert current["state"] == "unreviewed" and current["revision"] == 2


def test_version_deletion_invalidates_root_with_actor(review_setup):
    client, document, submitter, _ = review_setup
    version = DocumentFactory(root_document=document, version_index=1)
    before = approve(review_setup)
    with review_actor_context(submitter):
        version.delete()
    current = client.get(url(document)).data
    assert current["revision"] == before["revision"] + 1
    assert current["history"][-1]["actor"] == submitter.pk
    assert current["state"] == "unreviewed"


def test_api_content_update_records_invalidation_actor(review_setup):
    client, document, submitter, _ = review_setup
    approve(review_setup)
    client.force_authenticate(submitter)
    response = client.patch(
        f"/api/documents/{document.pk}/",
        {"content": "Edited through the UI"},
        format="json",
    )
    assert response.status_code == 200, response.data
    current = client.get(url(document)).data
    assert current["state"] == "unreviewed"
    assert current["history"][-1]["actor"] == submitter.pk


def test_version_restore_invalidates_a_new_root_approval(review_setup):
    client, document, submitter, reviewer = review_setup
    version = DocumentFactory(root_document=document, version_index=1)
    approve(review_setup)
    version.delete()
    client.force_authenticate(submitter)
    assert (
        client.post(
            url(document),
            payload(revision=3, reviewer=reviewer),
            format="json",
        ).status_code
        == 200
    )
    client.force_authenticate(reviewer)
    assert (
        client.post(url(document), payload("approve", 4), format="json").status_code
        == 200
    )
    version.restore(strict=False)
    current = client.get(url(document)).data
    assert current["state"] == "unreviewed" and current["revision"] == 6
    assert current["history"][-1]["action"] == "invalidate"


def test_complete_lifecycle_and_history(review_setup):
    client, document, submitter, reviewer = review_setup
    submit(review_setup)
    client.force_authenticate(reviewer)
    response = client.post(
        url(document),
        payload("reject", 1, comment="  <script>bad()</script> ✨  "),
        format="json",
    )
    assert response.status_code == 200
    assert response.data["history"][-1]["comment"] == "<script>bad()</script> ✨"
    client.force_authenticate(submitter)
    assert (
        client.post(
            url(document),
            payload(reviewer=reviewer, revision=2),
            format="json",
        ).status_code
        == 409
    )
    response = client.post(url(document), payload("reopen", 2), format="json")
    assert response.status_code == 200
    assert response.data["state"] == "unreviewed"
    assert response.data["reviewer"] is None
    assert response.data["submitted_by"] is None
    response = client.post(
        url(document),
        payload(reviewer=reviewer, revision=3),
        format="json",
    )
    assert response.status_code == 200
    client.force_authenticate(reviewer)
    response = client.post(url(document), payload("approve", 4), format="json")
    assert response.status_code == 200
    assert response.data["state"] == "approved"
    assert [event["revision"] for event in response.data["history"]] == [1, 2, 3, 4, 5]
    assert [event["action"] for event in response.data["history"]] == [
        "submit",
        "reject",
        "reopen",
        "submit",
        "approve",
    ]
    assert [event["actor"] for event in response.data["history"]] == [
        submitter.pk,
        reviewer.pk,
        submitter.pk,
        submitter.pk,
        reviewer.pk,
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"extra": 1},
        {"actor": 1},
        {"state": "approved"},
        {"history": []},
        {"revision": 10},
        {"action": "invalidate"},
        {"action": True},
        {"action": []},
        {"expected_revision": True},
        {"expected_revision": -1},
        {"expected_revision": "0"},
        {"expected_revision": 0.0},
        {"expected_revision": None},
        {"request_id": "invalid"},
        {"request_id": 1},
        {"request_id": None},
        {"reviewer": True},
        {"reviewer": "1"},
        {"reviewer": 0},
        {"reviewer": -1},
        {"reviewer": 1.5},
        {"reviewer": 2**100},
        {"comment": "not allowed"},
    ],
)
def test_strict_atomic_submit_validation(review_setup, change):
    client, document, _, reviewer = review_setup
    response = client.post(
        url(document),
        payload(reviewer=reviewer) | change,
        format="json",
    )
    assert response.status_code == 400
    assert not DocumentReview.objects.exists()
    assert not DocumentReviewEvent.objects.exists()


@pytest.mark.parametrize(
    "missing",
    ["action", "reviewer", "expected_revision", "request_id"],
)
def test_missing_fields(review_setup, missing):
    client, document, _, reviewer = review_setup
    data = payload(reviewer=reviewer)
    del data[missing]
    assert client.post(url(document), data, format="json").status_code == 400


@pytest.mark.parametrize("comment", [None, 4, False, [], "", "   ", "ü" * 2001])
def test_rejection_comment_validation(review_setup, comment):
    client, document, _, reviewer = review_setup
    before = submit(review_setup)
    client.force_authenticate(reviewer)
    response = client.post(
        url(document),
        payload("reject", 1, comment=comment),
        format="json",
    )
    assert response.status_code == 400
    assert client.get(url(document)).data == before


def test_unicode_limit_and_trim(review_setup):
    client, document, _, reviewer = review_setup
    submit(review_setup)
    client.force_authenticate(reviewer)
    response = client.post(
        url(document),
        payload("reject", 1, comment="  " + "🌍" * 2000 + "  "),
        format="json",
    )
    assert response.status_code == 200
    assert len(response.data["history"][-1]["comment"]) == 2000


@pytest.mark.parametrize("action", ["approve", "reject", "reopen"])
def test_other_actions_reject_reviewer_and_extra_comments(review_setup, action):
    client, document, _, reviewer = review_setup
    submit(review_setup)
    client.force_authenticate(reviewer)
    data = payload(action, 1, reviewer=reviewer)
    if action == "reject":
        data["comment"] = "Reason"
    assert client.post(url(document), data, format="json").status_code == 400
    if action != "reject":
        data.pop("reviewer")
        data["comment"] = "Not allowed"
        assert client.post(url(document), data, format="json").status_code == 400


def test_visibility_precedes_validation_and_global_permissions(review_setup):
    client, document, _, _ = review_setup
    stranger = UserFactory()
    grant_global(stranger, "documents.view_document", "documents.change_document")
    client.force_authenticate(stranger)
    assert client.get(url(document)).status_code == 404
    assert client.post(url(document), {"bad": True}, format="json").status_code == 404
    assert client.get("/api/documents/2147483647/review/").status_code == 404
    client.force_authenticate(None)
    assert client.get(url(document)).status_code in {401, 403}


def test_ownership_never_bypasses_global_permissions(review_setup):
    client, document, submitter, reviewer = review_setup
    submitter.user_permissions.clear()
    client.force_authenticate(User.objects.get(pk=submitter.pk))
    assert client.get(url(document)).status_code == 404
    grant_global(submitter, "documents.view_document")
    client.force_authenticate(User.objects.get(pk=submitter.pk))
    assert client.get(url(document)).status_code == 200
    assert (
        client.post(
            url(document),
            payload(reviewer=reviewer),
            format="json",
        ).status_code
        == 403
    )
    assert client.post(url(document), {"bad": True}, format="json").status_code == 400


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "inactive",
        "private",
        "self",
        "no_global_change",
        "no_global_view",
        "no_object_change",
    ],
)
def test_invalid_assignment_is_generic_and_atomic(review_setup, kind):
    client, document, submitter, reviewer = review_setup
    if kind == "missing":
        reviewer.pk = 2147483647
    elif kind == "inactive":
        reviewer.is_active = False
        reviewer.save()
    elif kind == "private":
        remove_perm("view_document", reviewer, document)
        remove_perm("change_document", reviewer, document)
    elif kind == "self":
        reviewer = submitter
    elif kind.startswith("no_global"):
        codename = "view_document" if kind == "no_global_view" else "change_document"
        reviewer.user_permissions.remove(Permission.objects.get(codename=codename))
    else:
        remove_perm("change_document", reviewer, document)
    response = client.post(url(document), payload(reviewer=reviewer), format="json")
    assert response.status_code == 400
    assert str(response.data["reviewer"]) == "Invalid reviewer."
    assert not DocumentReview.objects.exists()


def test_assignment_and_self_review_not_bypassed_by_superuser(review_setup):
    client, document, submitter, _ = review_setup
    submit(review_setup)
    admin = UserFactory(superuser=True)
    client.force_authenticate(admin)
    assert (
        client.post(url(document), payload("approve", 1), format="json").status_code
        == 403
    )
    client.force_authenticate(submitter)
    assert (
        client.post(url(document), payload("approve", 1), format="json").status_code
        == 403
    )
    DocumentReview.objects.filter(document=document).update(reviewer=submitter)
    submitter.is_superuser = True
    submitter.save()
    assert (
        client.post(url(document), payload("approve", 1), format="json").status_code
        == 403
    )


@pytest.mark.parametrize(
    "revoke",
    ["global_view", "global_change", "object_view", "object_change", "inactive"],
)
def test_reviewer_access_rechecked_when_deciding(review_setup, revoke):
    client, document, _, reviewer = review_setup
    before = submit(review_setup)
    if revoke == "inactive":
        reviewer.is_active = False
        reviewer.save()
    elif revoke.startswith("global"):
        reviewer.user_permissions.remove(
            Permission.objects.get(codename=f"{revoke.split('_')[1]}_document"),
        )
    else:
        remove_perm(f"{revoke.split('_')[1]}_document", reviewer, document)
    client.force_authenticate(User.objects.get(pk=reviewer.pk))
    response = client.post(url(document), payload("approve", 1), format="json")
    assert response.status_code == (
        404 if revoke in {"global_view", "object_view", "inactive"} else 403
    )
    assert DocumentReview.objects.get(document=document).revision == before["revision"]


def test_group_global_and_object_permissions(review_setup):
    client, document, _, reviewer = review_setup
    reviewer.user_permissions.clear()
    remove_perm("view_document", reviewer, document)
    remove_perm("change_document", reviewer, document)
    group = Group.objects.create(name="Synthetic reviewers")
    group.permissions.add(
        *Permission.objects.filter(
            content_type__app_label="documents",
            codename__in=["view_document", "change_document"],
        ),
    )
    reviewer.groups.add(group)
    grant_object(group, document, "view_document", "change_document")
    submit(review_setup)
    client.force_authenticate(User.objects.get(pk=reviewer.pk))
    assert (
        client.post(url(document), payload("approve", 1), format="json").status_code
        == 200
    )


def test_idempotency_original_response_scopes_and_revoked_access(review_setup):
    client, document, submitter, reviewer = review_setup
    data = payload(reviewer=reviewer)
    response = client.post(url(document), data, format="json")
    assert response.status_code == 200
    assert client.post(url(document), data, format="json").data == response.data
    assert (
        client.post(
            url(document),
            data | {"expected_revision": 1},
            format="json",
        ).status_code
        == 409
    )
    second = DocumentFactory(owner=submitter)
    grant_object(reviewer, second, "view_document", "change_document")
    assert client.post(url(second), data, format="json").status_code == 200
    client.force_authenticate(reviewer)
    decision = payload("approve", 1, request_id=data["request_id"])
    approved = client.post(url(document), decision, format="json")
    assert approved.status_code == 200
    assert client.post(url(document), decision, format="json").data == approved.data
    client.force_authenticate(submitter)
    assert client.post(url(document), data, format="json").data == response.data
    submitter.user_permissions.remove(
        Permission.objects.get(codename="change_document"),
    )
    client.force_authenticate(User.objects.get(pk=submitter.pk))
    assert client.post(url(document), data, format="json").status_code == 403
    assert DocumentReviewEvent.objects.filter(review__document=document).count() == 2


def test_revision_and_transition_conflicts_are_atomic(review_setup):
    client, document, _, reviewer = review_setup
    assert (
        client.post(
            url(document),
            payload(reviewer=reviewer, revision=1),
            format="json",
        ).status_code
        == 409
    )
    assert (
        client.post(url(document), payload("reopen"), format="json").status_code == 409
    )
    before = submit(review_setup)
    assert (
        client.post(url(document), payload("reopen", 1), format="json").status_code
        == 409
    )
    assert client.get(url(document)).data == before
    client.force_authenticate(reviewer)
    assert (
        client.post(url(document), payload("approve", 0), format="json").status_code
        == 409
    )
    assert (
        client.post(url(document), payload("approve", 1), format="json").status_code
        == 200
    )
    assert (
        client.post(url(document), payload("approve", 2), format="json").status_code
        == 409
    )


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_unsupported_mutations(review_setup, method):
    client, document, _, _ = review_setup
    assert getattr(client, method)(url(document), {}, format="json").status_code == 405


def test_queue_permissions_count_order_filters_and_pagination(review_setup):
    client, document, submitter, reviewer = review_setup
    submit(review_setup)
    visible = DocumentFactory(owner=submitter)
    hidden = DocumentFactory(owner=reviewer)
    DocumentReview.objects.create(
        document=visible,
        state="pending",
        reviewer=reviewer,
        revision=1,
    )
    DocumentReview.objects.create(
        document=hidden,
        state="pending",
        reviewer=reviewer,
        revision=1,
    )
    DocumentFactory(owner=submitter)
    response = client.get(
        f"/api/review_queue/?state=pending&reviewer={reviewer.pk}&page_size=1",
    )
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["results"][0]["document"] == min(document.pk, visible.pk)
    second = client.get("/api/review_queue/?page=2&page_size=1").data
    assert second["results"][0]["document"] == max(document.pk, visible.pk)
    assert client.get("/api/review_queue/?page=3&page_size=1").data["results"] == []
    assert client.get("/api/review_queue/?state=approved").data["count"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "state=bad",
        "reviewer=0",
        "reviewer=-1",
        "reviewer=true",
        "page=0",
        "page=1.0",
        "page=x",
        "page_size=0",
        "page_size=101",
        "page_size=-1",
        "state=",
        "unexpected=1",
        "page=1&page=2",
    ],
)
def test_invalid_queue_filters(review_setup, query):
    client, _, _, _ = review_setup
    assert client.get(f"/api/review_queue/?{query}").status_code == 400


@pytest.mark.parametrize("state", ["pending", "approved"])
@pytest.mark.parametrize(
    "writer",
    ["save", "update", "bulk_update", "version", "checksum", "archive_checksum"],
)
def test_content_and_versions_invalidate_exactly_once(review_setup, state, writer):
    client, document, submitter, _ = review_setup
    if state == "approved":
        approve(review_setup)
    else:
        submit(review_setup)
    before = client.get(url(document)).data
    with review_actor_context(submitter):
        if writer == "save":
            document.content = "Changed content"
            document.save(update_fields=["content"])
        elif writer == "update":
            Document.objects.filter(pk=document.pk).update(content="Changed content")
        elif writer == "bulk_update":
            document.content = "Changed content"
            Document.objects.bulk_update([document], ["content"])
        elif writer == "version":
            DocumentFactory(root_document=document, version_index=1)
        else:
            Document.objects.filter(pk=document.pk).update(
                **{writer: "changed-checksum"},
            )
    after = client.get(url(document)).data
    assert after["state"] == "unreviewed"
    assert after["revision"] == before["revision"] + 1
    assert after["reviewer"] is None and after["submitted_by"] is None
    event = after["history"][-1]
    assert event["action"] == "invalidate" and event["actor"] == submitter.pk
    assert event["request_id"] is None and event["comment"] == ""


def test_metadata_and_noop_content_do_not_invalidate(review_setup):
    client, document, _, _ = review_setup
    before = approve(review_setup)
    document.title = "Edited title"
    document.save()
    document.save(update_fields=["content"])
    Document.objects.filter(pk=document.pk).update(content=document.content)
    Document.objects.bulk_update([document], ["content"])
    assert client.get(url(document)).data == before


def test_background_invalidation_and_rollback(review_setup):
    client, document, _, _ = review_setup
    before = approve(review_setup)
    with pytest.raises(RuntimeError), transaction.atomic():
        Document.objects.filter(pk=document.pk).update(content="Rolled back")
        raise RuntimeError
    assert client.get(url(document)).data == before
    Document.objects.filter(pk=document.pk).update(content="Background content")
    assert client.get(url(document)).data["history"][-1]["actor"] is None


def test_latest_version_edit_and_merge_invalidate_root(review_setup):
    from documents.bulk_edit import merge_as_versions

    client, document, submitter, _ = review_setup
    version = DocumentFactory(root_document=document, version_index=1)
    before = approve(review_setup)
    version.content = "Edited version"
    version.save(update_fields=["content"])
    assert client.get(url(document)).data["revision"] == before["revision"] + 1
    client.force_authenticate(submitter)
    client.post(
        url(document),
        payload(reviewer=review_setup[3], revision=3),
        format="json",
    )
    source = DocumentFactory(owner=submitter)
    with patch("documents.tasks.bulk_update_documents.delay"):
        merge_as_versions(
            [document.pk, source.pk],
            root_document_id=document.pk,
            user=submitter,
        )
    assert client.get(url(document)).data["state"] == "unreviewed"
    assert client.get(url(document)).data["history"][-1]["actor"] == submitter.pk


def test_trash_restore_and_permanent_deletion(review_setup):
    client, document, _, _ = review_setup
    DocumentFactory(root_document=document, version_index=1)
    before = approve(review_setup)
    document.delete()
    assert client.get(url(document)).data == before
    assert (
        client.post(url(document), payload("reopen", 2), format="json").status_code
        == 409
    )
    assert client.get("/api/review_queue/").data["count"] == 0
    document.restore(strict=False)
    assert client.get(url(document)).data == before
    document.hard_delete()
    assert not DocumentReview.global_objects.exists()
    assert not DocumentReviewEvent.global_objects.exists()


def test_reviewer_options_only_eligible_and_authorized(review_setup):
    client, document, _, reviewer = review_setup
    UserFactory()
    response = client.get(f"/api/documents/{document.pk}/reviewers/")
    assert response.status_code == 200
    assert response.data == {
        "allowed_actions": ["submit"],
        "results": [{"id": reviewer.pk, "username": reviewer.username}],
    }
    submit(review_setup)
    assert (
        client.get(f"/api/documents/{document.pk}/reviewers/").data["allowed_actions"]
        == []
    )
    client.force_authenticate(reviewer)
    assert client.get(f"/api/documents/{document.pk}/reviewers/").data[
        "allowed_actions"
    ] == ["approve", "reject"]


@pytest.fixture
def review_transactional_db(django_db_setup, django_db_blocker):
    # Threaded requests need committed rows. Restore migration seed data and
    # sequences too, so these tests don't disturb later TestCase regressions.
    with django_db_blocker.unblock():
        initial = connection.creation.serialize_db_to_string()
        try:
            yield
        finally:
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                reset_sequences=True,
                inhibit_post_migrate=True,
            )
            connection.creation.deserialize_db_from_string(initial)


@pytest.mark.parametrize("identical", [True, False])
def test_concurrent_retries_and_decisions(
    review_transactional_db,
    paperless_dirs,
    identical,
):
    submitter = UserFactory(superuser=True)
    reviewer = UserFactory(superuser=True)
    document = DocumentFactory(owner=submitter)
    client = APIClient()
    client.force_authenticate(submitter)
    assert (
        client.post(
            url(document),
            payload(reviewer=reviewer),
            format="json",
        ).status_code
        == 200
    )
    data = payload("approve", 1)
    barrier = Barrier(2)

    def decide(index):
        close_old_connections()
        try:
            worker = APIClient()
            worker.force_authenticate(User.objects.get(pk=reviewer.pk))
            barrier.wait(timeout=10)
            body = (
                data
                if identical or index == 0
                else payload("reject", 1, comment="Concurrent rejection")
            )
            response = worker.post(url(document), body, format="json")
            return response.status_code, response.data
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(decide, [0, 1]))
    assert sorted(code for code, _ in responses) == (
        [200, 200] if identical else [200, 409]
    )
    if identical:
        assert responses[0][1] == responses[1][1]
    assert DocumentReviewEvent.objects.count() == 2
    assert DocumentReview.objects.get(document=document).revision == 2


def test_content_change_and_approval_share_a_lock(
    review_transactional_db,
    paperless_dirs,
):
    from documents.review_views import visible_document

    submitter = UserFactory(superuser=True)
    reviewer = UserFactory(superuser=True)
    document = DocumentFactory(owner=submitter)
    client = APIClient()
    client.force_authenticate(submitter)
    assert (
        client.post(
            url(document),
            payload(reviewer=reviewer),
            format="json",
        ).status_code
        == 200
    )
    written, attempted, release = Event(), Event(), Event()

    def write_content():
        close_old_connections()
        try:
            with transaction.atomic():
                Document.objects.filter(pk=document.pk).update(
                    content="Concurrent content",
                )
                written.set()
                assert release.wait(timeout=10)
        finally:
            close_old_connections()

    def observe_attempt(*args, **kwargs):
        attempted.set()
        return visible_document(*args, **kwargs)

    def decide():
        close_old_connections()
        try:
            worker = APIClient()
            worker.force_authenticate(User.objects.get(pk=reviewer.pk))
            return worker.post(url(document), payload("approve", 1), format="json")
        finally:
            close_old_connections()

    with (
        patch("documents.review_views.visible_document", side_effect=observe_attempt),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        content = executor.submit(write_content)
        assert written.wait(timeout=10)
        decision = executor.submit(decide)
        try:
            assert attempted.wait(timeout=10)
        finally:
            release.set()
        content.result(timeout=10)
        assert decision.result(timeout=10).status_code in {403, 409}
    document.refresh_from_db()
    review = DocumentReview.objects.get(document=document)
    assert document.content == "Concurrent content"
    assert review.state == "unreviewed" and review.revision == 2
    assert list(review.events.values_list("action", flat=True)) == [
        "submit",
        "invalidate",
    ]
