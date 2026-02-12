import datetime
from pathlib import Path
from typing import Final

import pathvalidate
from celery import states
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField
from treenode.models import TreeNodeModel

if settings.AUDIT_LOG_ENABLED:
    from auditlog.registry import auditlog

from django.db.models import Case
from django.db.models import PositiveIntegerField
from django.db.models.functions import Cast
from django.db.models.functions import Length
from django.db.models.functions import Substr
from django_softdelete.models import SoftDeleteModel

from documents.data_models import DocumentSource
from documents.parsers import get_default_file_extension


class ModelWithOwner(models.Model):
    owner = models.ForeignKey(
        User,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name=_("owner"),
    )

    class Meta:
        abstract = True


class MatchingModel(ModelWithOwner):
    MATCH_NONE = 0
    MATCH_ANY = 1
    MATCH_ALL = 2
    MATCH_LITERAL = 3
    MATCH_REGEX = 4
    MATCH_FUZZY = 5
    MATCH_AUTO = 6

    MATCHING_ALGORITHMS = (
        (MATCH_NONE, _("None")),
        (MATCH_ANY, _("Any word")),
        (MATCH_ALL, _("All words")),
        (MATCH_LITERAL, _("Exact match")),
        (MATCH_REGEX, _("Regular expression")),
        (MATCH_FUZZY, _("Fuzzy word")),
        (MATCH_AUTO, _("Automatic")),
    )

    name = models.CharField(_("name"), max_length=128)

    match = models.CharField(_("match"), max_length=256, blank=True)

    matching_algorithm = models.PositiveSmallIntegerField(
        _("matching algorithm"),
        choices=MATCHING_ALGORITHMS,
        default=MATCH_ANY,
    )

    is_insensitive = models.BooleanField(_("is insensitive"), default=True)

    class Meta:
        abstract = True
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["name", "owner"],
                name="%(app_label)s_%(class)s_unique_name_owner",
            ),
            models.UniqueConstraint(
                name="%(app_label)s_%(class)s_name_uniq",
                fields=["name"],
                condition=models.Q(owner__isnull=True),
            ),
        ]

    def __str__(self):
        return self.name


class Correspondent(MatchingModel):
    class Meta(MatchingModel.Meta):
        verbose_name = _("correspondent")
        verbose_name_plural = _("correspondents")


class Tag(MatchingModel, TreeNodeModel):
    color = models.CharField(_("color"), max_length=7, default="#a6cee3")
    # Maximum allowed nesting depth for tags (root = 1, max depth = 5)
    MAX_NESTING_DEPTH: Final[int] = 5

    is_inbox_tag = models.BooleanField(
        _("is inbox tag"),
        default=False,
        help_text=_(
            "Marks this tag as an inbox tag: All newly consumed "
            "documents will be tagged with inbox tags.",
        ),
    )

    class Meta(MatchingModel.Meta, TreeNodeModel.Meta):
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def clean(self) -> None:
        # Prevent self-parenting and assigning a descendant as parent
        parent = self.get_parent()
        if parent == self:
            raise ValidationError({"parent": _("Cannot set itself as parent.")})
        if parent and self.pk is not None and self.is_ancestor_of(parent):
            raise ValidationError({"parent": _("Cannot set parent to a descendant.")})

        # Enforce maximum nesting depth
        new_parent_depth = 0
        if parent:
            new_parent_depth = parent.get_ancestors_count() + 1

        height = 0 if self.pk is None else self.get_depth()
        deepest_new_depth = (new_parent_depth + 1) + height
        if deepest_new_depth > self.MAX_NESTING_DEPTH:
            raise ValidationError({"parent": _("Maximum nesting depth exceeded.")})

        return super().clean()


class DocumentType(MatchingModel):
    class Meta(MatchingModel.Meta):
        verbose_name = _("document type")
        verbose_name_plural = _("document types")


class StoragePath(MatchingModel):
    path = models.TextField(
        _("path"),
    )

    class Meta(MatchingModel.Meta):
        verbose_name = _("storage path")
        verbose_name_plural = _("storage paths")


