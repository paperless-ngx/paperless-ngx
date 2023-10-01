import os
import tempfile
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from documents.models import Document
from documents.models import ShareLink
from documents.tests.utils import DirectoriesMixin


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

        with open(filename, "wb") as f:
            f.write(content)

        doc = Document.objects.create(
            title="none",
            filename=os.path.basename(filename),
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

    @override_settings(
        SOCIAL_AUTH_OIDC_ENABLE=True,
        SOCIAL_AUTH_OIDC_NAME="OIDC Login Link",
    )
    def test_oidc_enabled_login_view(self):
        """
        GIVEN:
            - OIDC Enabled, regular login not disabled
        WHEN:
            - Login template loaded
        THEN:
            - Both options available
        """
        self.client.force_login(self.user)
        response = self.client.get(
            "/accounts/login/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "Sign in",
            response.rendered_content,
        )
        self.assertIn(
            "OIDC Login Link",
            response.rendered_content,
        )

    @override_settings(
        SOCIAL_AUTH_OIDC_ENABLE=True,
        SOCIAL_AUTH_OIDC_NAME="OIDC Login Link",
        SOCIAL_AUTH_DISABLE_NORMAL_AUTH=True,
    )
    def test_oidc_enabled_normal_auth_disabled_login_view(self):
        """
        GIVEN:
            - OIDC Enabled, regular login disabled
        WHEN:
            - Login template loaded
        THEN:
            - Only OIDC login available
        """
        self.client.force_login(self.user)
        response = self.client.get(
            "/accounts/login/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            "Sign in",
            response.rendered_content,
        )
        self.assertIn(
            "OIDC Login Link",
            response.rendered_content,
        )
