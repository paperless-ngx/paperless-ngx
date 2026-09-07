import copy
import json
from contextlib import nullcontext
from typing import Any
from unittest.mock import patch

import httpx
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings

from documents import tasks
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.models import WorkflowAction
from documents.tests.utils import DirectoriesMixin
from documents.workflows.ai import apply_ai_suggestions_to_document
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.exceptions import StaleSuggestions
from paperless_ai.exceptions import SuggestionProviderError
from paperless_ai.exceptions import SuggestionProviderUnavailable
from paperless_ai.suggestion_provider import applied_event
from paperless_ai.suggestion_provider import document_snapshot
from paperless_ai.suggestion_provider import post_provider

PROPOSAL = {
    "title": "Synthetic proposal",
    "tags": {"existing_ids": [], "new_names": []},
    "correspondents": {"existing_ids": [], "new_names": []},
    "document_types": {"existing_ids": [], "new_names": []},
    "storage_paths": {"existing_ids": [], "new_names": []},
    "dates": ["2026-01-02"],
}


def response_for(request) -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "request_id": request["request_id"],
        "context_id": request["context_id"],
        "suggestions": copy.deepcopy(PROPOSAL),
    }


@override_settings(
    AI_ENABLED=True,
    AI_SUGGESTIONS_ENDPOINT="https://provider.example.invalid/suggestions",
    NUMBER_OF_SUGGESTED_DATES=3,
)
class TestSuggestionProvider(DirectoriesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username="synthetic-reviewer")
        self.document = Document.objects.create(
            title="Saved title",
            content="Synthetic invoice issued 2026-01-02",
            checksum="synthetic-original",
            owner=self.user,
            mime_type="application/pdf",
            original_filename="fixture.pdf",
        )
        self.tag = Tag.objects.create(
            name="Invoice",
            match="invoice",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )
        self.document.tags.add(self.tag)
        self.post = self.enterContext(
            patch(
                "paperless_ai.suggestion_provider.post_provider",
                side_effect=response_for,
            ),
        )
        self.enterContext(
            patch(
                "paperless_ai.suggestion_provider.load_classifier",
                return_value=None,
            ),
        )
        self.llm = self.enterContext(patch("paperless_ai.ai_classifier.AIClient"))
        self.client.force_login(self.user)

    def classify(self):
        return get_ai_document_classification(self.document, self.user, "de")

    def test_explicit_context_and_classic_candidates_without_writes(self):
        field = CustomField.objects.create(
            name="Synthetic amount",
            data_type="monetary",
        )
        CustomFieldInstance.objects.create(
            document=self.document,
            field=field,
            value_monetary="EUR10.00",
        )
        before = document_snapshot(self.document)
        self.assertEqual(self.classify(), PROPOSAL)
        request = self.post.call_args.args[0]
        self.assertEqual(request["document"], before)
        self.assertEqual(request["requester_id"], self.user.pk)
        self.assertEqual(request["output_language"], "de")
        self.assertEqual(request["classic_suggestions"]["tags"], [self.tag.pk])
        self.assertEqual(request["document"]["custom_fields"][0]["value"], "EUR10.00")
        self.assertEqual(
            request["taxonomy"]["tags"],
            [{"id": self.tag.pk, "name": "Invoice"}],
        )
        self.assertEqual(document_snapshot(self.document), before)
        self.llm.assert_not_called()

    def test_effective_content_carries_its_actual_version_identity(self):
        version = Document.objects.create(
            root_document=self.document,
            version_index=2,
            content="Synthetic revised text",
            checksum="synthetic-version",
            original_filename="revision.pdf",
        )
        self.classify()
        snapshot = self.post.call_args.args[0]["document"]
        self.assertEqual(snapshot["id"], self.document.pk)
        self.assertEqual(snapshot["content_version"]["id"], version.pk)
        self.assertEqual(snapshot["content_version"]["checksum"], "synthetic-version")
        self.assertEqual(snapshot["content"], "Synthetic revised text")
        self.assertEqual(snapshot["title"], "Saved title")

    def test_external_provider_bypasses_native_cache(self):
        with (
            patch("documents.views.get_llm_suggestion_cache") as cache_get,
            patch("documents.views.set_llm_suggestions_cache") as cache_set,
        ):
            for _ in range(2):
                response = self.client.get(
                    f"/api/documents/{self.document.pk}/ai_suggestions/",
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["title"], PROPOSAL["title"])
        self.assertEqual(self.post.call_count, 2)
        first, second = [call.args[0] for call in self.post.call_args_list]
        self.assertEqual(first["context_id"], second["context_id"])
        self.assertNotEqual(first["request_id"], second["request_id"])
        cache_get.assert_not_called()
        cache_set.assert_not_called()

    def test_metadata_and_ocr_changes_are_rejected_even_without_checksum_change(self):
        for change in ({"title": "Human correction"}, {"content": "Corrected text"}):
            with self.subTest(change=change):

                def changed(request):
                    Document.objects.filter(pk=self.document.pk).update(**change)
                    return response_for(request)

                self.post.side_effect = changed
                with self.assertRaises(StaleSuggestions):
                    self.classify()

    def test_new_version_during_request_is_rejected(self):
        def changed(request):
            Document.objects.create(
                root_document=self.document,
                version_index=1,
                content="New version",
            )
            return response_for(request)

        self.post.side_effect = changed
        with self.assertRaises(StaleSuggestions):
            self.classify()

    def test_tag_changes_are_rejected(self):
        def changed(request):
            self.document.tags.clear()
            return response_for(request)

        self.post.side_effect = changed
        with self.assertRaises(StaleSuggestions):
            self.classify()

    def test_custom_field_changes_are_rejected(self):
        field = CustomField.objects.create(name="Synthetic note", data_type="string")

        def changed(request):
            CustomFieldInstance.objects.create(
                document=self.document,
                field=field,
                value_text="Changed",
            )
            return response_for(request)

        self.post.side_effect = changed
        with self.assertRaises(StaleSuggestions):
            self.classify()

    @override_settings(AI_SUGGESTIONS_ENDPOINT="")
    def test_disabled_provider_retains_upstream_classifier(self):
        self.llm.return_value.run_llm_query.return_value = copy.deepcopy(PROPOSAL)
        self.assertEqual(
            get_ai_document_classification(self.document, self.user),
            PROPOSAL,
        )
        self.post.assert_not_called()
        self.llm.assert_called_once()

    def test_response_must_echo_exact_request_and_context(self):
        for key in ("request_id", "context_id"):
            with self.subTest(key=key):

                def wrong(request):
                    return {**response_for(request), key: "another-request"}

                self.post.side_effect = wrong
                with self.assertRaises(SuggestionProviderError):
                    self.classify()

    def test_invisible_taxonomy_is_neither_sent_nor_accepted(self):
        limited = User.objects.create_user(username="limited")
        hidden = Tag.objects.create(name="Private synthetic tag", owner=self.user)
        self.document.owner = limited
        self.document.save()

        def wrong(request):
            self.assertNotIn(
                hidden.pk,
                [item["id"] for item in request["taxonomy"]["tags"]],
            )
            response = response_for(request)
            response["suggestions"]["tags"]["existing_ids"] = [hidden.pk]
            return response

        self.post.side_effect = wrong
        with self.assertRaises(SuggestionProviderError):
            get_ai_document_classification(self.document, limited)

    def test_invalid_response_fails_without_fallback(self):
        for field, value in (
            ("title", "x" * 129),
            ("dates", ["2026-02-30"]),
            ("tags", {"existing_ids": [True]}),
            ("extra", "unexpected"),
        ):
            with self.subTest(field=field):

                def invalid(request):
                    response = response_for(request)
                    response["suggestions"][field] = value
                    return response

                self.post.side_effect = invalid
                with self.assertRaises(SuggestionProviderError):
                    self.classify()
        self.llm.assert_not_called()

    def test_view_reports_provider_errors_without_changing_document(self):
        for error, code in (
            (StaleSuggestions, 409),
            (SuggestionProviderUnavailable, 503),
            (SuggestionProviderError, 502),
        ):
            with self.subTest(error=error):
                self.post.side_effect = error("Synthetic provider error")
                response = self.client.get(
                    f"/api/documents/{self.document.pk}/ai_suggestions/",
                )
                self.assertEqual(response.status_code, code)
                self.document.refresh_from_db()
                self.assertEqual(self.document.title, "Saved title")

    @override_settings(AI_ENABLED=False)
    def test_native_ai_enable_gate_still_applies(self):
        response = self.client.get(f"/api/documents/{self.document.pk}/ai_suggestions/")
        self.assertEqual(response.status_code, 400)
        self.post.assert_not_called()

    def test_workflow_uses_same_provider_and_native_field_selection(self):
        storage = StoragePath.objects.create(name="Existing path", path="existing")
        self.document.storage_path = storage
        self.document.save()
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.APPLY_AI_SUGGESTIONS,
            ai_suggestion_fields=[WorkflowAction.AISuggestionField.TITLE],
            ai_overwrite_existing=True,
        )
        fields = apply_ai_suggestions_to_document(action, self.document)
        self.document.refresh_from_db()
        self.assertEqual(fields, ["title"])
        self.assertEqual(self.document.title, PROPOSAL["title"])
        self.assertEqual(self.document.storage_path_id, storage.pk)
        self.assertEqual(
            list(self.document.tags.values_list("pk", flat=True)),
            [self.tag.pk],
        )
        self.assertEqual(self.post.call_args.args[0]["requester_id"], self.user.pk)
        self.llm.assert_not_called()

    def test_background_apply_notifies_separately_without_updated_workflow_loop(self):
        action = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.APPLY_AI_SUGGESTIONS,
            ai_suggestion_fields=[WorkflowAction.AISuggestionField.TITLE],
            ai_overwrite_existing=True,
        )
        with (
            patch("documents.tasks.notify_suggestions_applied.delay") as notify,
            patch("documents.tasks.index_document.delay"),
            patch("documents.tasks.document_updated") as updated,
        ):
            tasks.apply_ai_suggestions.apply(
                args=(action.pk, self.document.pk),
                task_id="synthetic-apply-task",
                throw=True,
            )
        event = notify.call_args.args[0]
        self.assertEqual(event["event_id"], "synthetic-apply-task")
        self.assertEqual(event["document_id"], self.document.pk)
        self.assertEqual(event["changed_fields"], ["title"])
        self.assertNotIn("content", event)
        updated.send.assert_not_called()

    def test_notification_only_acknowledges_without_regenerating(self):
        event = applied_event(self.document.pk, 1, ["title"], "synthetic-event")
        self.post.side_effect = lambda value: {"event_id": value["event_id"]}
        tasks.notify_suggestions_applied(event)
        tasks.notify_suggestions_applied(event)
        self.assertEqual(self.post.call_args.args[0], event)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Saved title")
        self.llm.assert_not_called()