class Document(SoftDeleteModel, ModelWithOwner):
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

    content_length = models.GeneratedField(
        expression=Length("content"),
        output_field=PositiveIntegerField(default=0),
        db_persist=True,
        null=False,
        serialize=False,
        help_text="Length of the content field in characters. Automatically maintained by the database for faster statistics computation.",
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

    page_count = models.PositiveIntegerField(
        _("page count"),
        blank=False,
        null=True,
        unique=False,
        db_index=False,
        validators=[MinValueValidator(1)],
        help_text=_(
            "The number of pages of the document.",
        ),
    )

    created = models.DateField(
        _("created"),
        default=datetime.date.today,
        db_index=True,
    )

    modified = models.DateTimeField(
        _("modified"),
        auto_now=True,
        editable=False,
        db_index=True,
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

    original_filename = models.CharField(
        _("original filename"),
        max_length=1024,
        editable=False,
        default=None,
        unique=False,
        null=True,
        help_text=_("The original name of the file when it was uploaded"),
    )

    ARCHIVE_SERIAL_NUMBER_MIN: Final[int] = 0
    ARCHIVE_SERIAL_NUMBER_MAX: Final[int] = 0xFF_FF_FF_FF

    archive_serial_number = models.PositiveIntegerField(
        _("archive serial number"),
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        validators=[
            MaxValueValidator(ARCHIVE_SERIAL_NUMBER_MAX),
            MinValueValidator(ARCHIVE_SERIAL_NUMBER_MIN),
        ],
        help_text=_(
            "The position of this document in your physical document archive.",
        ),
    )

    class Meta:
        ordering = ("-created",)
        verbose_name = _("document")
        verbose_name_plural = _("documents")

    def __str__(self) -> str:
        created = self.created.isoformat()

        res = f"{created}"

        if self.correspondent:
            res += f" {self.correspondent}"
        if self.title:
            res += f" {self.title}"
        return res

    @property
    def suggestion_content(self):
        """
        Returns the document text used to generate suggestions.

        If the document content length exceeds a specified limit,
        the text is cropped to include the start and end segments.
        Otherwise, the full content is returned.

        This improves processing speed for large documents while keeping
        enough context for accurate suggestions.
        """
        if not self.content or len(self.content) <= 1200000:
            return self.content
        else:
            # Use 80% from the start and 20% from the end
            # to preserve both opening and closing context.
            head_len = 800000
            tail_len = 200000

            return " ".join((self.content[:head_len], self.content[-tail_len:]))

    @property
    def source_path(self) -> Path:
        fname = str(self.filename) if self.filename else f"{self.pk:07}{self.file_type}"

        return (settings.ORIGINALS_DIR / Path(fname)).resolve()

    @property
    def source_file(self):
        return Path(self.source_path).open("rb")

    @property
    def has_archive_version(self) -> bool:
        return self.archive_filename is not None

    @property
    def archive_path(self) -> Path | None:
        if self.has_archive_version:
            return (settings.ARCHIVE_DIR / Path(str(self.archive_filename))).resolve()
        else:
            return None

    @property
    def archive_file(self):
        return Path(self.archive_path).open("rb")

    def get_public_filename(self, *, archive=False, counter=0, suffix=None) -> str:
        """
        Returns a sanitized filename for the document, not including any paths.
        """
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
    def thumbnail_path(self) -> Path:
        webp_file_name = f"{self.pk:07}.webp"

        webp_file_path = settings.THUMBNAIL_DIR / Path(webp_file_name)

        return webp_file_path.resolve()

    @property
    def thumbnail_file(self):
        return Path(self.thumbnail_path).open("rb")

    @property
    def created_date(self):
        return self.created

    def add_nested_tags(self, tags) -> None:
        tag_ids = set()
        for tag in tags:
            tag_ids.add(tag.id)
            tag_ids.update(tag.get_ancestors_pks())

        tags_to_add = self.tags.model.objects.filter(id__in=tag_ids)
        self.tags.add(*tags_to_add)


class SavedView(ModelWithOwner):
    class DisplayMode(models.TextChoices):
        TABLE = ("table", _("Table"))
        SMALL_CARDS = ("smallCards", _("Small Cards"))
        LARGE_CARDS = ("largeCards", _("Large Cards"))

    class DisplayFields(models.TextChoices):
        TITLE = ("title", _("Title"))
        CREATED = ("created", _("Created"))
        ADDED = ("added", _("Added"))
        TAGS = ("tag"), _("Tags")
        CORRESPONDENT = ("correspondent", _("Correspondent"))
        DOCUMENT_TYPE = ("documenttype", _("Document Type"))
        STORAGE_PATH = ("storagepath", _("Storage Path"))
        NOTES = ("note", _("Note"))
        OWNER = ("owner", _("Owner"))
        SHARED = ("shared", _("Shared"))
        ASN = ("asn", _("ASN"))
        PAGE_COUNT = ("pagecount", _("Pages"))
        CUSTOM_FIELD = ("custom_field_%d", ("Custom Field"))

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

    page_size = models.PositiveIntegerField(
        _("View page size"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    display_mode = models.CharField(
        max_length=128,
        verbose_name=_("View display mode"),
        choices=DisplayMode.choices,
        null=True,
        blank=True,
    )

    display_fields = models.JSONField(
        verbose_name=_("Document display fields"),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("saved view")
        verbose_name_plural = _("saved views")

    def __str__(self):
        return f"SavedView {self.name}"


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
        (23, _("ASN greater than")),
        (24, _("ASN less than")),
        (25, _("storage path is")),
        (26, _("has correspondent in")),
        (27, _("does not have correspondent in")),
        (28, _("has document type in")),
        (29, _("does not have document type in")),
        (30, _("has storage path in")),
        (31, _("does not have storage path in")),
        (32, _("owner is")),
        (33, _("has owner in")),
        (34, _("does not have owner")),
        (35, _("does not have owner in")),
        (36, _("has custom field value")),
        (37, _("is shared by me")),
        (38, _("has custom fields")),
        (39, _("has custom field in")),
        (40, _("does not have custom field in")),
        (41, _("does not have custom field")),
        (42, _("custom fields query")),
        (43, _("created to")),
        (44, _("created from")),
        (45, _("added to")),
        (46, _("added from")),
        (47, _("mime type is")),
    ]

    saved_view = models.ForeignKey(
        SavedView,
        on_delete=models.CASCADE,
        related_name="filter_rules",
        verbose_name=_("saved view"),
    )

    rule_type = models.PositiveSmallIntegerField(_("rule type"), choices=RULE_TYPES)

    value = models.CharField(_("value"), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("filter rule")
        verbose_name_plural = _("filter rules")

    def __str__(self) -> str:
        return f"SavedViewFilterRule: {self.rule_type} : {self.value}"


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


class PaperlessTask(ModelWithOwner):
    ALL_STATES = sorted(states.ALL_STATES)
    TASK_STATE_CHOICES = sorted(zip(ALL_STATES, ALL_STATES))

    class TaskType(models.TextChoices):
        AUTO = ("auto_task", _("Auto Task"))
        SCHEDULED_TASK = ("scheduled_task", _("Scheduled Task"))
        MANUAL_TASK = ("manual_task", _("Manual Task"))

    class TaskName(models.TextChoices):
        CONSUME_FILE = ("consume_file", _("Consume File"))
        TRAIN_CLASSIFIER = ("train_classifier", _("Train Classifier"))
        CHECK_SANITY = ("check_sanity", _("Check Sanity"))
        INDEX_OPTIMIZE = ("index_optimize", _("Index Optimize"))
        LLMINDEX_UPDATE = ("llmindex_update", _("LLM Index Update"))

    task_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Task ID"),
        help_text=_("Celery ID for the Task that was run"),
    )

    acknowledged = models.BooleanField(
        default=False,
        verbose_name=_("Acknowledged"),
        help_text=_("If the task is acknowledged via the frontend or API"),
    )

    task_file_name = models.CharField(
        null=True,
        max_length=255,
        verbose_name=_("Task Filename"),
        help_text=_("Name of the file which the Task was run for"),
    )

    task_name = models.CharField(
        null=True,
        max_length=255,
        choices=TaskName.choices,
        verbose_name=_("Task Name"),
        help_text=_("Name of the task that was run"),
    )

    status = models.CharField(
        max_length=30,
        default=states.PENDING,
        choices=TASK_STATE_CHOICES,
        verbose_name=_("Task State"),
        help_text=_("Current state of the task being run"),
    )

    date_created = models.DateTimeField(
        null=True,
        default=timezone.now,
        verbose_name=_("Created DateTime"),
        help_text=_("Datetime field when the task result was created in UTC"),
    )

    date_started = models.DateTimeField(
        null=True,
        default=None,
        verbose_name=_("Started DateTime"),
        help_text=_("Datetime field when the task was started in UTC"),
    )

    date_done = models.DateTimeField(
        null=True,
        default=None,
        verbose_name=_("Completed DateTime"),
        help_text=_("Datetime field when the task was completed in UTC"),
    )

    result = models.TextField(
        null=True,
        default=None,
        verbose_name=_("Result Data"),
        help_text=_(
            "The data returned by the task",
        ),
    )

    type = models.CharField(
        max_length=30,
        choices=TaskType.choices,
        default=TaskType.AUTO,
        verbose_name=_("Task Type"),
        help_text=_("The type of task that was run"),
    )

    def __str__(self) -> str:
        return f"Task {self.task_id}"


class Note(SoftDeleteModel):
    note = models.TextField(
        _("content"),
        blank=True,
        help_text=_("Note for the document"),
    )

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
    )

    document = models.ForeignKey(
        Document,
        blank=True,
        null=True,
        related_name="notes",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )

    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="notes",
        on_delete=models.SET_NULL,
        verbose_name=_("user"),
    )

    class Meta:
        ordering = ("created",)
        verbose_name = _("note")
        verbose_name_plural = _("notes")

    def __str__(self):
        return self.note


class ShareLink(SoftDeleteModel):
    class FileVersion(models.TextChoices):
        ARCHIVE = ("archive", _("Archive"))
        ORIGINAL = ("original", _("Original"))

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
        blank=True,
        editable=False,
    )

    expiration = models.DateTimeField(
        _("expiration"),
        blank=True,
        null=True,
        db_index=True,
    )

    slug = models.SlugField(
        _("slug"),
        db_index=True,
        unique=True,
        blank=True,
        editable=False,
    )

    document = models.ForeignKey(
        Document,
        blank=True,
        related_name="share_links",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )

    file_version = models.CharField(
        max_length=50,
        choices=FileVersion.choices,
        default=FileVersion.ARCHIVE,
    )

    owner = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="share_links",
        on_delete=models.SET_NULL,
        verbose_name=_("owner"),
    )

    class Meta:
        ordering = ("created",)
        verbose_name = _("share link")
        verbose_name_plural = _("share links")

    def __str__(self):
        return f"Share Link for {self.document.title}"


