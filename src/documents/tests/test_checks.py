import unittest
from unittest import mock

from django.core.checks import Error
from django.test import TestCase

from .factories import DocumentFactory
from .. import document_consumer_declaration
from ..checks import changed_password_check, parser_check
from ..models import Document


class ChecksTestCase(TestCase):

    def test_changed_password_check_empty_db(self):
        self.assertEqual(changed_password_check(None), [])

    def test_changed_password_check_no_encryption(self):
        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertEqual(changed_password_check(None), [])

    def test_parser_check(self):

        self.assertEqual(parser_check(None), [])

        with mock.patch('documents.checks.document_consumer_declaration.send') as m:
            m.return_value = []

            self.assertEqual(parser_check(None), [Error("No parsers found. This is a bug. The consumer won't be "
                                                        "able to consume any documents without parsers.")])
