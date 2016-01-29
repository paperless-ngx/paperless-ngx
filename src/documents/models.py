import os
import re

from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone


class SluggedModel(models.Model):

    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(blank=True)

    class Meta(object):
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        models.Model.save(self, *args, **kwargs)

    def __str__(self):
        return self.name


class Sender(SluggedModel):

    class Meta(object):
        ordering = ("name",)


class Tag(SluggedModel):
    
    COLOURS = (
        (1, "#a6cee3"),
        (2, "#1f78b4"),
        (3, "#b2df8a"),
        (4, "#33a02c"),
        (5, "#fb9a99"),
        (6, "#e31a1c"),
        (7, "#fdbf6f"),
        (8, "#ff7f00"),
        (9, "#cab2d6"),
        (10, "#6a3d9a"),
        (11, "#b15928"),
        (12, "#000000"),
        (13, "#cccccc")
    )

    MATCH_ANY = 1
    MATCH_ALL = 2
    MATCH_LITERAL = 3
    MATCH_REGEX = 4
    MATCHING_ALGORITHMS = (
        (MATCH_ANY, "Any"),
        (MATCH_ALL, "All"),
        (MATCH_LITERAL, "Literal"),
        (MATCH_REGEX, "Regular Expression"),
    )

    colour = models.PositiveIntegerField(choices=COLOURS, default=1)
    match = models.CharField(max_length=256, blank=True)
    matching_algorithm = models.PositiveIntegerField(
        choices=MATCHING_ALGORITHMS,
        blank=True,
        null=True,
        help_text=(
            "Which algorithm you want to use when matching text to the OCR'd "
            "PDF.  Here, \"any\" looks for any occurrence of any word provided "
            "in the PDF, while \"all\" requires that every word provided "
            "appear in the PDF, albeit not in the order provided.  A "
            "\"literal\" match means that the text you enter must appear in "
            "the PDF exactly as you've entered it, and \"regular expression\" "
            "uses a regex to match the PDF.  If you don't know what a regex"
            "is, you probably don't want this option."
        )
    )

    @property
    def conditions(self):
        return "{}: \"{}\" ({})".format(
            self.name, self.match, self.get_matching_algorithm_display())

    def matches(self, text):

        if self.matching_algorithm == self.MATCH_ALL:
            for word in self.match.split(" "):
                if word not in text:
                    return False
            return True

        if self.matching_algorithm == self.MATCH_ANY:
            for word in self.match.split(" "):
                if word in text:
                    return True
            return False

        if self.matching_algorithm == self.MATCH_LITERAL:
            return self.match in text

        if self.matching_algorithm == self.MATCH_REGEX:
            return re.search(re.compile(self.match), text)

        raise NotImplementedError("Unsupported matching algorithm")

    def save(self, *args, **kwargs):
        self.match = self.match.lower()
        SluggedModel.save(self, *args, **kwargs)


class Document(models.Model):

    TYPE_PDF = "pdf"
    TYPE_PNG = "png"
    TYPE_JPG = "jpg"
    TYPE_GIF = "gif"
    TYPE_TIF = "tiff"
    TYPES = (TYPE_PDF, TYPE_PNG, TYPE_JPG, TYPE_GIF, TYPE_TIF,)

    sender = models.ForeignKey(
        Sender, blank=True, null=True, related_name="documents")
    title = models.CharField(max_length=128, blank=True, db_index=True)
    content = models.TextField(db_index=True)
    file_type = models.CharField(
        max_length=4,
        editable=False,
        choices=tuple([(t, t.upper()) for t in TYPES])
    )
    tags = models.ManyToManyField(Tag, related_name="documents")
    created = models.DateTimeField(default=timezone.now, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta(object):
        ordering = ("sender", "title")

    def __str__(self):
        created = self.created.strftime("%Y-%m-%d")
        if self.sender and self.title:
            return "{}: {}, {}".format(created, self.sender, self.title)
        if self.sender or self.title:
            return "{}: {}".format(created, self.sender or self.title)
        return str(created)

    @property
    def source_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "{:07}.{}.gpg".format(self.pk, self.file_type)
        )

    @property
    def source_file(self):
        return open(self.source_path, "rb")

    @property
    def parseable_file_name(self):
        if self.sender and self.title:
            return "{} - {}.{}".format(self.sender, self.title, self.file_types)
        return os.path.basename(self.source_path)
