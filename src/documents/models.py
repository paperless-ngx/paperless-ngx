# coding=utf-8
import datetime
import logging
import os
import re
from collections import OrderedDict

import pathvalidate

import dateutil.parser
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from documents.file_handling import archive_name_from_filename
from documents.parsers import get_default_file_extension


class MatchingModel(models.Model):

    MATCH_ANY = 1
    MATCH_ALL = 2
    MATCH_LITERAL = 3
    MATCH_REGEX = 4
    MATCH_FUZZY = 5
    MATCH_AUTO = 6

    MATCHING_ALGORITHMS = (
        (MATCH_ANY, "Any"),
        (MATCH_ALL, "All"),
        (MATCH_LITERAL, "Literal"),
        (MATCH_REGEX, "Regular Expression"),
        (MATCH_FUZZY, "Fuzzy Match"),
        (MATCH_AUTO, "Automatic Classification"),
    )

    name = models.CharField(max_length=128, unique=True)

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
            "uses a regex to match the PDF.  (If you don't know what a regex "
            "is, you probably don't want this option.)  Finally, a \"fuzzy "
            "match\" looks for words or phrases that are mostly—but not "
            "exactly—the same, which can be useful for matching against "
            "documents containg imperfections that foil accurate OCR."
        )
    )

    is_insensitive = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):

        self.match = self.match.lower()

        models.Model.save(self, *args, **kwargs)


class Correspondent(MatchingModel):

    # This regex is probably more restrictive than it needs to be, but it's
    # better safe than sorry.
    SAFE_REGEX = re.compile(r"^[\w\- ,.']+$")

    class Meta:
        ordering = ("name",)


class Tag(MatchingModel):

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

    colour = models.PositiveIntegerField(choices=COLOURS, default=1)

    is_inbox_tag = models.BooleanField(
        default=False,
        help_text="Marks this tag as an inbox tag: All newly consumed "
                  "documents will be tagged with inbox tags."
    )


class DocumentType(MatchingModel):

    pass


class Document(models.Model):

    STORAGE_TYPE_UNENCRYPTED = "unencrypted"
    STORAGE_TYPE_GPG = "gpg"
    STORAGE_TYPES = (
        (STORAGE_TYPE_UNENCRYPTED, "Unencrypted"),
        (STORAGE_TYPE_GPG, "Encrypted with GNU Privacy Guard")
    )

    correspondent = models.ForeignKey(
        Correspondent,
        blank=True,
        null=True,
        related_name="documents",
        on_delete=models.SET_NULL
    )

    title = models.CharField(max_length=128, blank=True, db_index=True)

    document_type = models.ForeignKey(
        DocumentType,
        blank=True,
        null=True,
        related_name="documents",
        on_delete=models.SET_NULL
    )

    content = models.TextField(
        blank=True,
        help_text="The raw, text-only data of the document. This field is "
                  "primarily used for searching."
    )

    mime_type = models.CharField(
        max_length=256,
        editable=False
    )

    tags = models.ManyToManyField(
        Tag, related_name="documents", blank=True)

    checksum = models.CharField(
        max_length=32,
        editable=False,
        unique=True,
        help_text="The checksum of the original document."
    )

    archive_checksum = models.CharField(
        max_length=32,
        editable=False,
        blank=True,
        null=True,
        help_text="The checksum of the archived document."
    )

    created = models.DateTimeField(
        default=timezone.now, db_index=True)

    modified = models.DateTimeField(
        auto_now=True, editable=False, db_index=True)

    storage_type = models.CharField(
        max_length=11,
        choices=STORAGE_TYPES,
        default=STORAGE_TYPE_UNENCRYPTED,
        editable=False
    )

    added = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True)

    filename = models.FilePathField(
        max_length=1024,
        editable=False,
        default=None,
        null=True,
        help_text="Current filename in storage"
    )

    archive_serial_number = models.IntegerField(
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="The position of this document in your physical document "
                  "archive."
    )

    class Meta:
        ordering = ("correspondent", "title")

    def __str__(self):
        created = datetime.date.isoformat(self.created)
        if self.correspondent and self.title:
            return f"{created} {self.correspondent} {self.title}"
        else:
            return f"{created} {self.title}"

    @property
    def source_path(self):
        if self.filename:
            fname = str(self.filename)
        else:
            fname = "{:07}{}".format(self.pk, self.file_type)
            if self.storage_type == self.STORAGE_TYPE_GPG:
                fname += ".gpg"  # pragma: no cover

        return os.path.join(
            settings.ORIGINALS_DIR,
            fname
        )

    @property
    def source_file(self):
        return open(self.source_path, "rb")

    @property
    def archive_path(self):
        if self.filename:
            fname = archive_name_from_filename(self.filename)
        else:
            fname = "{:07}.pdf".format(self.pk)

        return os.path.join(
            settings.ARCHIVE_DIR,
            fname
        )

    @property
    def archive_file(self):
        return open(self.archive_path, "rb")

    def get_public_filename(self, archive=False, counter=0, suffix=None):
        result = str(self)

        if counter:
            result += f"_{counter:02}"

        if suffix:
            result += suffix

        if archive:
            result += ".pdf"
        else:
            result += self.file_type

        return pathvalidate.sanitize_filename(result, replacement_text="-")

    @property
    def file_type(self):
        return get_default_file_extension(self.mime_type)

    @property
    def thumbnail_path(self):
        file_name = "{:07}.png".format(self.pk)
        if self.storage_type == self.STORAGE_TYPE_GPG:
            file_name += ".gpg"

        return os.path.join(
            settings.THUMBNAIL_DIR,
            file_name
        )

    @property
    def thumbnail_file(self):
        return open(self.thumbnail_path, "rb")


