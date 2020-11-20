import os
import re
import shutil
import tempfile
from unittest import mock
from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from ..consumer import Consumer, ConsumerError
from ..models import FileInfo, Tag, Correspondent, DocumentType, Document
from ..parsers import DocumentParser, ParseError


class TestAttributes(TestCase):

    TAGS = ("tag1", "tag2", "tag3")
    EXTENSIONS = (
        "pdf", "png", "jpg", "jpeg", "gif", "tiff", "tif",
        "PDF", "PNG", "JPG", "JPEG", "GIF", "TIFF", "TIF",
        "PdF", "PnG", "JpG", "JPeG", "GiF", "TiFf", "TiF",
    )

    def _test_guess_attributes_from_name(self, path, sender, title, tags):

        for extension in self.EXTENSIONS:

            f = path.format(extension)
            file_info = FileInfo.from_path(f)

            if sender:
                self.assertEqual(file_info.correspondent.name, sender, f)
            else:
                self.assertIsNone(file_info.correspondent, f)

            self.assertEqual(file_info.title, title, f)

            self.assertEqual(tuple([t.slug for t in file_info.tags]), tags, f)
            if extension.lower() == "jpeg":
                self.assertEqual(file_info.extension, "jpg", f)
            elif extension.lower() == "tif":
                self.assertEqual(file_info.extension, "tiff", f)
            else:
                self.assertEqual(file_info.extension, extension.lower(), f)

    def test_guess_attributes_from_name0(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Title.{}", "Sender", "Title", ())

    def test_guess_attributes_from_name1(self):
        self._test_guess_attributes_from_name(
            "/path/to/Spaced Sender - Title.{}", "Spaced Sender", "Title", ())

    def test_guess_attributes_from_name2(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Spaced Title.{}", "Sender", "Spaced Title", ())

    def test_guess_attributes_from_name3(self):
        self._test_guess_attributes_from_name(
            "/path/to/Dashed-Sender - Title.{}", "Dashed-Sender", "Title", ())

    def test_guess_attributes_from_name4(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Dashed-Title.{}", "Sender", "Dashed-Title", ())

    def test_guess_attributes_from_name5(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Title - tag1,tag2,tag3.{}",
            "Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name6(self):
        self._test_guess_attributes_from_name(
            "/path/to/Spaced Sender - Title - tag1,tag2,tag3.{}",
            "Spaced Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name7(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Spaced Title - tag1,tag2,tag3.{}",
            "Sender",
            "Spaced Title",
            self.TAGS
        )

    def test_guess_attributes_from_name8(self):
        self._test_guess_attributes_from_name(
            "/path/to/Dashed-Sender - Title - tag1,tag2,tag3.{}",
            "Dashed-Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name9(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Dashed-Title - tag1,tag2,tag3.{}",
            "Sender",
            "Dashed-Title",
            self.TAGS
        )

    def test_guess_attributes_from_name10(self):
        self._test_guess_attributes_from_name(
            "/path/to/Σενδερ - Τιτλε - tag1,tag2,tag3.{}",
            "Σενδερ",
            "Τιτλε",
            self.TAGS
        )

    def test_guess_attributes_from_name_when_correspondent_empty(self):
        self._test_guess_attributes_from_name(
            '/path/to/ - weird empty correspondent but should not break.{}',
            None,
            'weird empty correspondent but should not break',
            ()
        )

    def test_guess_attributes_from_name_when_title_starts_with_dash(self):
        self._test_guess_attributes_from_name(
            '/path/to/- weird but should not break.{}',
            None,
            '- weird but should not break',
            ()
        )

    def test_guess_attributes_from_name_when_title_ends_with_dash(self):
        self._test_guess_attributes_from_name(
            '/path/to/weird but should not break -.{}',
            None,
            'weird but should not break -',
            ()
        )

    def test_guess_attributes_from_name_when_title_is_empty(self):
        self._test_guess_attributes_from_name(
            '/path/to/weird correspondent but should not break - .{}',
            'weird correspondent but should not break',
            '',
            ()
        )

    def test_case_insensitive_tag_creation(self):
        """
        Tags should be detected and created as lower case.
        :return:
        """

        path = "Title - Correspondent - tAg1,TAG2.pdf"
        self.assertEqual(len(FileInfo.from_path(path).tags), 2)

        path = "Title - Correspondent - tag1,tag2.pdf"
        self.assertEqual(len(FileInfo.from_path(path).tags), 2)

        self.assertEqual(Tag.objects.all().count(), 2)


class TestFieldPermutations(TestCase):

    valid_dates = (
        "20150102030405Z",
        "20150102Z",
    )
    valid_correspondents = [
        "timmy",
        "Dr. McWheelie",
        "Dash Gor-don",
        "ο Θερμαστής",
        ""
    ]
    valid_titles = ["title", "Title w Spaces", "Title a-dash", "Τίτλος", ""]
    valid_tags = ["tag", "tig,tag", "tag1,tag2,tag-3"]
    valid_extensions = ["pdf", "png", "jpg", "jpeg", "gif"]

    def _test_guessed_attributes(self, filename, created=None,
                                 correspondent=None, title=None,
                                 extension=None, tags=None):

        info = FileInfo.from_path(filename)

        # Created
        if created is None:
            self.assertIsNone(info.created, filename)
        else:
            self.assertEqual(info.created.year, int(created[:4]), filename)
            self.assertEqual(info.created.month, int(created[4:6]), filename)
            self.assertEqual(info.created.day, int(created[6:8]), filename)

        # Correspondent
        if correspondent:
            self.assertEqual(info.correspondent.name, correspondent, filename)
        else:
            self.assertEqual(info.correspondent, None, filename)

        # Title
        self.assertEqual(info.title, title, filename)

        # Tags
        if tags is None:
            self.assertEqual(info.tags, (), filename)
        else:
            self.assertEqual(
                [t.slug for t in info.tags], tags.split(','),
                filename
            )

        # Extension
        if extension == 'jpeg':
            extension = 'jpg'
        self.assertEqual(info.extension, extension, filename)

    def test_just_title(self):
        template = '/path/to/{title}.{extension}'
        for title in self.valid_titles:
            for extension in self.valid_extensions:
                spec = dict(title=title, extension=extension)
                filename = template.format(**spec)
                self._test_guessed_attributes(filename, **spec)

    def test_title_and_correspondent(self):
        template = '/path/to/{correspondent} - {title}.{extension}'
        for correspondent in self.valid_correspondents:
            for title in self.valid_titles:
                for extension in self.valid_extensions:
                    spec = dict(correspondent=correspondent, title=title,
                                extension=extension)
                    filename = template.format(**spec)
                    self._test_guessed_attributes(filename, **spec)

    def test_title_and_correspondent_and_tags(self):
        template = '/path/to/{correspondent} - {title} - {tags}.{extension}'
        for correspondent in self.valid_correspondents:
            for title in self.valid_titles:
                for tags in self.valid_tags:
                    for extension in self.valid_extensions:
                        spec = dict(correspondent=correspondent, title=title,
                                    tags=tags, extension=extension)
                        filename = template.format(**spec)
                        self._test_guessed_attributes(filename, **spec)

    def test_created_and_correspondent_and_title_and_tags(self):

        template = (
            "/path/to/{created} - "
            "{correspondent} - "
            "{title} - "
            "{tags}"
            ".{extension}"
        )

        for created in self.valid_dates:
            for correspondent in self.valid_correspondents:
                for title in self.valid_titles:
                    for tags in self.valid_tags:
                        for extension in self.valid_extensions:
                            spec = {
                                "created": created,
                                "correspondent": correspondent,
                                "title": title,
                                "tags": tags,
                                "extension": extension
                            }
                            self._test_guessed_attributes(
                                template.format(**spec), **spec)

    def test_created_and_correspondent_and_title(self):

        template = "/path/to/{created} - {correspondent} - {title}.{extension}"

        for created in self.valid_dates:
            for correspondent in self.valid_correspondents:
                for title in self.valid_titles:

                    # Skip cases where title looks like a tag as we can't
                    # accommodate such cases.
                    if title.lower() == title:
                        continue

                    for extension in self.valid_extensions:
                        spec = {
                            "created": created,
                            "correspondent": correspondent,
                            "title": title,
                            "extension": extension
                        }
                        self._test_guessed_attributes(
                            template.format(**spec), **spec)

    def test_created_and_title(self):

        template = "/path/to/{created} - {title}.{extension}"

        for created in self.valid_dates:
            for title in self.valid_titles:
                for extension in self.valid_extensions:
                    spec = {
                        "created": created,
                        "title": title,
                        "extension": extension
                    }
                    self._test_guessed_attributes(
                        template.format(**spec), **spec)

    def test_created_and_title_and_tags(self):

        template = "/path/to/{created} - {title} - {tags}.{extension}"

        for created in self.valid_dates:
            for title in self.valid_titles:
                for tags in self.valid_tags:
                    for extension in self.valid_extensions:
                        spec = {
                            "created": created,
                            "title": title,
                            "tags": tags,
                            "extension": extension
                        }
                        self._test_guessed_attributes(
                            template.format(**spec), **spec)

    def test_invalid_date_format(self):
        info = FileInfo.from_path("/path/to/06112017Z - title.pdf")
        self.assertEqual(info.title, "title")
        self.assertIsNone(info.created)

    def test_filename_parse_transforms(self):

        path = "/some/path/to/tag1,tag2_20190908_180610_0001.pdf"
        all_patt = re.compile("^.*$")
        none_patt = re.compile("$a")
        exact_patt = re.compile("^([a-z0-9,]+)_(\\d{8})_(\\d{6})_([0-9]+)\\.")
        repl1 = " - \\4 - \\1."    # (empty) corrspondent, title and tags
        repl2 = "\\2Z - " + repl1  # creation date + repl1

        # No transformations configured (= default)
        info = FileInfo.from_path(path)
        self.assertEqual(info.title, "tag1,tag2_20190908_180610_0001")
        self.assertEqual(info.extension, "pdf")
        self.assertEqual(info.tags, ())
        self.assertIsNone(info.created)

        # Pattern doesn't match (filename unaltered)
        with self.settings(
                FILENAME_PARSE_TRANSFORMS=[(none_patt, "none.gif")]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "tag1,tag2_20190908_180610_0001")
            self.assertEqual(info.extension, "pdf")

        # Simple transformation (match all)
        with self.settings(
                FILENAME_PARSE_TRANSFORMS=[(all_patt, "all.gif")]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "all")
            self.assertEqual(info.extension, "gif")

        # Multiple transformations configured (first pattern matches)
        with self.settings(
                FILENAME_PARSE_TRANSFORMS=[
                    (all_patt, "all.gif"),
                    (all_patt, "anotherall.gif")]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "all")
            self.assertEqual(info.extension, "gif")

        # Multiple transformations configured (second pattern matches)
        with self.settings(
                FILENAME_PARSE_TRANSFORMS=[
                    (none_patt, "none.gif"),
                    (all_patt, "anotherall.gif")]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "anotherall")
            self.assertEqual(info.extension, "gif")

        # Complex transformation without date in replacement string
        with self.settings(
                FILENAME_PARSE_TRANSFORMS=[(exact_patt, repl1)]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "0001")
            self.assertEqual(info.extension, "pdf")
            self.assertEqual(len(info.tags), 2)
            self.assertEqual(info.tags[0].slug, "tag1")
            self.assertEqual(info.tags[1].slug, "tag2")
            self.assertIsNone(info.created)

        # Complex transformation with date in replacement string
        with self.settings(
            FILENAME_PARSE_TRANSFORMS=[
                (none_patt, "none.gif"),
                (exact_patt, repl2),    # <-- matches
                (exact_patt, repl1),
                (all_patt, "all.gif")]):
            info = FileInfo.from_path(path)
            self.assertEqual(info.title, "0001")
            self.assertEqual(info.extension, "pdf")
            self.assertEqual(len(info.tags), 2)
            self.assertEqual(info.tags[0].slug, "tag1")
            self.assertEqual(info.tags[1].slug, "tag2")
            self.assertEqual(info.created.year, 2019)
            self.assertEqual(info.created.month, 9)
            self.assertEqual(info.created.day, 8)


class DummyParser(DocumentParser):

    def get_thumbnail(self):
        # not important during tests
        raise NotImplementedError()

    def __init__(self, path, logging_group, scratch_dir):
        super(DummyParser, self).__init__(path, logging_group)
        _, self.fake_thumb = tempfile.mkstemp(suffix=".png", dir=scratch_dir)

    def get_optimised_thumbnail(self):
        return self.fake_thumb

    def get_text(self):
        return "The Text"


class FaultyParser(DocumentParser):

    def get_thumbnail(self):
        # not important during tests
        raise NotImplementedError()

    def __init__(self, path, logging_group, scratch_dir):
        super(FaultyParser, self).__init__(path, logging_group)
        _, self.fake_thumb = tempfile.mkstemp(suffix=".png", dir=scratch_dir)

    def get_optimised_thumbnail(self):
        return self.fake_thumb

    def get_text(self):
        raise ParseError("Does not compute.")


def fake_magic_from_file(file, mime=False):

    if mime:
        if os.path.splitext(file)[1] == ".pdf":
            return "application/pdf"
        else:
            return "unknown"
    else:
        return "A verbose string that describes the contents of the file"


@mock.patch("documents.consumer.magic.from_file", fake_magic_from_file)
class TestConsumer(TestCase):

    def make_dummy_parser(self, path, logging_group):
        return DummyParser(path, logging_group, self.scratch_dir)

    def make_faulty_parser(self, path, logging_group):
        return FaultyParser(path, logging_group, self.scratch_dir)

    def setUp(self):
        self.scratch_dir = tempfile.mkdtemp()
        self.media_dir = tempfile.mkdtemp()
        self.consumption_dir = tempfile.mkdtemp()

        override_settings(
            SCRATCH_DIR=self.scratch_dir,
            MEDIA_ROOT=self.media_dir,
            ORIGINALS_DIR=os.path.join(self.media_dir, "documents", "originals"),
            THUMBNAIL_DIR=os.path.join(self.media_dir, "documents", "thumbnails"),
            CONSUMPTION_DIR=self.consumption_dir
        ).enable()

        patcher = mock.patch("documents.parsers.document_consumer_declaration.send")
        m = patcher.start()
        m.return_value = [(None, {
            "parser": self.make_dummy_parser,
            "mime_types": ["application/pdf"],
            "weight": 0
        })]

        self.addCleanup(patcher.stop)

        self.consumer = Consumer()

    def tearDown(self):
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        shutil.rmtree(self.media_dir, ignore_errors=True)
        shutil.rmtree(self.consumption_dir, ignore_errors=True)

    def get_test_file(self):
        fd, f = tempfile.mkstemp(suffix=".pdf", dir=self.scratch_dir)
        return f

    def testNormalOperation(self):

        filename = self.get_test_file()
        document = self.consumer.try_consume_file(filename)

        self.assertEqual(document.content, "The Text")
        self.assertEqual(document.title, os.path.splitext(os.path.basename(filename))[0])
        self.assertIsNone(document.correspondent)
        self.assertIsNone(document.document_type)
        self.assertEqual(document.filename, "0000001.pdf")

        self.assertTrue(os.path.isfile(
            document.source_path
        ))

        self.assertTrue(os.path.isfile(
            document.thumbnail_path
        ))

        self.assertFalse(os.path.isfile(filename))

    def testOverrideFilename(self):
        filename = self.get_test_file()
        override_filename = "My Bank - Statement for November.pdf"

        document = self.consumer.try_consume_file(filename, override_filename=override_filename)

        self.assertEqual(document.correspondent.name, "My Bank")
        self.assertEqual(document.title, "Statement for November")

    def testOverrideTitle(self):

        document = self.consumer.try_consume_file(self.get_test_file(), override_title="Override Title")
        self.assertEqual(document.title, "Override Title")

    def testOverrideCorrespondent(self):
        c = Correspondent.objects.create(name="test")

        document = self.consumer.try_consume_file(self.get_test_file(), override_correspondent_id=c.pk)
        self.assertEqual(document.correspondent.id, c.id)

    def testOverrideDocumentType(self):
        dt = DocumentType.objects.create(name="test")

        document = self.consumer.try_consume_file(self.get_test_file(), override_document_type_id=dt.pk)
        self.assertEqual(document.document_type.id, dt.id)

    def testOverrideTags(self):
        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")
        t3 = Tag.objects.create(name="t3")
        document = self.consumer.try_consume_file(self.get_test_file(), override_tag_ids=[t1.id, t3.id])

        self.assertIn(t1, document.tags.all())
        self.assertNotIn(t2, document.tags.all())
        self.assertIn(t3, document.tags.all())

    def testNotAFile(self):
        try:
            self.consumer.try_consume_file("non-existing-file")
        except ConsumerError as e:
            self.assertTrue(str(e).endswith('It is not a file'))
            return

        self.fail("Should throw exception")

    @override_settings(CONSUMPTION_DIR=None)
    def testConsumptionDirUnset(self):
        try:
            self.consumer.try_consume_file(self.get_test_file())
        except ConsumerError as e:
            self.assertEqual(str(e), "The CONSUMPTION_DIR settings variable does not appear to be set.")
            return

        self.fail("Should throw exception")

    @override_settings(CONSUMPTION_DIR="asd")
    def testNoConsumptionDir(self):
        try:
            self.consumer.try_consume_file(self.get_test_file())
        except ConsumerError as e:
            self.assertEqual(str(e), "Consumption directory asd does not exist")
            return

        self.fail("Should throw exception")

    def testDuplicates(self):
        self.consumer.try_consume_file(self.get_test_file())

        try:
            self.consumer.try_consume_file(self.get_test_file())
        except ConsumerError as e:
            self.assertTrue(str(e).endswith("It is a duplicate."))
            return

        self.fail("Should throw exception")

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def testNoParsers(self, m):
        m.return_value = []

        try:
            self.consumer.try_consume_file(self.get_test_file())
        except ConsumerError as e:
            self.assertTrue(str(e).startswith("No parsers abvailable"))
            return

        self.fail("Should throw exception")

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def testFaultyParser(self, m):
        m.return_value = [(None, {
            "parser": self.make_faulty_parser,
            "mime_types": ["application/pdf"],
            "weight": 0
        })]

        try:
            self.consumer.try_consume_file(self.get_test_file())
        except ConsumerError as e:
            self.assertEqual(str(e), "Does not compute.")
            return

        self.fail("Should throw exception.")

    @mock.patch("documents.consumer.Consumer._write")
    def testPostSaveError(self, m):
        filename = self.get_test_file()
        m.side_effect = OSError("NO.")
        try:
            self.consumer.try_consume_file(filename)
        except ConsumerError as e:
            self.assertEqual(str(e), "NO.")
        else:
            self.fail("Should raise exception")

        # file not deleted
        self.assertTrue(os.path.isfile(filename))

        # Database empty
        self.assertEqual(len(Document.objects.all()), 0)

    @override_settings(PAPERLESS_FILENAME_FORMAT="{correspondent}/{title}")
    def testFilenameHandling(self):
        filename = self.get_test_file()

        document = self.consumer.try_consume_file(filename, override_filename="Bank - Test.pdf", override_title="new docs")

        print(document.source_path)
        print("===")

        self.assertEqual(document.title, "new docs")
        self.assertEqual(document.correspondent.name, "Bank")
        self.assertEqual(document.filename, "bank/new-docs-0000001.pdf")

    @mock.patch("documents.consumer.DocumentClassifier")
    def testClassifyDocument(self, m):
        correspondent = Correspondent.objects.create(name="test")
        dtype = DocumentType.objects.create(name="test")
        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")

        m.return_value = MagicMock()
        m.return_value.predict_correspondent.return_value = correspondent.pk
        m.return_value.predict_document_type.return_value = dtype.pk
        m.return_value.predict_tags.return_value = [t1.pk]

        document = self.consumer.try_consume_file(self.get_test_file())

        self.assertEqual(document.correspondent, correspondent)
        self.assertEqual(document.document_type, dtype)
        self.assertIn(t1, document.tags.all())
        self.assertNotIn(t2, document.tags.all())
