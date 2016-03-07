from django.test import TestCase

from ..models import FileInfo


class TestAttachment(TestCase):

    TAGS = ("tag1", "tag2", "tag3")
    SUFFIXES = (
        "pdf", "png", "jpg", "jpeg", "gif",
        "PDF", "PNG", "JPG", "JPEG", "GIF",
        "PdF", "PnG", "JpG", "JPeG", "GiF",
    )

    def _test_guess_attributes_from_name(self, path, sender, title, tags):
        for suffix in self.SUFFIXES:
            f = path.format(suffix)
            file_info = FileInfo.from_path(f)
            self.assertEqual(file_info.correspondent.name, sender, f)
            self.assertEqual(file_info.title, title, f)
            self.assertEqual(tuple([t.slug for t in file_info.tags]), tags, f)
            if suffix.lower() == "jpeg":
                self.assertEqual(file_info.suffix, "jpg", f)
            else:
                self.assertEqual(file_info.suffix, suffix.lower(), f)

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