class Log(models.Model):

    LEVELS = (
        (logging.DEBUG, "Debugging"),
        (logging.INFO, "Informational"),
        (logging.WARNING, "Warning"),
        (logging.ERROR, "Error"),
        (logging.CRITICAL, "Critical"),
    )

    group = models.UUIDField(blank=True, null=True)
    message = models.TextField()
    level = models.PositiveIntegerField(choices=LEVELS, default=logging.INFO)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return self.message


class SavedView(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)

    show_on_dashboard = models.BooleanField()
    show_in_sidebar = models.BooleanField()

    sort_field = models.CharField(max_length=128)
    sort_reverse = models.BooleanField(default=False)


class SavedViewFilterRule(models.Model):
    RULE_TYPES = [
        (0, "Title contains"),
        (1, "Content contains"),
        (2, "ASN is"),
        (3, "Correspondent is"),
        (4, "Document type is"),
        (5, "Is in inbox"),
        (6, "Has tag"),
        (7, "Has any tag"),
        (8, "Created before"),
        (9, "Created after"),
        (10, "Created year is"),
        (11, "Created month is"),
        (12, "Created day is"),
        (13, "Added before"),
        (14, "Added after"),
        (15, "Modified before"),
        (16, "Modified after"),
        (17, "Does not have tag"),
    ]

    saved_view = models.ForeignKey(
        SavedView,
        on_delete=models.CASCADE,
        related_name="filter_rules"
    )

    rule_type = models.PositiveIntegerField(choices=RULE_TYPES)

    value = models.CharField(max_length=128)


# TODO: why is this in the models file?
class FileInfo:

    # This epic regex *almost* worked for our needs, so I'm keeping it here for
    # posterity, in the hopes that we might find a way to make it work one day.
    ALMOST_REGEX = re.compile(
        r"^((?P<date>\d\d\d\d\d\d\d\d\d\d\d\d\d\dZ){separator})?"
        r"((?P<correspondent>{non_separated_word}+){separator})??"
        r"(?P<title>{non_separated_word}+)"
        r"({separator}(?P<tags>[a-z,0-9-]+))?"
        r"\.(?P<extension>[a-zA-Z.-]+)$".format(
            separator=r"\s+-\s+",
            non_separated_word=r"([\w,. ]|([^\s]-))"
        )
    )
    REGEXES = OrderedDict([
        ("created-correspondent-title-tags", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)$",
            flags=re.IGNORECASE
        )),
        ("created-title-tags", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)$",
            flags=re.IGNORECASE
        )),
        ("created-correspondent-title", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*)$",
            flags=re.IGNORECASE
        )),
        ("created-title", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<title>.*)$",
            flags=re.IGNORECASE
        )),
        ("correspondent-title-tags", re.compile(
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)$",
            flags=re.IGNORECASE
        )),
        ("correspondent-title", re.compile(
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*)?$",
            flags=re.IGNORECASE
        )),
        ("title", re.compile(
            r"(?P<title>.*)$",
            flags=re.IGNORECASE
        ))
    ])

    def __init__(self, created=None, correspondent=None, title=None, tags=(),
                 extension=None):

        self.created = created
        self.title = title
        self.extension = extension
        self.correspondent = correspondent
        self.tags = tags

    @classmethod
    def _get_created(cls, created):
        try:
            return dateutil.parser.parse("{:0<14}Z".format(created[:-1]))
        except ValueError:
            return None

    @classmethod
    def _get_correspondent(cls, name):
        if not name:
            return None
        return Correspondent.objects.get_or_create(name=name)[0]

    @classmethod
    def _get_title(cls, title):
        return title

    @classmethod
    def _get_tags(cls, tags):
        r = []
        for t in tags.split(","):
            r.append(Tag.objects.get_or_create(name=t)[0])
        return tuple(r)

    @classmethod
    def _mangle_property(cls, properties, name):
        if name in properties:
            properties[name] = getattr(cls, "_get_{}".format(name))(
                properties[name]
            )

    @classmethod
    def from_filename(cls, filename):
        """
        We use a crude naming convention to make handling the correspondent,
        title, and tags easier:
          "<date> - <correspondent> - <title> - <tags>"
          "<correspondent> - <title> - <tags>"
          "<correspondent> - <title>"
          "<title>"
        """

        # Mutate filename in-place before parsing its components
        # by applying at most one of the configured transformations.
        for (pattern, repl) in settings.FILENAME_PARSE_TRANSFORMS:
            (filename, count) = pattern.subn(repl, filename)
            if count:
                break

        # do this after the transforms so that the transforms can do whatever
        # with the file extension.
        filename_no_ext = os.path.splitext(filename)[0]

        if filename_no_ext == filename and filename.startswith("."):
            # This is a very special case where there is no text before the
            # file type.
            # TODO: this should be handled better. The ext is not removed
            #  because usually, files like '.pdf' are just hidden files
            #  with the name pdf, but in our case, its more likely that
            #  there's just no name to begin with.
            filename = ""
            # This isn't too bad either, since we'll just not match anything
            # and return an empty title. TODO: actually, this is kinda bad.
        else:
            filename = filename_no_ext

        # Parse filename components.
        for regex in cls.REGEXES.values():
            m = regex.match(filename)
            if m:
                properties = m.groupdict()
                cls._mangle_property(properties, "created")
                cls._mangle_property(properties, "correspondent")
                cls._mangle_property(properties, "title")
                cls._mangle_property(properties, "tags")
                return cls(**properties)
