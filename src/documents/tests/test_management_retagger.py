from django.core.management import call_command
from django.test import TestCase

from documents.models import Document, Tag, Correspondent, DocumentType
from documents.tests.utils import DirectoriesMixin


class TestRetagger(DirectoriesMixin, TestCase):

    def make_models(self):
        self.d1 = Document.objects.create(checksum="A", title="A", content="first document")
        self.d2 = Document.objects.create(checksum="B", title="B", content="second document")
        self.d3 = Document.objects.create(checksum="C", title="C", content="unrelated document")

        self.tag_first = Tag.objects.create(name="tag1", match="first", matching_algorithm=Tag.MATCH_ANY)
        self.tag_second = Tag.objects.create(name="tag2", match="second", matching_algorithm=Tag.MATCH_ANY)
        self.tag_inbox = Tag.objects.create(name="test", is_inbox_tag=True)
        self.tag_no_match = Tag.objects.create(name="test2")

        self.d3.tags.add(self.tag_inbox)
        self.d3.tags.add(self.tag_no_match)

        self.correspondent_first = Correspondent.objects.create(
            name="c1", match="first", matching_algorithm=Correspondent.MATCH_ANY)
        self.correspondent_second = Correspondent.objects.create(
            name="c2", match="second", matching_algorithm=Correspondent.MATCH_ANY)

        self.doctype_first = DocumentType.objects.create(
            name="dt1", match="first", matching_algorithm=DocumentType.MATCH_ANY)
        self.doctype_second = DocumentType.objects.create(
            name="dt2", match="second", matching_algorithm=DocumentType.MATCH_ANY)

    def get_updated_docs(self):
        return Document.objects.get(title="A"), Document.objects.get(title="B"), Document.objects.get(title="C")

    def setUp(self) -> None:
        super(TestRetagger, self).setUp()
        self.make_models()

    def test_add_tags(self):
        call_command('document_retagger', '--tags')
        d_first, d_second, d_unrelated = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 1)
        self.assertEqual(d_second.tags.count(), 1)
        self.assertEqual(d_unrelated.tags.count(), 2)

        self.assertEqual(d_first.tags.first(), self.tag_first)
        self.assertEqual(d_second.tags.first(), self.tag_second)

    def test_add_type(self):
        call_command('document_retagger', '--document_type')
        d_first, d_second, d_unrelated = self.get_updated_docs()

        self.assertEqual(d_first.document_type, self.doctype_first)
        self.assertEqual(d_second.document_type, self.doctype_second)

    def test_add_correspondent(self):
        call_command('document_retagger', '--correspondent')
        d_first, d_second, d_unrelated = self.get_updated_docs()

        self.assertEqual(d_first.correspondent, self.correspondent_first)
        self.assertEqual(d_second.correspondent, self.correspondent_second)

    def test_force_preserve_inbox(self):
        call_command('document_retagger', '--tags', '--overwrite')

        d_first, d_second, d_unrelated = self.get_updated_docs()

        self.assertCountEqual([tag.id for tag in d_unrelated.tags.all()], [self.tag_inbox.id, self.tag_no_match.id])
