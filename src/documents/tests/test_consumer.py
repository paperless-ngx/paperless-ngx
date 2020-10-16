import re

from django.test import TestCase
from unittest import mock
from tempfile import TemporaryDirectory

from ..consumer import Consumer
from ..models import FileInfo, Tag


class TestConsumer(TestCase):

    class DummyParser(object):
        pass

    def test__get_parser_class_1_parser(self):
        self.assertEqual(
            self._get_consumer()._get_parser_class("doc.pdf"),
            self.DummyParser
        )

    @mock.patch("documents.consumer.os.makedirs")
    @mock.patch("documents.consumer.os.path.exists", return_value=True)
    @mock.patch("documents.consumer.document_consumer_declaration.send")
    def test__get_parser_class_n_parsers(self, m, *args):

        class DummyParser1(object):
            pass

        class DummyParser2(object):
            pass

        m.return_value = (
            (None, lambda _: {"weight": 0, "parser": DummyParser1}),
            (None, lambda _: {"weight": 1, "parser": DummyParser2}),
        )
        with TemporaryDirectory() as tmpdir:
            self.assertEqual(
                Consumer(consume=tmpdir)._get_parser_class("doc.pdf"),
                DummyParser2
            )

    @mock.patch("documents.consumer.os.makedirs")
    @mock.patch("documents.consumer.os.path.exists", return_value=True)
    @mock.patch("documents.consumer.document_consumer_declaration.send")
    def test__get_parser_class_0_parsers(self, m, *args):
        m.return_value = ((None, lambda _: None),)
        with TemporaryDirectory() as tmpdir:
            self.assertIsNone(
                Consumer(consume=tmpdir)._get_parser_class("doc.pdf")
            )

    @mock.patch("documents.consumer.os.makedirs")
    @mock.patch("documents.consumer.os.path.exists", return_value=True)
    @mock.patch("documents.consumer.document_consumer_declaration.send")
    def _get_consumer(self, m, *args):
        m.return_value = (
            (None, lambda _: {"weight": 0, "parser": self.DummyParser}),
        )
        with TemporaryDirectory() as tmpdir:
            return Consumer(consume=tmpdir)


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
