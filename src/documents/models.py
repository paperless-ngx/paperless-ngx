# coding=utf-8

import logging
import os
import re
import uuid
from collections import OrderedDict

import dateutil.parser
from django.dispatch import receiver
from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.text import slugify
from fuzzywuzzy import fuzz
from collections import defaultdict

from .managers import LogManager

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse


class MatchingModel(models.Model):

    MATCH_ANY = 1
    MATCH_ALL = 2
    MATCH_LITERAL = 3
    MATCH_REGEX = 4
    MATCH_FUZZY = 5
    MATCHING_ALGORITHMS = (
        (MATCH_ANY, "Any"),
        (MATCH_ALL, "All"),
        (MATCH_LITERAL, "Literal"),
        (MATCH_REGEX, "Regular Expression"),
        (MATCH_FUZZY, "Fuzzy Match"),
    )

    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(blank=True, editable=False)

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

        search_kwargs = {}

        # Check that match is not empty
        if self.match.strip() == "":
            return False

        if self.is_insensitive:
            search_kwargs = {"flags": re.IGNORECASE}

        if self.matching_algorithm == self.MATCH_ALL:
            for word in self._split_match():
                search_result = re.search(
                    r"\b{}\b".format(word), text, **search_kwargs)
                if not search_result:
                    return False
            return True

        if self.matching_algorithm == self.MATCH_ANY:
            for word in self._split_match():
                if re.search(r"\b{}\b".format(word), text, **search_kwargs):
                    return True
            return False

        if self.matching_algorithm == self.MATCH_LITERAL:
            return bool(re.search(
                r"\b{}\b".format(self.match), text, **search_kwargs))

        if self.matching_algorithm == self.MATCH_REGEX:
            return bool(re.search(
                re.compile(self.match, **search_kwargs), text))

        if self.matching_algorithm == self.MATCH_FUZZY:
            match = re.sub(r'[^\w\s]', '', self.match)
            text = re.sub(r'[^\w\s]', '', text)
            if self.is_insensitive:
                match = match.lower()
                text = text.lower()

            return True if fuzz.partial_ratio(match, text) >= 90 else False

        raise NotImplementedError("Unsupported matching algorithm")

    def _split_match(self):
        """
        Splits the match to individual keywords, getting rid of unnecessary
        spaces and grouping quoted words together.

        Example:
          '  some random  words "with   quotes  " and   spaces'
            ==>
          ["some", "random", "words", "with+quotes", "and", "spaces"]
        """
        findterms = re.compile(r'"([^"]+)"|(\S+)').findall
        normspace = re.compile(r"\s+").sub
        return [
            normspace(" ", (t[0] or t[1]).strip()).replace(" ", r"\s+")
            for t in findterms(self.match)
        ]

    def save(self, *args, **kwargs):

        self.match = self.match.lower()
        self.slug = slugify(self.name)

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