class ShareLinkBundle(models.Model):
    class Status(models.TextChoices):
        PENDING = ("pending", _("Pending"))
        PROCESSING = ("processing", _("Processing"))
        READY = ("ready", _("Ready"))
        FAILED = ("failed", _("Failed"))

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
        blank=True,
        editable=False,
    )

    expiration = models.DateTimeField(
        _("expiration"),
        blank=True,
        null=True,
        db_index=True,
    )

    slug = models.SlugField(
        _("slug"),
        db_index=True,
        unique=True,
        blank=True,
        editable=False,
    )

    owner = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="share_link_bundles",
        on_delete=models.SET_NULL,
        verbose_name=_("owner"),
    )

    file_version = models.CharField(
        max_length=50,
        choices=ShareLink.FileVersion.choices,
        default=ShareLink.FileVersion.ARCHIVE,
    )

    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )

    size_bytes = models.PositiveIntegerField(
        _("size (bytes)"),
        blank=True,
        null=True,
    )

    last_error = models.JSONField(
        _("last error"),
        blank=True,
        null=True,
        default=None,
    )

    file_path = models.CharField(
        _("file path"),
        max_length=512,
        blank=True,
    )

    built_at = models.DateTimeField(
        _("built at"),
        null=True,
        blank=True,
    )

    documents = models.ManyToManyField(
        "documents.Document",
        related_name="share_link_bundles",
        verbose_name=_("documents"),
    )

    class Meta:
        ordering = ("-created",)
        verbose_name = _("share link bundle")
        verbose_name_plural = _("share link bundles")

    def __str__(self):
        return _("Share link bundle %(slug)s") % {"slug": self.slug}

    @property
    def absolute_file_path(self) -> Path | None:
        if not self.file_path:
            return None
        return (settings.SHARE_LINK_BUNDLE_DIR / Path(self.file_path)).resolve()

    def remove_file(self) -> None:
        if self.absolute_file_path is not None and self.absolute_file_path.exists():
            try:
                self.absolute_file_path.unlink()
            except OSError:
                pass

    def delete(self, using=None, *, keep_parents=False):
        self.remove_file()
        return super().delete(using=using, keep_parents=keep_parents)


