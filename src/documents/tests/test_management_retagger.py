from django.core.management import call_command
from django.test import TestCase

from documents.models import Document, Tag, Correspondent, DocumentType
from documents.tests.utils import DirectoriesMixin


class TestRetagger(DirectoriesMixin, TestCase):

    def make_models(self):
        self.d1 = Document.objects.create(checksum="A", title="A", content="first document")
        self.d2 = Document.objects.create(checksum="B", title="B", content="second document")
        self.d3 = Document.objects.create(checksum="C", title="C", content="unrelated document")
        self.d4 = Document.objects.create(checksum="D", title="D", content="auto document")

        self.tag_first = Tag.objects.create(name="tag1", match="first", matching_algorithm=Tag.MATCH_ANY)
        self.tag_second = Tag.objects.create(name="tag2", match="second", matching_algorithm=Tag.MATCH_ANY)
        self.tag_inbox = Tag.objects.create(name="test", is_inbox_tag=True)
        self.tag_no_match = Tag.objects.create(name="test2")
        self.tag_auto = Tag.objects.create(name="tagauto", matching_algorithm=Tag.MATCH_AUTO)

        self.d3.tags.add(self.tag_inbox)
        self.d3.tags.add(self.tag_no_match)
        self.d4.tags.add(self.tag_auto)


        self.correspondent_first = Correspondent.objects.create(
            name="c1", match="first", matching_algorithm=Correspondent.MATCH_ANY)
        self.correspondent_second = Correspondent.objects.create(
            name="c2", match="second", matching_algorithm=Correspondent.MATCH_ANY)

        self.doctype_first = DocumentType.objects.create(
            name="dt1", match="first", matching_algorithm=DocumentType.MATCH_ANY)
        self.doctype_second = DocumentType.objects.create(
            name="dt2", match="second", matching_algorithm=DocumentType.MATCH_ANY)

    def get_updated_docs(self):
        return Document.objects.get(title="A"), Document.objects.get(title="B"), \
            Document.objects.get(title="C"), Document.objects.get(title="D")

    def setUp(self) -> None:
        super(TestRetagger, self).setUp()
        self.make_models()

    def test_add_tags(self):
        call_command('document_retagger', '--tags')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 1)
        self.assertEqual(d_second.tags.count(), 1)
        self.assertEqual(d_unrelated.tags.count(), 2)
        self.assertEqual(d_auto.tags.count(), 1)

        self.assertEqual(d_first.tags.first(), self.tag_first)
        self.assertEqual(d_second.tags.first(), self.tag_second)

    def test_add_type(self):
        call_command('document_retagger', '--document_type')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.document_type, self.doctype_first)
        self.assertEqual(d_second.document_type, self.doctype_second)

    def test_add_correspondent(self):
        call_command('document_retagger', '--correspondent')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.correspondent, self.correspondent_first)
        self.assertEqual(d_second.correspondent, self.correspondent_second)

    def test_overwrite_preserve_inbox(self):
        self.d1.tags.add(self.tag_second)

        call_command('document_retagger', '--tags', '--overwrite')

        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNotNone(Tag.objects.get(id=self.tag_second.id))

        self.assertCountEqual([tag.id for tag in d_first.tags.all()], [self.tag_first.id])
        self.assertCountEqual([tag.id for tag in d_second.tags.all()], [self.tag_second.id])
        self.assertCountEqual([tag.id for tag in d_unrelated.tags.all()], [self.tag_inbox.id, self.tag_no_match.id])
        self.assertEqual(d_auto.tags.count(), 0)

    def test_add_tags_suggest(self):
        call_command('document_retagger', '--tags', '--suggest')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 0)
        self.assertEqual(d_second.tags.count(), 0)
        self.assertEqual(d_auto.tags.count(), 1)

    def test_add_type_suggest(self):
        call_command('document_retagger', '--document_type', '--suggest')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.document_type, None)
        self.assertEqual(d_second.document_type, None)

    def test_add_correspondent_suggest(self):
        call_command('document_retagger', '--correspondent', '--suggest')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.correspondent, None)
        self.assertEqual(d_second.correspondent, None)

    def test_add_tags_suggest_url(self):
        call_command('document_retagger', '--tags', '--suggest', '--base-url=http://localhost')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 0)
        self.assertEqual(d_second.tags.count(), 0)
        self.assertEqual(d_auto.tags.count(), 1)

    def test_add_type_suggest_url(self):
        call_command('document_retagger', '--document_type', '--suggest', '--base-url=http://localhost')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.document_type, None)
        self.assertEqual(d_second.document_type, None)

    def test_add_correspondent_suggest_url(self):
        call_command('document_retagger', '--correspondent', '--suggest', '--base-url=http://localhost')
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.correspondent, None)
        self.assertEqual(d_second.correspondent, None)
