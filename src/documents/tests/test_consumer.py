import os
from unittest import mock, skipIf

import pyocr
from django.test import TestCase
from pyocr.libtesseract.tesseract_raw import \
    TesseractError as OtherTesseractError

from ..models import FileInfo
from ..consumer import image_to_string, strip_excess_whitespace


class TestAttributes(TestCase):

    TAGS = ("tag1", "tag2", "tag3")
    EXTENSIONS = (
        "pdf", "png", "jpg", "jpeg", "gif",
        "PDF", "PNG", "JPG", "JPEG", "GIF",
        "PdF", "PnG", "JpG", "JPeG", "GiF",
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

        template = ("/path/to/{created} - "
                    "{correspondent} - "
                    "{title} - "
                    "{tags}"
                    ".{extension}")

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

        template = ("/path/to/{created} - "
                    "{correspondent} - "
                    "{title}"
                    ".{extension}")

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

        template = ("/path/to/{created} - "
                    "{title}"
                    ".{extension}")

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

        template = ("/path/to/{created} - "
                    "{title} - "
                    "{tags}"
                    ".{extension}")

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


class FakeTesseract(object):

    @staticmethod
    def can_detect_orientation():
        return True

    @staticmethod
    def detect_orientation(file_handle, lang):
        raise OtherTesseractError("arbitrary status", "message")

    @staticmethod
    def image_to_string(file_handle, lang):
        return "This is test text"


class FakePyOcr(object):

    @staticmethod
    def get_available_tools():
        return [FakeTesseract]


class TestOCR(TestCase):

    text_cases = [
        ("simple     string", "simple string"),
        (
            "simple    newline\n   testing string",
            "simple newline\ntesting string"
        ),
        (
            "utf-8   строка с пробелами в конце  ",
            "utf-8 строка с пробелами в конце"
        )
    ]
    
    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")
    TESSERACT_INSTALLED = bool(pyocr.get_available_tools())

    def test_strip_excess_whitespace(self):
        for source, result in self.text_cases:
            actual_result = strip_excess_whitespace(source)
            self.assertEqual(
                result,
                actual_result,
                "strip_exceess_whitespace({}) != '{}', but '{}'".format(
                    source,
                    result,
                    actual_result
                )
            )

    @skipIf(not TESSERACT_INSTALLED, "Tesseract not installed. Skipping")
    @mock.patch("documents.consumer.Consumer.SCRATCH", SAMPLE_FILES)
    @mock.patch("documents.consumer.pyocr", FakePyOcr)
    def test_image_to_string_with_text_free_page(self):
        """
        This test is sort of silly, since it's really just reproducing an odd
        exception thrown by pyocr when it encounters a page with no text.
        Actually running this test against an installation of Tesseract results
        in a segmentation fault rooted somewhere deep inside pyocr where I
        don't care to dig.  Regardless, if you run the consumer normally,
        text-free pages are now handled correctly so long as we work around
        this weird exception.
        """
        image_to_string(["text.png", "en"])