class CustomField(models.Model):
    """
    Defines the name and type of a custom field
    """

    class FieldDataType(models.TextChoices):
        STRING = ("string", _("String"))
        URL = ("url", _("URL"))
        DATE = ("date", _("Date"))
        BOOL = ("boolean"), _("Boolean")
        INT = ("integer", _("Integer"))
        FLOAT = ("float", _("Float"))
        MONETARY = ("monetary", _("Monetary"))
        DOCUMENTLINK = ("documentlink", _("Document Link"))
        SELECT = ("select", _("Select"))
        LONG_TEXT = ("longtext", _("Long Text"))

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
        editable=False,
    )

    name = models.CharField(max_length=128)

    data_type = models.CharField(
        _("data type"),
        max_length=50,
        choices=FieldDataType.choices,
        editable=False,
    )

    extra_data = models.JSONField(
        _("extra data"),
        null=True,
        blank=True,
        help_text=_(
            "Extra data for the custom field, such as select options",
        ),
    )

    class Meta:
        ordering = ("created",)
        verbose_name = _("custom field")
        verbose_name_plural = _("custom fields")
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="%(app_label)s_%(class)s_unique_name",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} : {self.data_type}"


class CustomFieldInstance(SoftDeleteModel):
    """
    A single instance of a field, attached to a CustomField for the name and type
    and attached to a single Document to be metadata for it
    """

    TYPE_TO_DATA_STORE_NAME_MAP = {
        CustomField.FieldDataType.STRING: "value_text",
        CustomField.FieldDataType.URL: "value_url",
        CustomField.FieldDataType.DATE: "value_date",
        CustomField.FieldDataType.BOOL: "value_bool",
        CustomField.FieldDataType.INT: "value_int",
        CustomField.FieldDataType.FLOAT: "value_float",
        CustomField.FieldDataType.MONETARY: "value_monetary",
        CustomField.FieldDataType.DOCUMENTLINK: "value_document_ids",
        CustomField.FieldDataType.SELECT: "value_select",
        CustomField.FieldDataType.LONG_TEXT: "value_long_text",
    }

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
        editable=False,
    )

    document = models.ForeignKey(
        Document,
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name="custom_fields",
        editable=False,
    )

    field = models.ForeignKey(
        CustomField,
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name="fields",
        editable=False,
    )

    # Actual data storage
    value_text = models.CharField(max_length=128, null=True)

    value_bool = models.BooleanField(null=True)

    value_url = models.URLField(null=True)

    value_date = models.DateField(null=True)

    value_int = models.IntegerField(null=True)

    value_float = models.FloatField(null=True)

    value_monetary = models.CharField(null=True, max_length=128)

    value_monetary_amount = models.GeneratedField(
        expression=Case(
            # If the value starts with a number and no currency symbol, use the whole string
            models.When(
                value_monetary__regex=r"^\d+",
                then=Cast(
                    Substr("value_monetary", 1),
                    output_field=models.DecimalField(decimal_places=2, max_digits=65),
                ),
            ),
            # If the value starts with a 3-char currency symbol, use the rest of the string
            default=Cast(
                Substr("value_monetary", 4),
                output_field=models.DecimalField(decimal_places=2, max_digits=65),
            ),
            output_field=models.DecimalField(decimal_places=2, max_digits=65),
        ),
        output_field=models.DecimalField(decimal_places=2, max_digits=65),
        db_persist=True,
    )

    value_document_ids = models.JSONField(null=True)

    value_select = models.CharField(null=True, max_length=16)

    value_long_text = models.TextField(null=True)

    class Meta:
        ordering = ("created",)
        verbose_name = _("custom field instance")
        verbose_name_plural = _("custom field instances")
        constraints = [
            models.UniqueConstraint(
                fields=["document", "field"],
                name="%(app_label)s_%(class)s_unique_document_field",
            ),
        ]

    def __str__(self) -> str:
        value = (
            next(
                option.get("label")
                for option in self.field.extra_data["select_options"]
                if option.get("id") == self.value_select
            )
            if (
                self.field.data_type == CustomField.FieldDataType.SELECT
                and self.value_select is not None
            )
            else self.value
        )
        return str(self.field.name) + f" : {value}"

    @classmethod
    def get_value_field_name(cls, data_type: CustomField.FieldDataType):
        try:
            return cls.TYPE_TO_DATA_STORE_NAME_MAP[data_type]
        except KeyError:  # pragma: no cover
            raise NotImplementedError(data_type)

    @property
    def value(self):
        """
        Based on the data type, access the actual value the instance stores
        A little shorthand/quick way to get what is actually here
        """
        value_field_name = self.get_value_field_name(self.field.data_type)
        return getattr(self, value_field_name)


