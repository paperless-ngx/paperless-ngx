import unittest

from django.test import TestCase

from ..checks import changed_password_check
from ..models import Document
from .factories import DocumentFactory


class ChecksTestCase(TestCase):

    def test_changed_password_check_empty_db(self):
        self.assertEqual(changed_password_check(None), [])

    def test_changed_password_check_no_encryption(self):
        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(changed_password_check(None), [])

    @unittest.skip("I don't know how to test this")
    def test_changed_password_check_gpg_encryption_with_good_password(self):
        pass

    @unittest.skip("I don't know how to test this")
    def test_changed_password_check_fail(self):
        pass
