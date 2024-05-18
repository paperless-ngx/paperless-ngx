from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


class TestRetagger(DirectoriesMixin, TestCase):
    def make_models(self):
        self.sp1 = StoragePath.objects.create(
            name="dummy a",
            path="{created_data}/{title}",
            match="auto document",
            matching_algorithm=StoragePath.MATCH_LITERAL,
        )
        self.sp2 = StoragePath.objects.create(
            name="dummy b",
            path="{title}",
            match="^first|^unrelated",
            matching_algorithm=StoragePath.MATCH_REGEX,
        )

        self.sp3 = StoragePath.objects.create(
            name="dummy c",
            path="{title}",
            match="^blah",
            matching_algorithm=StoragePath.MATCH_REGEX,
        )

        self.d1 = Document.objects.create(
            checksum="A",
            title="A",
            content="first document",
        )
        self.d2 = Document.objects.create(
            checksum="B",
            title="B",
            content="second document",
        )
        self.d3 = Document.objects.create(
            checksum="C",
            title="C",
            content="unrelated document",
            storage_path=self.sp3,
        )
        self.d4 = Document.objects.create(
            checksum="D",
            title="D",
            content="auto document",
        )

        self.tag_first = Tag.objects.create(
            name="tag1",
            match="first",
            matching_algorithm=Tag.MATCH_ANY,
        )
        self.tag_second = Tag.objects.create(
            name="tag2",
            match="second",
            matching_algorithm=Tag.MATCH_ANY,
        )
        self.tag_inbox = Tag.objects.create(name="test", is_inbox_tag=True)
        self.tag_no_match = Tag.objects.create(name="test2")
        self.tag_auto = Tag.objects.create(
            name="tagauto",
            matching_algorithm=Tag.MATCH_AUTO,
        )

        self.d3.tags.add(self.tag_inbox)
        self.d3.tags.add(self.tag_no_match)
        self.d4.tags.add(self.tag_auto)

        self.correspondent_first = Correspondent.objects.create(
            name="c1",
            match="first",
            matching_algorithm=Correspondent.MATCH_ANY,
        )
        self.correspondent_second = Correspondent.objects.create(
            name="c2",
            match="second",
            matching_algorithm=Correspondent.MATCH_ANY,
        )

        self.doctype_first = DocumentType.objects.create(
            name="dt1",
            match="first",
            matching_algorithm=DocumentType.MATCH_ANY,
        )
        self.doctype_second = DocumentType.objects.create(
            name="dt2",
            match="second",
            matching_algorithm=DocumentType.MATCH_ANY,
        )

    def get_updated_docs(self):
        return (
            Document.objects.get(title="A"),
            Document.objects.get(title="B"),
            Document.objects.get(title="C"),
            Document.objects.get(title="D"),
        )

    def setUp(self) -> None:
        super().setUp()
        self.make_models()

    def test_add_tags(self):
        call_command("document_retagger", "--tags")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 1)
        self.assertEqual(d_second.tags.count(), 1)
        self.assertEqual(d_unrelated.tags.count(), 2)
        self.assertEqual(d_auto.tags.count(), 1)

        self.assertEqual(d_first.tags.first(), self.tag_first)
        self.assertEqual(d_second.tags.first(), self.tag_second)

    def test_add_type(self):
        call_command("document_retagger", "--document_type")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.document_type, self.doctype_first)
        self.assertEqual(d_second.document_type, self.doctype_second)

    def test_add_correspondent(self):
        call_command("document_retagger", "--correspondent")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.correspondent, self.correspondent_first)
        self.assertEqual(d_second.correspondent, self.correspondent_second)

    def test_overwrite_preserve_inbox(self):
        self.d1.tags.add(self.tag_second)

        call_command("document_retagger", "--tags", "--overwrite")

        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNotNone(Tag.objects.get(id=self.tag_second.id))

        self.assertCountEqual(
            [tag.id for tag in d_first.tags.all()],
            [self.tag_first.id],
        )
        self.assertCountEqual(
            [tag.id for tag in d_second.tags.all()],
            [self.tag_second.id],
        )
        self.assertCountEqual(
            [tag.id for tag in d_unrelated.tags.all()],
            [self.tag_inbox.id, self.tag_no_match.id],
        )
        self.assertEqual(d_auto.tags.count(), 0)

    def test_add_tags_suggest(self):
        call_command("document_retagger", "--tags", "--suggest")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 0)
        self.assertEqual(d_second.tags.count(), 0)
        self.assertEqual(d_auto.tags.count(), 1)

    def test_add_type_suggest(self):
        call_command("document_retagger", "--document_type", "--suggest")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNone(d_first.document_type)
        self.assertIsNone(d_second.document_type)

    def test_add_correspondent_suggest(self):
        call_command("document_retagger", "--correspondent", "--suggest")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNone(d_first.correspondent)
        self.assertIsNone(d_second.correspondent)

    def test_add_tags_suggest_url(self):
        call_command(
            "document_retagger",
            "--tags",
            "--suggest",
            "--base-url=http://localhost",
        )
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.tags.count(), 0)
        self.assertEqual(d_second.tags.count(), 0)
        self.assertEqual(d_auto.tags.count(), 1)

    def test_add_type_suggest_url(self):
        call_command(
            "document_retagger",
            "--document_type",
            "--suggest",
            "--base-url=http://localhost",
        )
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNone(d_first.document_type)
        self.assertIsNone(d_second.document_type)

    def test_add_correspondent_suggest_url(self):
        call_command(
            "document_retagger",
            "--correspondent",
            "--suggest",
            "--base-url=http://localhost",
        )
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertIsNone(d_first.correspondent)
        self.assertIsNone(d_second.correspondent)

    def test_add_storage_path(self):
        """
        GIVEN:
            - 2 storage paths with documents which match them
            - 1 document which matches but has a storage path
        WHEN:
            - document retagger is called
        THEN:
            - Matching document's storage paths updated
            - Non-matching documents have no storage path
            - Existing storage patch left unchanged
        """
        call_command(
            "document_retagger",
            "--storage_path",
        )
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.storage_path, self.sp2)
        self.assertEqual(d_auto.storage_path, self.sp1)
        self.assertIsNone(d_second.storage_path)
        self.assertEqual(d_unrelated.storage_path, self.sp3)

    def test_overwrite_storage_path(self):
        """
        GIVEN:
            - 2 storage paths with documents which match them
            - 1 document which matches but has a storage path
        WHEN:
            - document retagger is called with overwrite
        THEN:
            - Matching document's storage paths updated
            - Non-matching documents have no storage path
            - Existing storage patch overwritten
        """
        call_command("document_retagger", "--storage_path", "--overwrite")
        d_first, d_second, d_unrelated, d_auto = self.get_updated_docs()

        self.assertEqual(d_first.storage_path, self.sp2)
        self.assertEqual(d_auto.storage_path, self.sp1)
        self.assertIsNone(d_second.storage_path)
        self.assertEqual(d_unrelated.storage_path, self.sp2)

    def test_id_range_parameter(self):
        commandOutput = ""
        Document.objects.create(
            checksum="E",
            title="E",
            content="NOT the first document",
        )
        call_command("document_retagger", "--tags", "--id-range", "1", "2")
        # The retagger shouldn`t apply the 'first' tag to our new document
        self.assertEqual(Document.objects.filter(tags__id=self.tag_first.id).count(), 1)

        try:
            commandOutput = call_command("document_retagger", "--tags", "--id-range")
        except CommandError:
            # Just ignore the error
            None
        self.assertIn(commandOutput, "Error: argument --id-range: expected 2 arguments")

        try:
            commandOutput = call_command(
                "document_retagger",
                "--tags",
                "--id-range",
                "a",
                "b",
            )
        except CommandError:
            # Just ignore the error
            None
        self.assertIn(commandOutput, "error: argument --id-range: invalid int value:")

        call_command("document_retagger", "--tags", "--id-range", "1", "9999")
        # Now we should have 2 documents
        self.assertEqual(Document.objects.filter(tags__id=self.tag_first.id).count(), 2)
