import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
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

    def test_login_redirect(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.url, "/accounts/login/?next=/")

    def test_index(self):
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
    def test_index_app_logo_with_base_url(self):
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

    def test_share_link_views(self):
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


class TestAISuggestions(DirectoriesMixin, TestCase):
    def setUp(self):
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
    def test_suggestions_with_cached_llm(self, mock_refresh_cache, mock_get_cache):
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
    ):
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

    def test_invalidate_suggestions_cache(self):
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
