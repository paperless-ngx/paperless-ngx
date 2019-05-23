from random import randint

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ..models import Correspondent, Document, Tag
from ..signals import document_consumption_finished

@override_settings(POST_CONSUME_SCRIPT=None)
class TestDocumentConsumptionFinishedSignal(TestCase):
    """
    We make use of document_consumption_finished, so we should test that it's
    doing what we expect wrt to tag & correspondent matching.
    """

    def setUp(self):
        TestCase.setUp(self)
        User.objects.create_user(username='test_consumer', password='12345')
        self.doc_contains = Document.objects.create(
            content="I contain the keyword.", file_type="pdf")

    def test_tag_applied_any(self):
        t1 = Tag.objects.create(
            name="test", match="keyword", matching_algorithm=Tag.MATCH_ANY)
        document_consumption_finished.send(
            sender=self.__class__, document=self.doc_contains)
        self.assertTrue(list(self.doc_contains.tags.all()) == [t1])

    def test_tag_not_applied(self):
        Tag.objects.create(
            name="test", match="no-match", matching_algorithm=Tag.MATCH_ANY)
        document_consumption_finished.send(
            sender=self.__class__, document=self.doc_contains)
        self.assertTrue(list(self.doc_contains.tags.all()) == [])

    def test_correspondent_applied(self):
        correspondent = Correspondent.objects.create(
            name="test",
            match="keyword",
            matching_algorithm=Correspondent.MATCH_ANY
        )
        document_consumption_finished.send(
            sender=self.__class__, document=self.doc_contains)
        self.assertTrue(self.doc_contains.correspondent == correspondent)

    def test_correspondent_not_applied(self):
        Tag.objects.create(
            name="test",
            match="no-match",
            matching_algorithm=Correspondent.MATCH_ANY
        )
        document_consumption_finished.send(
            sender=self.__class__, document=self.doc_contains)
        self.assertEqual(self.doc_contains.correspondent, None)

    def test_logentry_created(self):
        document_consumption_finished.send(
            sender=self.__class__, document=self.doc_contains)

        self.assertEqual(LogEntry.objects.count(), 1)
