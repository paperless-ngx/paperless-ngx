import os
import shutil
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from documents.management.commands.document_thumbnails import _process_document
from documents.models import Document, Tag, Correspondent, DocumentType
from documents.tests.utils import DirectoriesMixin


class TestManageSuperUser(DirectoriesMixin, TestCase):

    def reset_environment(self):
        if "PAPERLESS_ADMIN_USER" in os.environ:
            del os.environ["PAPERLESS_ADMIN_USER"]
        if "PAPERLESS_ADMIN_PASSWORD" in os.environ:
            del os.environ["PAPERLESS_ADMIN_PASSWORD"]

    def setUp(self) -> None:
        super().setUp()
        self.reset_environment()

    def tearDown(self) -> None:
        super().tearDown()
        self.reset_environment()

    def test_no_user(self):
        call_command("manage_superuser")

        # just the consumer user.
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.filter(username="consumer").exists())

    def test_create(self):
        os.environ["PAPERLESS_ADMIN_USER"] = "new_user"
        os.environ["PAPERLESS_ADMIN_PASSWORD"] = "123456"

        call_command("manage_superuser")

        user: User = User.objects.get_by_natural_key("new_user")
        self.assertTrue(user.check_password("123456"))

    def test_update(self):
        os.environ["PAPERLESS_ADMIN_USER"] = "new_user"
        os.environ["PAPERLESS_ADMIN_PASSWORD"] = "123456"

        call_command("manage_superuser")

        os.environ["PAPERLESS_ADMIN_USER"] = "new_user"
        os.environ["PAPERLESS_ADMIN_PASSWORD"] = "more_secure_pwd_7645"

        call_command("manage_superuser")

        user: User = User.objects.get_by_natural_key("new_user")
        self.assertTrue(user.check_password("more_secure_pwd_7645"))

    def test_no_password(self):
        os.environ["PAPERLESS_ADMIN_USER"] = "new_user"

        call_command("manage_superuser")

        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("new_user")
