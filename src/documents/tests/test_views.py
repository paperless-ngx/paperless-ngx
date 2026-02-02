import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status

from documents.caching import get_llm_suggestion_cache
from documents.caching import set_llm_suggestions_cache
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.signals.handlers import update_llm_suggestions_cache
from documents.tests.utils import DirectoriesMixin
from paperless.models import ApplicationConfiguration


class TestViews(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("testuser")
        super().setUp()

    def test_login_redirect(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.url, "/accounts/login/?next=/")

    def test_index(self) -> None:
        self.client.force_login(self.user)
        for language_given, language_actual in [
            ("", "en-US"),
            ("en-US", "en-US"),
            ("de", "de-DE"),
            ("en", "en-US"),
            ("en-us", "en-US"),
            ("fr", "fr-FR"),
            ("jp", "en-US"),
        ]:
            if language_given:
                self.client.cookies.load(
                    {settings.LANGUAGE_COOKIE_NAME: language_given},
                )
            elif settings.LANGUAGE_COOKIE_NAME in self.client.cookies:
                self.client.cookies.pop(settings.LANGUAGE_COOKIE_NAME)

            response = self.client.get(
                "/",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.context_data["webmanifest"],
                f"frontend/{language_actual}/manifest.webmanifest",
            )
            self.assertEqual(
                response.context_data["styles_css"],
                f"frontend/{language_actual}/styles.css",
            )
            self.assertEqual(
                response.context_data["runtime_js"],
                f"frontend/{language_actual}/runtime.js",
            )
            self.assertEqual(
                response.context_data["polyfills_js"],
                f"frontend/{language_actual}/polyfills.js",
            )
            self.assertEqual(
                response.context_data["main_js"],
                f"frontend/{language_actual}/main.js",
            )

    @override_settings(BASE_URL="/paperless/")
    def test_index_app_logo_with_base_url(self) -> None:
        """
        GIVEN:
            - Existing config with app_logo specified
        WHEN:
            - Index page is loaded
        THEN:
            - app_logo is prefixed with BASE_URL
        """
        config = ApplicationConfiguration.objects.first()
        config.app_logo = "/logo/example.jpg"
        config.save()
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertEqual(
            response.context["APP_LOGO"],
            f"/paperless{config.app_logo}",
        )

    def test_share_link_views(self) -> None:
        """
        GIVEN:
            - Share link created
        WHEN:
            - Valid request for share link is made
            - Invalid request for share link is made
            - Request for expired share link is made
        THEN:
            - Document is returned without need for login
            - User is redirected to login with error
            - User is redirected to login with error
        """

        _, filename = tempfile.mkstemp(dir=self.dirs.originals_dir)

        content = b"This is a test"

        with Path(filename).open("wb") as f:
            f.write(content)

        doc = Document.objects.create(
            title="none",
            filename=Path(filename).name,
            mime_type="application/pdf",
        )

        sharelink_permissions = Permission.objects.filter(
            codename__contains="sharelink",
        )
        self.user.user_permissions.add(*sharelink_permissions)
        self.user.save()

        self.client.force_login(self.user)

        self.client.post(
            "/api/share_links/",
            {
                "document": doc.pk,
                "file_version": "original",
            },
        )
        sl1 = ShareLink.objects.get(document=doc)

        self.client.logout()

        # Valid
        response = self.client.get(f"/share/{sl1.slug}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, content)

        # Invalid
        response = self.client.get("/share/123notaslug", follow=True)
        response.render()
        self.assertEqual(response.request["PATH_INFO"], "/accounts/login/")
        self.assertContains(response, b"Share link was not found")

        # Expired
        sl1.expiration = timezone.now() - timedelta(days=1)
        sl1.save()

        response = self.client.get(f"/share/{sl1.slug}", follow=True)
        response.render()
        self.assertEqual(response.request["PATH_INFO"], "/accounts/login/")
        self.assertContains(response, b"Share link has expired")

    def test_list_with_full_permissions(self) -> None:
        """
        GIVEN:
            - Tags with different permissions
        WHEN:
            - Request to get tag list with full permissions is made
        THEN:
            - Tag list is returned with the right permission information
        """
        user2 = User.objects.create(username="user2")
        user3 = User.objects.create(username="user3")
        group1 = Group.objects.create(name="group1")
        group2 = Group.objects.create(name="group2")
        group3 = Group.objects.create(name="group3")
        t1 = Tag.objects.create(name="invoice", pk=1)
        assign_perm("view_tag", self.user, t1)
        assign_perm("view_tag", user2, t1)
        assign_perm("view_tag", user3, t1)
        assign_perm("view_tag", group1, t1)
        assign_perm("view_tag", group2, t1)
        assign_perm("view_tag", group3, t1)
        assign_perm("change_tag", self.user, t1)
        assign_perm("change_tag", user2, t1)
        assign_perm("change_tag", group1, t1)
        assign_perm("change_tag", group2, t1)

        Tag.objects.create(name="bank statement", pk=2)
        d1 = Document.objects.create(
            title="Invoice 1",
            content="This is the invoice of a very expensive item",
            checksum="A",
        )
        d1.tags.add(t1)
        d2 = Document.objects.create(
            title="Invoice 2",
            content="Internet invoice, I should pay it to continue contributing",
            checksum="B",
        )
        d2.tags.add(t1)

        view_permissions = Permission.objects.filter(
            codename__contains="view_tag",
        )
        self.user.user_permissions.add(*view_permissions)
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get("/api/tags/?page=1&full_perms=true")
        results = json.loads(response.content)["results"]
        for tag in results:
            if tag["name"] == "invoice":
                assert tag["permissions"] == {
                    "view": {
                        "users": [self.user.pk, user2.pk, user3.pk],
                        "groups": [group1.pk, group2.pk, group3.pk],
                    },
                    "change": {
                        "users": [self.user.pk, user2.pk],
                        "groups": [group1.pk, group2.pk],
                    },
                }
            elif tag["name"] == "bank statement":
                assert tag["permissions"] == {
                    "view": {"users": [], "groups": []},
                    "change": {"users": [], "groups": []},
                }
            else:
                assert False, f"Unexpected tag found: {tag['name']}"

    def test_list_no_n_plus_1_queries(self) -> None:
        """
        GIVEN:
            - Tags with different permissions
        WHEN:
            - Request to get tag list with full permissions is made
        THEN:
            - Permissions are not queried in database tag by tag,
             i.e. there are no N+1 queries
        """
        view_permissions = Permission.objects.filter(
            codename__contains="view_tag",
        )
        self.user.user_permissions.add(*view_permissions)
        self.user.save()
        self.client.force_login(self.user)

        # Start by a small list, and count the number of SQL queries
        for i in range(2):
            Tag.objects.create(name=f"tag_{i}")

        with CaptureQueriesContext(connection) as ctx_small:
            response_small = self.client.get("/api/tags/?full_perms=true")
            assert response_small.status_code == 200
        num_queries_small = len(ctx_small.captured_queries)

        # Complete the list, and count the number of SQL queries again
        for i in range(2, 50):
            Tag.objects.create(name=f"tag_{i}")

        with CaptureQueriesContext(connection) as ctx_large:
            response_large = self.client.get("/api/tags/?full_perms=true")
            assert response_large.status_code == 200
        num_queries_large = len(ctx_large.captured_queries)

        # A few additional queries are allowed, but not a linear explosion
        assert num_queries_large <= num_queries_small + 5, (
            f"Possible N+1 queries detected: {num_queries_small} queries for 2 tags, "
            f"but {num_queries_large} queries for 50 tags"
        )


class TestAISuggestions(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="testuser")
        self.document = Document.objects.create(
            title="Test Document",
            filename="test.pdf",
            mime_type="application/pdf",
        )
        self.tag1 = Tag.objects.create(name="tag1")
        self.correspondent1 = Correspondent.objects.create(name="correspondent1")
        self.document_type1 = DocumentType.objects.create(name="type1")
        self.path1 = StoragePath.objects.create(name="path1")
        super().setUp()

    @patch("documents.views.get_llm_suggestion_cache")
    @patch("documents.views.refresh_suggestions_cache")
    @override_settings(
        AI_ENABLED=True,
        LLM_BACKEND="mock_backend",
    )
    def test_suggestions_with_cached_llm(
        self,
        mock_refresh_cache,
        mock_get_cache,
    ) -> None:
        mock_get_cache.return_value = MagicMock(suggestions={"tags": ["tag1", "tag2"]})

        self.client.force_login(user=self.user)
        response = self.client.get(f"/api/documents/{self.document.pk}/suggestions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"tags": ["tag1", "tag2"]})
        mock_refresh_cache.assert_called_once_with(self.document.pk)

    @patch("documents.views.get_ai_document_classification")
    @override_settings(
        AI_ENABLED=True,
        LLM_BACKEND="mock_backend",
    )
    def test_suggestions_with_ai_enabled(
        self,
        mock_get_ai_classification,
    ) -> None:
        mock_get_ai_classification.return_value = {
            "title": "AI Title",
            "tags": ["tag1", "tag2"],
            "correspondents": ["correspondent1"],
            "document_types": ["type1"],
            "storage_paths": ["path1"],
            "dates": ["2023-01-01"],
        }

        self.client.force_login(user=self.user)
        response = self.client.get(f"/api/documents/{self.document.pk}/suggestions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "title": "AI Title",
                "tags": [self.tag1.pk],
                "suggested_tags": ["tag2"],
                "correspondents": [self.correspondent1.pk],
                "suggested_correspondents": [],
                "document_types": [self.document_type1.pk],
                "suggested_document_types": [],
                "storage_paths": [self.path1.pk],
                "suggested_storage_paths": [],
                "dates": ["2023-01-01"],
            },
        )

    def test_invalidate_suggestions_cache(self) -> None:
        self.client.force_login(user=self.user)
        suggestions = {
            "title": "AI Title",
            "tags": ["tag1", "tag2"],
            "correspondents": ["correspondent1"],
            "document_types": ["type1"],
            "storage_paths": ["path1"],
            "dates": ["2023-01-01"],
        }
        set_llm_suggestions_cache(
            self.document.pk,
            suggestions,
            backend="mock_backend",
        )
        self.assertEqual(
            get_llm_suggestion_cache(
                self.document.pk,
                backend="mock_backend",
            ).suggestions,
            suggestions,
        )
        # post_save signal triggered
        update_llm_suggestions_cache(
            sender=None,
            instance=self.document,
        )
        self.assertIsNone(
            get_llm_suggestion_cache(
                self.document.pk,
                backend="mock_backend",
            ),
        )


class TestAIChatStreamingView(DirectoriesMixin, TestCase):
    ENDPOINT = "/api/documents/chat/"

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.client.force_login(user=self.user)
        self.document = Document.objects.create(
            title="Test Document",
            filename="test.pdf",
            mime_type="application/pdf",
        )
        super().setUp()

    @override_settings(AI_ENABLED=False)
    def test_post_ai_disabled(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            data='{"q": "question"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"AI is required for this feature", response.content)

    @patch("documents.views.stream_chat_with_documents")
    @patch("documents.views.get_objects_for_user_owner_aware")
    @override_settings(AI_ENABLED=True)
    def test_post_no_document_id(self, mock_get_objects, mock_stream_chat) -> None:
        mock_get_objects.return_value = [self.document]
        mock_stream_chat.return_value = iter([b"data"])
        response = self.client.post(
            self.ENDPOINT,
            data='{"q": "question"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")

    @patch("documents.views.stream_chat_with_documents")
    @override_settings(AI_ENABLED=True)
    def test_post_with_document_id(self, mock_stream_chat) -> None:
        mock_stream_chat.return_value = iter([b"data"])
        response = self.client.post(
            self.ENDPOINT,
            data=f'{{"q": "question", "document_id": {self.document.pk}}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")

    @override_settings(AI_ENABLED=True)
    def test_post_with_invalid_document_id(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            data='{"q": "question", "document_id": 999999}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Document not found", response.content)

    @patch("documents.views.has_perms_owner_aware")
    @override_settings(AI_ENABLED=True)
    def test_post_with_document_id_no_permission(self, mock_has_perms) -> None:
        mock_has_perms.return_value = False
        response = self.client.post(
            self.ENDPOINT,
            data=f'{{"q": "question", "document_id": {self.document.pk}}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Insufficient permissions", response.content)
