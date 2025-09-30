import json
import tempfile
from datetime import timedelta
from pathlib import Path

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

from documents.models import Document
from documents.models import ShareLink
from documents.models import Tag
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

    def test_list_with_full_permissions(self):
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

    def test_list_no_n_plus_1_queries(self):
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