if settings.AUDIT_LOG_ENABLED:
    auditlog.register(
        Document,
        m2m_fields={"tags"},
        exclude_fields=["content_length", "modified"],
    )
    auditlog.register(Correspondent)
    auditlog.register(Tag)
    auditlog.register(DocumentType)
    auditlog.register(Note)
    auditlog.register(CustomField)
    auditlog.register(CustomFieldInstance)


class WorkflowTrigger(models.Model):
    class WorkflowTriggerMatching(models.IntegerChoices):
        # No auto matching
        NONE = MatchingModel.MATCH_NONE, _("None")
        ANY = MatchingModel.MATCH_ANY, _("Any word")
        ALL = MatchingModel.MATCH_ALL, _("All words")
        LITERAL = MatchingModel.MATCH_LITERAL, _("Exact match")
        REGEX = MatchingModel.MATCH_REGEX, _("Regular expression")
        FUZZY = MatchingModel.MATCH_FUZZY, _("Fuzzy word")

    class WorkflowTriggerType(models.IntegerChoices):
        CONSUMPTION = 1, _("Consumption Started")
        DOCUMENT_ADDED = 2, _("Document Added")
        DOCUMENT_UPDATED = 3, _("Document Updated")
        SCHEDULED = 4, _("Scheduled")

    class DocumentSourceChoices(models.IntegerChoices):
        CONSUME_FOLDER = DocumentSource.ConsumeFolder.value, _("Consume Folder")
        API_UPLOAD = DocumentSource.ApiUpload.value, _("Api Upload")
        MAIL_FETCH = DocumentSource.MailFetch.value, _("Mail Fetch")
        WEB_UI = DocumentSource.WebUI.value, _("Web UI")

    class ScheduleDateField(models.TextChoices):
        ADDED = "added", _("Added")
        CREATED = "created", _("Created")
        MODIFIED = "modified", _("Modified")
        CUSTOM_FIELD = "custom_field", _("Custom Field")

    type = models.PositiveSmallIntegerField(
        _("Workflow Trigger Type"),
        choices=WorkflowTriggerType.choices,
        default=WorkflowTriggerType.CONSUMPTION,
    )

    sources = MultiSelectField(
        max_length=7,
        choices=DocumentSourceChoices.choices,
        default=f"{DocumentSource.ConsumeFolder},{DocumentSource.ApiUpload},{DocumentSource.MailFetch},{DocumentSource.WebUI}",
    )

    filter_path = models.CharField(
        _("filter path"),
        max_length=256,
        null=True,
        blank=True,
        help_text=_(
            "Only consume documents with a path that matches "
            "this if specified. Wildcards specified as * are "
            "allowed. Case insensitive.",
        ),
    )

    filter_filename = models.CharField(
        _("filter filename"),
        max_length=256,
        null=True,
        blank=True,
        help_text=_(
            "Only consume documents which entirely match this "
            "filename if specified. Wildcards such as *.pdf or "
            "*invoice* are allowed. Case insensitive.",
        ),
    )

    filter_mailrule = models.ForeignKey(
        "paperless_mail.MailRule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("filter documents from this mail rule"),
    )

    match = models.CharField(_("match"), max_length=256, blank=True)

    matching_algorithm = models.PositiveSmallIntegerField(
        _("matching algorithm"),
        choices=WorkflowTriggerMatching.choices,
        default=WorkflowTriggerMatching.NONE,
    )

    is_insensitive = models.BooleanField(_("is insensitive"), default=True)

    filter_has_tags = models.ManyToManyField(
        Tag,
        blank=True,
        verbose_name=_("has these tag(s)"),
    )

    filter_has_all_tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="workflowtriggers_has_all",
        verbose_name=_("has all of these tag(s)"),
    )

    filter_has_not_tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="workflowtriggers_has_not",
        verbose_name=_("does not have these tag(s)"),
    )

    filter_has_document_type = models.ForeignKey(
        DocumentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("has this document type"),
    )

    filter_has_any_document_types = models.ManyToManyField(
        DocumentType,
        blank=True,
        related_name="workflowtriggers_has_any_document_type",
        verbose_name=_("has one of these document types"),
    )

    filter_has_not_document_types = models.ManyToManyField(
        DocumentType,
        blank=True,
        related_name="workflowtriggers_has_not_document_type",
        verbose_name=_("does not have these document type(s)"),
    )

    filter_has_correspondent = models.ForeignKey(
        Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("has this correspondent"),
    )

    filter_has_not_correspondents = models.ManyToManyField(
        Correspondent,
        blank=True,
        related_name="workflowtriggers_has_not_correspondent",
        verbose_name=_("does not have these correspondent(s)"),
    )

    filter_has_any_correspondents = models.ManyToManyField(
        Correspondent,
        blank=True,
        related_name="workflowtriggers_has_any_correspondent",
        verbose_name=_("has one of these correspondents"),
    )

    filter_has_storage_path = models.ForeignKey(
        StoragePath,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("has this storage path"),
    )

    filter_has_any_storage_paths = models.ManyToManyField(
        StoragePath,
        blank=True,
        related_name="workflowtriggers_has_any_storage_path",
        verbose_name=_("has one of these storage paths"),
    )

    filter_has_not_storage_paths = models.ManyToManyField(
        StoragePath,
        blank=True,
        related_name="workflowtriggers_has_not_storage_path",
        verbose_name=_("does not have these storage path(s)"),
    )

    filter_custom_field_query = models.TextField(
        _("filter custom field query"),
        null=True,
        blank=True,
        help_text=_("JSON-encoded custom field query expression."),
    )

    schedule_offset_days = models.SmallIntegerField(
        _("schedule offset days"),
        default=0,
        help_text=_(
            "The number of days to offset the schedule trigger by.",
        ),
    )

    schedule_is_recurring = models.BooleanField(
        _("schedule is recurring"),
        default=False,
        help_text=_(
            "If the schedule should be recurring.",
        ),
    )

    schedule_recurring_interval_days = models.PositiveSmallIntegerField(
        _("schedule recurring delay in days"),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_(
            "The number of days between recurring schedule triggers.",
        ),
    )

    schedule_date_field = models.CharField(
        _("schedule date field"),
        max_length=20,
        choices=ScheduleDateField.choices,
        default=ScheduleDateField.ADDED,
        help_text=_(
            "The field to check for a schedule trigger.",
        ),
    )

    schedule_date_custom_field = models.ForeignKey(
        CustomField,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("schedule date custom field"),
    )

    class Meta:
        verbose_name = _("workflow trigger")
        verbose_name_plural = _("workflow triggers")

    def __str__(self):
        return f"WorkflowTrigger {self.pk}"


