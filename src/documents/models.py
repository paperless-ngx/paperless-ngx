import datetime
import logging
import os
import re
from collections import OrderedDict
from typing import Optional

import dateutil.parser
import pathvalidate
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_q.tasks import Task
from documents.parsers import get_default_file_extension


class MatchingModel(models.Model):

    MATCH_ANY = 1
    MATCH_ALL = 2
    MATCH_LITERAL = 3
    MATCH_REGEX = 4
    MATCH_FUZZY = 5
    MATCH_AUTO = 6

    MATCHING_ALGORITHMS = (
        (MATCH_ANY, _("Any word")),
        (MATCH_ALL, _("All words")),
        (MATCH_LITERAL, _("Exact match")),
        (MATCH_REGEX, _("Regular expression")),
        (MATCH_FUZZY, _("Fuzzy word")),
        (MATCH_AUTO, _("Automatic")),
    )

    name = models.CharField(_("name"), max_length=128, unique=True)

    match = models.CharField(_("match"), max_length=256, blank=True)

    matching_algorithm = models.PositiveIntegerField(
        _("matching algorithm"),
        choices=MATCHING_ALGORITHMS,
        default=MATCH_ANY,
    )

    is_insensitive = models.BooleanField(_("is insensitive"), default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self):
        return self.name


class Correspondent(MatchingModel):
    class Meta:
        ordering = ("name",)
        verbose_name = _("correspondent")
        verbose_name_plural = _("correspondents")


class Tag(MatchingModel):

    color = models.CharField(_("color"), max_length=7, default="#a6cee3")

    is_inbox_tag = models.BooleanField(
        _("is inbox tag"),
        default=False,
        help_text=_(
            "Marks this tag as an inbox tag: All newly consumed "
            "documents will be tagged with inbox tags.",
        ),
    )

    class Meta:
        verbose_name = _("tag")
        verbose_name_plural = _("tags")


class DocumentType(MatchingModel):
    class Meta:
        verbose_name = _("document type")
        verbose_name_plural = _("document types")


