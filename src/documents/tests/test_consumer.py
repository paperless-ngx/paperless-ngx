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


class Permutations(TestCase):
    valid_correspondents = ['timmy', 'Dr. McWheelie',
                            'Dash Gor-don', 'ο Θερμαστής']
    valid_titles = ['title', 'Title w Spaces', 'Title a-dash', 'Τίτλος', '']
    valid_tags = ['tag', 'tig,tag', '-', '0,1,2', '']
    valid_suffixes = ['pdf', 'png', 'jpg', 'jpeg', 'gif']

    def _test_guessed_attributes(
            self, filename, title, suffix, correspondent=None, tags=None):
        file_info = FileInfo.from_path(filename)

        # Required
        self.assertEqual(file_info.title, title, filename)
        if suffix == 'jpeg':
            suffix = 'jpg'
        self.assertEqual(file_info.suffix, suffix, filename)
        # Optional
        if correspondent is None:
            self.assertEqual(file_info.correspondent,
                             correspondent, filename)
        else:
            self.assertEqual(file_info.correspondent.name,
                             correspondent, filename)
        if tags is None:
            self.assertEqual(file_info.tags, (), filename)
        else:
            self.assertEqual([t.slug for t in file_info.tags],
                             tags.split(','),
                             filename)

    def test_just_title(self):
        template = '/path/to/{title}.{suffix}'
        for title in self.valid_titles:
            for suffix in self.valid_suffixes:
                spec = dict(title=title, suffix=suffix)
                filename = template.format(**spec)
                self._test_guessed_attributes(filename, **spec)

    def test_title_and_correspondent(self):
        template = '/path/to/{correspondent} - {title}.{suffix}'
        for correspondent in self.valid_correspondents:
            for title in self.valid_titles:
                for suffix in self.valid_suffixes:
                    spec = dict(correspondent=correspondent, title=title,
                                suffix=suffix)
                    filename = template.format(**spec)
                    self._test_guessed_attributes(filename, **spec)

    def test_title_and_correspondent_and_tags(self):
        template = '/path/to/{correspondent} - {title} - {tags}.{suffix}'
        for correspondent in self.valid_correspondents:
            for title in self.valid_titles:
                for tags in self.valid_tags:
                    for suffix in self.valid_suffixes:
                        spec = dict(correspondent=correspondent, title=title,
                                    tags=tags, suffix=suffix)
                        filename = template.format(**spec)
                        self._test_guessed_attributes(filename, **spec)