class WorkflowActionEmail(models.Model):
    subject = models.CharField(
        _("email subject"),
        max_length=256,
        null=False,
        help_text=_(
            "The subject of the email, can include some placeholders, "
            "see documentation.",
        ),
    )

    body = models.TextField(
        _("email body"),
        null=False,
        help_text=_(
            "The body (message) of the email, can include some placeholders, "
            "see documentation.",
        ),
    )

    to = models.TextField(
        _("emails to"),
        null=False,
        help_text=_(
            "The destination email addresses, comma separated.",
        ),
    )

    include_document = models.BooleanField(
        default=False,
        verbose_name=_("include document in email"),
    )

    def __str__(self):
        return f"Workflow Email Action {self.pk}"


class WorkflowActionWebhook(models.Model):
    # We dont use the built-in URLField because it is not flexible enough
    # validation is handled in the serializer
    url = models.CharField(
        _("webhook url"),
        null=False,
        max_length=256,
        help_text=_("The destination URL for the notification."),
    )

    use_params = models.BooleanField(
        default=True,
        verbose_name=_("use parameters"),
    )

    as_json = models.BooleanField(
        default=False,
        verbose_name=_("send as JSON"),
    )

    params = models.JSONField(
        _("webhook parameters"),
        null=True,
        blank=True,
        help_text=_("The parameters to send with the webhook URL if body not used."),
    )

    body = models.TextField(
        _("webhook body"),
        null=True,
        blank=True,
        help_text=_("The body to send with the webhook URL if parameters not used."),
    )

    headers = models.JSONField(
        _("webhook headers"),
        null=True,
        blank=True,
        help_text=_("The headers to send with the webhook URL."),
    )

    include_document = models.BooleanField(
        default=False,
        verbose_name=_("include document in webhook"),
    )

    def __str__(self):
        return f"Workflow Webhook Action {self.pk}"