class Document(models.Model):

    TYPE_PDF = "pdf"
    TYPE_PNG = "png"
    TYPE_JPG = "jpg"
    TYPE_GIF = "gif"
    TYPE_TIF = "tiff"
    TYPE_TXT = "txt"
    TYPE_CSV = "csv"
    TYPE_MD = "md"
    TYPES = (TYPE_PDF, TYPE_PNG, TYPE_JPG, TYPE_GIF, TYPE_TIF,
             TYPE_TXT, TYPE_CSV, TYPE_MD)

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

    content = models.TextField(
        db_index=True,
        blank=True,
        help_text="The raw, text-only data of the document.  This field is "
                  "primarily used for searching."
    )

    file_type = models.CharField(
        max_length=4,
        editable=False,
        choices=tuple([(t, t.upper()) for t in TYPES])
    )

    tags = models.ManyToManyField(
        Tag, related_name="documents", blank=True)

    checksum = models.CharField(
        max_length=32,
        editable=False,
        unique=True,
        help_text="The checksum of the original document (before it was "
                  "encrypted).  We use this to prevent duplicate document "
                  "imports."
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
        max_length=256,
        editable=False,
        default=None,
        null=True,
        help_text="Current filename in storage"
    )

    class Meta:
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
    def source_filename(self):
        if self.filename is None:
            self.filename = self.generate_source_filename()

        return self.filename

    @staticmethod
    def many_to_dictionary(field):
        # Converts ManyToManyField to dictionary by assuming, that field
        # entries contain an _ or - which will be used as a delimiter
        mydictionary = dict()

        for t in field.all():
            # Find delimiter
            delimiter = t.name.find('_')

            if delimiter is -1:
                delimiter = t.name.find('-')

            if delimiter is -1:
                continue

            key = t.name[:delimiter]
            value = t.name[delimiter+1:]

            mydictionary[slugify(key)] = slugify(value)

        return mydictionary

    @staticmethod
    def many_to_list(field):
        # Converts ManyToManyField to list
        mylist = list()

        for t in field.all():
            mylist.append(slugify(t.name))

        return mylist

    @staticmethod
    def fill_list(input_list, length, filler):
        while len(input_list) < length:
            input_list.append(slugify(filler))

        return input_list

    def generate_source_filename(self):
        # Create filename based on configured format
        if settings.PAPERLESS_FILENAME_FORMAT is not None:
            tag = defaultdict(lambda: slugify(None),
                              self.many_to_dictionary(self.tags))
            tags = defaultdict(lambda: slugify(None),
                               enumerate(self.many_to_list(self.tags)))
            path = settings.PAPERLESS_FILENAME_FORMAT.format(
                   correspondent=slugify(self.correspondent),
                   title=slugify(self.title),
                   created=slugify(self.created),
                   added=slugify(self.added),
                   tag=tag,
                   tags=tags)
        else:
            path = ""

        # Always append the primary key to guarantee uniqueness of filename
        if len(path) > 0:
            filename = "%s-%07i.%s" % (path, self.pk, self.file_type)
        else:
            filename = "%07i.%s" % (self.pk, self.file_type)

        # Append .gpg for encrypted files
        if self.storage_type == self.STORAGE_TYPE_GPG:
            filename += ".gpg"

        return filename

    def create_source_directory(self):
        new_filename = self.generate_source_filename()

        # Determine the full "target" path
        dir_new = Document.filename_to_path(os.path.dirname(new_filename))

        # Create new path
        os.makedirs(dir_new, exist_ok=True)

    @property
    def source_path(self):
        return Document.filename_to_path(self.source_filename)

    @staticmethod
    def filename_to_path(filename):
        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "originals",
            filename
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

        file_name = "{:07}.png".format(self.pk)
        if self.storage_type == self.STORAGE_TYPE_GPG:
            file_name += ".gpg"

        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "thumbnails",
            file_name
        )

    @property
    def thumbnail_file(self):
        return open(self.thumbnail_path, "rb")

    @property
    def thumbnail_url(self):
        return reverse("fetch", kwargs={"kind": "thumb", "pk": self.pk})

    def set_filename(self, filename):
        if os.path.isfile(Document.filename_to_path(filename)):
            self.filename = filename


def try_delete_empty_directories(directory):
    # Go up in the directory hierarchy and try to delete all directories
    directory = os.path.normpath(directory)
    root = os.path.normpath(Document.filename_to_path(""))

    while directory != root:
        # Try to delete the current directory
        try:
            os.rmdir(directory)
        except os.error:
            # Directory not empty, no need to go further up
            return

        # Cut off actual directory and go one level up
        directory, _ = os.path.split(directory)
        directory = os.path.normpath(directory)


@receiver(models.signals.m2m_changed, sender=Document.tags.through)
@receiver(models.signals.post_save, sender=Document)
def update_filename(sender, instance, **kwargs):
    # Skip if document has not been saved yet
    if instance.filename is None:
        return

    # Build the new filename
    new_filename = instance.generate_source_filename()

    # If the filename is the same, then nothing needs to be done
    if instance.filename == new_filename:
        return

    # Determine the full "target" path
    path_new = instance.filename_to_path(new_filename)
    dir_new = instance.filename_to_path(os.path.dirname(new_filename))

    # Create new path
    instance.create_source_directory()

    # Determine the full "current" path
    path_current = instance.filename_to_path(instance.filename)

    # Move file
    try:
        os.rename(path_current, path_new)
    except PermissionError:
        # Do not update filename in object
        return

    # Delete empty directory
    old_dir = os.path.dirname(instance.filename)
    old_path = instance.filename_to_path(old_dir)
    try_delete_empty_directories(old_path)

    instance.filename = new_filename

    # Save instance
    # This will not cause a cascade of post_save signals, as next time
    # nothing needs to be renamed
    instance.save()


