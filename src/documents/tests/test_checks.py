import unittest

from django.test import TestCase

from .factories import DocumentFactory
from ..checks import changed_password_check
from ..models import Document


class ChecksTestCase(TestCase):

    def test_changed_password_check_empty_db(self):
        self.assertEqual(changed_password_check(None), [])

    def test_changed_password_check_no_encryption(self):
        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(changed_password_check(None), [])