class WorkflowAction(models.Model):
    class WorkflowActionType(models.IntegerChoices):
        ASSIGNMENT = (
            1,
            _("Assignment"),
        )
        REMOVAL = (
            2,
            _("Removal"),
        )
        EMAIL = (
            3,
            _("Email"),
        )
        WEBHOOK = (
            4,
            _("Webhook"),
        )
        PASSWORD_REMOVAL = (
            5,
            _("Password removal"),
        )

    type = models.PositiveSmallIntegerField(
        _("Workflow Action Type"),
        choices=WorkflowActionType.choices,
        default=WorkflowActionType.ASSIGNMENT,
    )

    order = models.PositiveSmallIntegerField(_("order"), default=0)

    assign_title = models.TextField(
        _("assign title"),
        null=True,
        blank=True,
        help_text=_(
            "Assign a document title, must  be a Jinja2 template, see documentation.",
        ),
    )

    assign_tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="+",
        verbose_name=_("assign this tag"),
    )

    assign_document_type = models.ForeignKey(
        DocumentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("assign this document type"),
    )

    assign_correspondent = models.ForeignKey(
        Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("assign this correspondent"),
    )

    assign_storage_path = models.ForeignKey(
        StoragePath,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("assign this storage path"),
    )

    assign_owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("assign this owner"),
    )

    assign_view_users = models.ManyToManyField(
        User,
        blank=True,
        related_name="+",
        verbose_name=_("grant view permissions to these users"),
    )

    assign_view_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="+",
        verbose_name=_("grant view permissions to these groups"),
    )

    assign_change_users = models.ManyToManyField(
        User,
        blank=True,
        related_name="+",
        verbose_name=_("grant change permissions to these users"),
    )

    assign_change_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="+",
        verbose_name=_("grant change permissions to these groups"),
    )

    assign_custom_fields = models.ManyToManyField(
        CustomField,
        blank=True,
        related_name="+",
        verbose_name=_("assign these custom fields"),
    )

    assign_custom_fields_values = models.JSONField(
        _("custom field values"),
        null=True,
        blank=True,
        help_text=_(
            "Optional values to assign to the custom fields.",
        ),
        default=dict,
    )

    remove_tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="+",
        verbose_name=_("remove these tag(s)"),
    )

    remove_all_tags = models.BooleanField(
        default=False,
        verbose_name=_("remove all tags"),
    )

    remove_document_types = models.ManyToManyField(
        DocumentType,
        blank=True,
        related_name="+",
        verbose_name=_("remove these document type(s)"),
    )

    remove_all_document_types = models.BooleanField(
        default=False,
        verbose_name=_("remove all document types"),
    )

    remove_correspondents = models.ManyToManyField(
        Correspondent,
        blank=True,
        related_name="+",
        verbose_name=_("remove these correspondent(s)"),
    )

    remove_all_correspondents = models.BooleanField(
        default=False,
        verbose_name=_("remove all correspondents"),
    )

    remove_storage_paths = models.ManyToManyField(
        StoragePath,
        blank=True,
        related_name="+",
        verbose_name=_("remove these storage path(s)"),
    )

    remove_all_storage_paths = models.BooleanField(
        default=False,
        verbose_name=_("remove all storage paths"),
    )

    remove_owners = models.ManyToManyField(
        User,
        blank=True,
        related_name="+",
        verbose_name=_("remove these owner(s)"),
    )

    remove_all_owners = models.BooleanField(
        default=False,
        verbose_name=_("remove all owners"),
    )

    remove_view_users = models.ManyToManyField(
        User,
        blank=True,
        related_name="+",
        verbose_name=_("remove view permissions for these users"),
    )

    remove_view_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="+",
        verbose_name=_("remove view permissions for these groups"),
    )

    remove_change_users = models.ManyToManyField(
        User,
        blank=True,
        related_name="+",
        verbose_name=_("remove change permissions for these users"),
    )

    remove_change_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="+",
        verbose_name=_("remove change permissions for these groups"),
    )

    remove_all_permissions = models.BooleanField(
        default=False,
        verbose_name=_("remove all permissions"),
    )

    remove_custom_fields = models.ManyToManyField(
        CustomField,
        blank=True,
        related_name="+",
        verbose_name=_("remove these custom fields"),
    )

    remove_all_custom_fields = models.BooleanField(
        default=False,
        verbose_name=_("remove all custom fields"),
    )

    email = models.ForeignKey(
        WorkflowActionEmail,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action",
        verbose_name=_("email"),
    )

    webhook = models.ForeignKey(
        WorkflowActionWebhook,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action",
        verbose_name=_("webhook"),
    )

    passwords = models.JSONField(
        _("passwords"),
        null=True,
        blank=True,
        help_text=_(
            "Passwords to try when removing PDF protection. Separate with commas or new lines.",
        ),
    )

    class Meta:
        verbose_name = _("workflow action")
        verbose_name_plural = _("workflow actions")

    def __str__(self):
        return f"WorkflowAction {self.pk}"