@override_settings(
    AI_SUGGESTIONS_ENDPOINT="https://provider.example.invalid/suggestions",
    AI_SUGGESTIONS_API_KEY="synthetic-only",
    AI_SUGGESTIONS_ALLOW_INTERNAL=False,
)
class TestProviderTransport(SimpleTestCase):
    def run_http(self, handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            patch(
                "paperless_ai.suggestion_provider.create_pinned_httpx_client",
                return_value=client,
            ) as factory,
            patch(
                "paperless_ai.suggestion_provider.db_connection_released",
                return_value=nullcontext(),
            ),
        ):
            result = post_provider({"synthetic": True})
        factory.assert_called_once_with(
            "https://provider.example.invalid/suggestions",
            allow_internal=False,
            timeout=120,
            follow_redirects=False,
            trust_env=False,
        )
        return result

    def test_authenticated_post(self):
        def handler(request):
            self.assertEqual(request.headers["Authorization"], "Bearer synthetic-only")
            self.assertEqual(json.loads(request.content), {"synthetic": True})
            return httpx.Response(200, json={"ok": True})

        self.assertEqual(self.run_http(handler), {"ok": True})

    def test_retryable_http_responses(self):
        for code in (408, 409, 425, 429, 500, 503):
            with (
                self.subTest(code=code),
                self.assertRaises(SuggestionProviderUnavailable),
            ):
                self.run_http(
                    lambda request: httpx.Response(code, text="private response body"),
                )

    def test_redirects_and_invalid_payloads_are_not_accepted(self):
        for response in (
            httpx.Response(302, headers={"Location": "http://elsewhere.invalid"}),
            httpx.Response(200, content=b"x" * 1_048_577),
            httpx.Response(200, text="not JSON"),
            httpx.Response(200, json=[]),
        ):
            with (
                self.subTest(response=response),
                self.assertRaises(SuggestionProviderError),
            ):
                self.run_http(lambda request: response)

    def test_transport_failure_does_not_expose_endpoint_credentials(self):
        def handler(request):
            raise httpx.ConnectError("sensitive transport detail")

        with self.assertRaises(SuggestionProviderUnavailable) as error:
            self.run_http(handler)
        self.assertNotIn("sensitive", str(error.exception))

    @override_settings(AI_SUGGESTIONS_ENDPOINT="http://127.0.0.1:8080/suggestions")
    def test_internal_endpoint_requires_explicit_opt_in(self):
        with (
            patch(
                "paperless_ai.suggestion_provider.db_connection_released",
                return_value=nullcontext(),
            ),
            self.assertRaises(SuggestionProviderError),
        ):
            post_provider({"synthetic": True})
