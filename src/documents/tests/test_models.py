from django.test import TestCase

from .factories import DocumentFactory, CorrespondentFactory
from ..models import Document, Correspondent


class CorrespondentTestCase(TestCase):

    def test___str__(self):
        for s in ("test", "οχι", "test with fun_charÅc'\"terß"):
            correspondent = CorrespondentFactory.create(name=s)
            self.assertEqual(str(correspondent), s)


class DocumentTestCase(TestCase):

    def test_correspondent_deletion_does_not_cascade(self):

        self.assertEqual(Correspondent.objects.all().count(), 0)
        correspondent = CorrespondentFactory.create()
        self.assertEqual(Correspondent.objects.all().count(), 1)

        self.assertEqual(Document.objects.all().count(), 0)
        DocumentFactory.create(correspondent=correspondent)
        self.assertEqual(Document.objects.all().count(), 1)
        self.assertIsNotNone(Document.objects.all().first().correspondent)

        correspondent.delete()
        self.assertEqual(Correspondent.objects.all().count(), 0)
        self.assertEqual(Document.objects.all().count(), 1)
        self.assertIsNone(Document.objects.all().first().correspondent)