class Workflow(models.Model):
    name = models.CharField(_("name"), max_length=256, unique=True)

    order = models.SmallIntegerField(_("order"), default=0)

    triggers = models.ManyToManyField(
        WorkflowTrigger,
        related_name="workflows",
        blank=False,
        verbose_name=_("triggers"),
    )

    actions = models.ManyToManyField(
        WorkflowAction,
        related_name="workflows",
        blank=False,
        verbose_name=_("actions"),
    )

    enabled = models.BooleanField(_("enabled"), default=True)

    def __str__(self):
        return f"Workflow: {self.name}"


class WorkflowRun(SoftDeleteModel):
    workflow = models.ForeignKey(
        Workflow,
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name=_("workflow"),
    )

    type = models.PositiveSmallIntegerField(
        _("workflow trigger type"),
        choices=WorkflowTrigger.WorkflowTriggerType.choices,
        null=True,
    )

    document = models.ForeignKey(
        Document,
        null=True,
        on_delete=models.CASCADE,
        related_name="workflow_runs",
        verbose_name=_("document"),
    )

    run_at = models.DateTimeField(
        _("date run"),
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        verbose_name = _("workflow run")
        verbose_name_plural = _("workflow runs")

    def __str__(self):
        return f"WorkflowRun of {self.workflow} at {self.run_at} on {self.document}"
