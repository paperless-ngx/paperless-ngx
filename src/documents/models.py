import logging
import os
import re
import uuid

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone

from .managers import LogManager


class FileInfo(object):
    def __init__(self, title, suffix,
                 correspondent=None, tags=None,
                 file_mtime=None, path=None):
        self._title = title
        self._suffix = suffix
        self._correspondent = correspondent
        self._tags = tags
        self._file_mtime = file_mtime
        self._path = path

    @classmethod
    def from_path(cls, path):
        pass

    @classmethod
    def from_document(cls, document):
        pass

    def filename(self):
        pass

    def kwargs_for_document_create(self):
        pass

    def add_tags(self, tags):
        self._tags = set(tags).union(self._tags)


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


class Correspondent(SluggedModel):

    # This regex is probably more restrictive than it needs to be, but it's
    # better safe than sorry.
    SAFE_REGEX = re.compile(r"^[\w\- ,.']+$")

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
        default=MATCH_ANY,
        help_text=(
            "Which algorithm you want to use when matching text to the OCR'd "
            "PDF.  Here, \"any\" looks for any occurrence of any word "
            "provided in the PDF, while \"all\" requires that every word "
            "provided appear in the PDF, albeit not in the order provided.  A "
            "\"literal\" match means that the text you enter must appear in "
            "the PDF exactly as you've entered it, and \"regular expression\" "
            "uses a regex to match the PDF.  If you don't know what a regex "
            "is, you probably don't want this option."
        )
    )

    @property
    def conditions(self):
        return "{}: \"{}\" ({})".format(
            self.name, self.match, self.get_matching_algorithm_display())

    @classmethod
    def match_all(cls, text, tags=None):

        if tags is None:
            tags = cls.objects.all()

        text = text.lower()
        for tag in tags:
            if tag.matches(text):
                yield tag

    def matches(self, text):

        # Check that match is not empty
        if self.match.strip() == "":
            return False

        if self.matching_algorithm == self.MATCH_ALL:
            for word in self.match.split(" "):
                if not re.search(r"\b{}\b".format(word), text):
                    return False
            return True

        if self.matching_algorithm == self.MATCH_ANY:
            for word in self.match.split(" "):
                if re.search(r"\b{}\b".format(word), text):
                    return True
            return False

        if self.matching_algorithm == self.MATCH_LITERAL:
            return bool(re.search(r"\b{}\b".format(self.match), text))

        if self.matching_algorithm == self.MATCH_REGEX:
            return bool(re.search(re.compile(self.match), text))

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

    correspondent = models.ForeignKey(
        Correspondent, blank=True, null=True, related_name="documents")
    title = models.CharField(max_length=128, blank=True, db_index=True)
    content = models.TextField(db_index=True)
    file_type = models.CharField(
        max_length=4,
        editable=False,
        choices=tuple([(t, t.upper()) for t in TYPES])
    )
    tags = models.ManyToManyField(
        Tag, related_name="documents", blank=True)
    created = models.DateTimeField(default=timezone.now, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta(object):
        ordering = ("correspondent", "title")

    def __str__(self):
        created = self.created.strftime("%Y%m%d%H%M%S")
        if self.correspondent and self.title:
            return "{}: {} - {}".format(
                created, self.correspondent, self.title)
        if self.correspondent or self.title:
            return "{}: {}".format(created, self.correspondent or self.title)
        return str(created)

    @property
    def source_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "originals",
            "{:07}.{}.gpg".format(self.pk, self.file_type)
        )

    @property
    def source_file(self):
        return open(self.source_path, "rb")

    @property
    def file_name(self):
        return slugify(str(self)) + "." + self.file_type

    @property
    def download_url(self):
        return reverse("fetch", kwargs={"kind": "doc", "pk": self.pk})

    @property
    def thumbnail_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "thumbnails",
            "{:07}.png.gpg".format(self.pk)
        )

    @property
    def thumbnail_file(self):
        return open(self.thumbnail_path, "rb")

    @property
    def thumbnail_url(self):
        return reverse("fetch", kwargs={"kind": "thumb", "pk": self.pk})


class Log(models.Model):

    LEVELS = (
        (logging.DEBUG, "Debugging"),
        (logging.INFO, "Informational"),
        (logging.WARNING, "Warning"),
        (logging.ERROR, "Error"),
        (logging.CRITICAL, "Critical"),
    )

    COMPONENT_CONSUMER = 1
    COMPONENT_MAIL = 2
    COMPONENTS = (
        (COMPONENT_CONSUMER, "Consumer"),
        (COMPONENT_MAIL, "Mail Fetcher")
    )

    group = models.UUIDField(blank=True)
    message = models.TextField()
    level = models.PositiveIntegerField(choices=LEVELS, default=logging.INFO)
    component = models.PositiveIntegerField(choices=COMPONENTS)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    objects = LogManager()

    class Meta(object):
        ordering = ("-modified",)

    def __str__(self):
        return self.message

    def save(self, *args, **kwargs):
        """
        To allow for the case where we don't want to group the message, we
        shouldn't force the caller to specify a one-time group value.  However,
        allowing group=None means that the manager can't differentiate the
        different un-grouped messages, so instead we set a random one here.
        """

        if not self.group:
            self.group = uuid.uuid4()

        models.Model.save(self, *args, **kwargs)