class StoragePath(MatchingModel):
    path = models.CharField(
        _("path"),
        max_length=512,
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("storage path")
        verbose_name_plural = _("storage paths")


class Document(models.Model):

    STORAGE_TYPE_UNENCRYPTED = "unencrypted"
    STORAGE_TYPE_GPG = "gpg"
    STORAGE_TYPES = (
        (STORAGE_TYPE_UNENCRYPTED, _("Unencrypted")),
        (STORAGE_TYPE_GPG, _("Encrypted with GNU Privacy Guard")),
    )

    correspondent = models.ForeignKey(
        Correspondent,
        blank=True,
        null=True,
        related_name="documents",
        on_delete=models.SET_NULL,
        verbose_name=_("correspondent"),
    )

    storage_path = models.ForeignKey(
        StoragePath,
        blank=True,
        null=True,
        related_name="documents",
        on_delete=models.SET_NULL,
        verbose_name=_("storage path"),
    )

    title = models.CharField(_("title"), max_length=128, blank=True, db_index=True)

    document_type = models.ForeignKey(
        DocumentType,
        blank=True,
        null=True,
        related_name="documents",
        on_delete=models.SET_NULL,
        verbose_name=_("document type"),
    )

    content = models.TextField(
        _("content"),
        blank=True,
        help_text=_(
            "The raw, text-only data of the document. This field is "
            "primarily used for searching.",
        ),
    )

    mime_type = models.CharField(_("mime type"), max_length=256, editable=False)

    tags = models.ManyToManyField(
        Tag,
        related_name="documents",
        blank=True,
        verbose_name=_("tags"),
    )

    checksum = models.CharField(
        _("checksum"),
        max_length=32,
        editable=False,
        unique=True,
        help_text=_("The checksum of the original document."),
    )

    archive_checksum = models.CharField(
        _("archive checksum"),
        max_length=32,
        editable=False,
        blank=True,
        null=True,
        help_text=_("The checksum of the archived document."),
    )

    created = models.DateTimeField(_("created"), default=timezone.now, db_index=True)

    modified = models.DateTimeField(
        _("modified"),
        auto_now=True,
        editable=False,
        db_index=True,
    )

    storage_type = models.CharField(
        _("storage type"),
        max_length=11,
        choices=STORAGE_TYPES,
        default=STORAGE_TYPE_UNENCRYPTED,
        editable=False,
    )

    added = models.DateTimeField(
        _("added"),
        default=timezone.now,
        editable=False,
        db_index=True,
    )

    filename = models.FilePathField(
        _("filename"),
        max_length=1024,
        editable=False,
        default=None,
        unique=True,
        null=True,
        help_text=_("Current filename in storage"),
    )

    archive_filename = models.FilePathField(
        _("archive filename"),
        max_length=1024,
        editable=False,
        default=None,
        unique=True,
        null=True,
        help_text=_("Current archive filename in storage"),
    )

    archive_serial_number = models.IntegerField(
        _("archive serial number"),
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text=_(
            "The position of this document in your physical document " "archive.",
        ),
    )

    class Meta:
        ordering = ("-created",)
        verbose_name = _("document")
        verbose_name_plural = _("documents")

    def __str__(self) -> str:

        # Convert UTC database time to local time
        created = datetime.date.isoformat(timezone.localdate(self.created))

        res = f"{created}"

        if self.correspondent:
            res += f" {self.correspondent}"
        if self.title:
            res += f" {self.title}"
        return res

    @property
    def source_path(self) -> str:
        if self.filename:
            fname = str(self.filename)
        else:
            fname = f"{self.pk:07}{self.file_type}"
            if self.storage_type == self.STORAGE_TYPE_GPG:
                fname += ".gpg"  # pragma: no cover

        return os.path.join(settings.ORIGINALS_DIR, fname)

    @property
    def source_file(self):
        return open(self.source_path, "rb")

    @property
    def has_archive_version(self) -> bool:
        return self.archive_filename is not None

    @property
    def archive_path(self) -> Optional[str]:
        if self.has_archive_version:
            return os.path.join(settings.ARCHIVE_DIR, str(self.archive_filename))
        else:
            return None

    @property
    def archive_file(self):
        return open(self.archive_path, "rb")

    def get_public_filename(self, archive=False, counter=0, suffix=None) -> str:
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
    def thumbnail_path(self) -> str:
        webp_file_name = f"{self.pk:07}.webp"
        if self.storage_type == self.STORAGE_TYPE_GPG:
            webp_file_name += ".gpg"

        webp_file_path = os.path.join(settings.THUMBNAIL_DIR, webp_file_name)

        return os.path.normpath(webp_file_path)

    @property
    def thumbnail_file(self):
        return open(self.thumbnail_path, "rb")

    @property
    def created_date(self):
        return timezone.localdate(self.created)


class Log(models.Model):

    LEVELS = (
        (logging.DEBUG, _("debug")),
        (logging.INFO, _("information")),
        (logging.WARNING, _("warning")),
        (logging.ERROR, _("error")),
        (logging.CRITICAL, _("critical")),
    )

    group = models.UUIDField(_("group"), blank=True, null=True)

    message = models.TextField(_("message"))

    level = models.PositiveIntegerField(
        _("level"),
        choices=LEVELS,
        default=logging.INFO,
    )

    created = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        ordering = ("-created",)
        verbose_name = _("log")
        verbose_name_plural = _("logs")

    def __str__(self):
        return self.message


class SavedView(models.Model):
    class Meta:

        ordering = ("name",)
        verbose_name = _("saved view")
        verbose_name_plural = _("saved views")

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    name = models.CharField(_("name"), max_length=128)

    show_on_dashboard = models.BooleanField(
        _("show on dashboard"),
    )
    show_in_sidebar = models.BooleanField(
        _("show in sidebar"),
    )

    sort_field = models.CharField(
        _("sort field"),
        max_length=128,
        null=True,
        blank=True,
    )
    sort_reverse = models.BooleanField(_("sort reverse"), default=False)


class SavedViewFilterRule(models.Model):
    RULE_TYPES = [
        (0, _("title contains")),
        (1, _("content contains")),
        (2, _("ASN is")),
        (3, _("correspondent is")),
        (4, _("document type is")),
        (5, _("is in inbox")),
        (6, _("has tag")),
        (7, _("has any tag")),
        (8, _("created before")),
        (9, _("created after")),
        (10, _("created year is")),
        (11, _("created month is")),
        (12, _("created day is")),
        (13, _("added before")),
        (14, _("added after")),
        (15, _("modified before")),
        (16, _("modified after")),
        (17, _("does not have tag")),
        (18, _("does not have ASN")),
        (19, _("title or content contains")),
        (20, _("fulltext query")),
        (21, _("more like this")),
        (22, _("has tags in")),
    ]

    saved_view = models.ForeignKey(
        SavedView,
        on_delete=models.CASCADE,
        related_name="filter_rules",
        verbose_name=_("saved view"),
    )

    rule_type = models.PositiveIntegerField(_("rule type"), choices=RULE_TYPES)

    value = models.CharField(_("value"), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("filter rule")
        verbose_name_plural = _("filter rules")


# TODO: why is this in the models file?
# TODO: how about, what is this and where is it documented?
# It appears to parsing JSON from an environment variable to get a title and date from
# the filename, if possible, as a higher priority than either document filename or
# content parsing
class FileInfo:

    REGEXES = OrderedDict(
        [
            (
                "created-title",
                re.compile(
                    r"^(?P<created>\d{8}(\d{6})?Z) - " r"(?P<title>.*)$",
                    flags=re.IGNORECASE,
                ),
            ),
            ("title", re.compile(r"(?P<title>.*)$", flags=re.IGNORECASE)),
        ],
    )

    def __init__(
        self,
        created=None,
        correspondent=None,
        title=None,
        tags=(),
        extension=None,
    ):

        self.created = created
        self.title = title
        self.extension = extension
        self.correspondent = correspondent
        self.tags = tags

    @classmethod
    def _get_created(cls, created):
        try:
            return dateutil.parser.parse(f"{created[:-1]:0<14}Z")
        except ValueError:
            return None

    @classmethod
    def _get_title(cls, title):
        return title

    @classmethod
    def _mangle_property(cls, properties, name):
        if name in properties:
            properties[name] = getattr(cls, f"_get_{name}")(properties[name])

    @classmethod
    def from_filename(cls, filename) -> "FileInfo":
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
                cls._mangle_property(properties, "title")
                return cls(**properties)


# Extending User Model Using a One-To-One Link
class UiSettings(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="ui_settings",
    )
    settings = models.JSONField(null=True)

    def __str__(self):
        return self.user.username


class PaperlessTask(models.Model):

    task_id = models.CharField(max_length=128)
    name = models.CharField(max_length=256)
    created = models.DateTimeField(_("created"), auto_now=True)
    started = models.DateTimeField(_("started"), null=True)
    attempted_task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name="attempted_task",
        null=True,
        blank=True,
    )
    acknowledged = models.BooleanField(default=False)