@receiver(models.signals.post_delete, sender=Document)
def delete_files(sender, instance, **kwargs):
    if instance.filename is None:
        return

    # Remove the document
    old_file = instance.filename_to_path(instance.filename)

    try:
        os.remove(old_file)
    except FileNotFoundError:
        logger = logging.getLogger(__name__)
        logger.warning("Deleted document " + str(instance.id) + " but file " +
                       old_file + " was no longer present")

    # And remove the directory (if applicable)
    old_dir = os.path.dirname(instance.filename)
    old_path = instance.filename_to_path(old_dir)
    try_delete_empty_directories(old_path)


class Log(models.Model):

    LEVELS = (
        (logging.DEBUG, "Debugging"),
        (logging.INFO, "Informational"),
        (logging.WARNING, "Warning"),
        (logging.ERROR, "Error"),
        (logging.CRITICAL, "Critical"),
    )

    group = models.UUIDField(blank=True)
    message = models.TextField()
    level = models.PositiveIntegerField(choices=LEVELS, default=logging.INFO)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    objects = LogManager()

    class Meta:
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

    formats = "pdf|jpe?g|png|gif|tiff?|te?xt|md|csv"
    REGEXES = OrderedDict([
        ("created-correspondent-title-tags", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("created-title-tags", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("created-correspondent-title", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*)"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("created-title", re.compile(
            r"^(?P<created>\d\d\d\d\d\d\d\d(\d\d\d\d\d\d)?Z) - "
            r"(?P<title>.*)"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("correspondent-title-tags", re.compile(
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*) - "
            r"(?P<tags>[a-z0-9\-,]*)"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("correspondent-title", re.compile(
            r"(?P<correspondent>.*) - "
            r"(?P<title>.*)?"
            r"\.(?P<extension>{})$".format(formats),
            flags=re.IGNORECASE
        )),
        ("title", re.compile(
            r"(?P<title>.*)"
            r"\.(?P<extension>{})$".format(formats),
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
        return Correspondent.objects.get_or_create(name=name, defaults={
            "slug": slugify(name)
        })[0]

    @classmethod
    def _get_title(cls, title):
        return title

    @classmethod
    def _get_tags(cls, tags):
        r = []
        for t in tags.split(","):
            r.append(Tag.objects.get_or_create(
                slug=slugify(t),
                defaults={"name": t}
            )[0])
        return tuple(r)

    @classmethod
    def _get_extension(cls, extension):
        r = extension.lower()
        if r == "jpeg":
            return "jpg"
        if r == "tif":
            return "tiff"
        return r

    @classmethod
    def _mangle_property(cls, properties, name):
        if name in properties:
            properties[name] = getattr(cls, "_get_{}".format(name))(
                properties[name]
            )

    @classmethod
    def from_path(cls, path):
        """
        We use a crude naming convention to make handling the correspondent,
        title, and tags easier:
          "<date> - <correspondent> - <title> - <tags>.<suffix>"
          "<correspondent> - <title> - <tags>.<suffix>"
          "<correspondent> - <title>.<suffix>"
          "<title>.<suffix>"
        """

        filename = os.path.basename(path)

        # Mutate filename in-place before parsing its components
        # by applying at most one of the configured transformations.
        for (pattern, repl) in settings.FILENAME_PARSE_TRANSFORMS:
            (filename, count) = pattern.subn(repl, filename)
            if count:
                break

        # Parse filename components.
        for regex in cls.REGEXES.values():
            m = regex.match(filename)
            if m:
                properties = m.groupdict()
                cls._mangle_property(properties, "created")
                cls._mangle_property(properties, "correspondent")
                cls._mangle_property(properties, "title")
                cls._mangle_property(properties, "tags")
                cls._mangle_property(properties, "extension")
                return cls(**properties)
