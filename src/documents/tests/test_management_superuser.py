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
        if "PAPERLESS_ADMIN_PASSWORD" in os.environ:
            del os.environ["PAPERLESS_ADMIN_PASSWORD"]

    def setUp(self) -> None:
        super().setUp()
        self.reset_environment()

    def tearDown(self) -> None:
        super().tearDown()
        self.reset_environment()

    def test_some_users(self):
        User.objects.create_superuser('someuser', 'root@localhost', '123456')
        os.environ["PAPERLESS_ADMIN_PASSWORD"] = "123456"

        call_command("manage_superuser")
 
        self.assertEqual(User.objects.count(), 1)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("admin")

    def test_create(self):
        os.environ["PAPERLESS_ADMIN_PASSWORD"] = "123456"

        call_command("manage_superuser")

        user: User = User.objects.get_by_natural_key("admin")
        self.assertTrue(user.check_password("123456"))

    def test_no_password(self):
        call_command("manage_superuser")

        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("admin")
