"""
OCR Template models for zone-based extraction.

An OcrTemplate is linked to a DocumentType. When a document of that type is consumed,
each zone in the template is cropped from the document image and OCR'd separately.
The extracted text is written to the configured custom field.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class OcrTemplate(models.Model):
    """
    Defines a set of OCR extraction zones for a specific document type.
    """

    name = models.CharField(
        _("name"),
        max_length=128,
    )

    document_type = models.ForeignKey(
        "documents.DocumentType",
        on_delete=models.CASCADE,
        related_name="ocr_templates",
        verbose_name=_("document type"),
        db_index=True,
    )

    default_page = models.IntegerField(
        _("default page"),
        default=1,
        help_text=_("Default page for zones (1 = first page, -1 = last page)"),
    )

    source_width = models.PositiveIntegerField(
        _("source width"),
        validators=[MinValueValidator(1)],
        help_text=_("Width of the image the zones were drawn on (px)"),
    )

    source_height = models.PositiveIntegerField(
        _("source height"),
        validators=[MinValueValidator(1)],
        help_text=_("Height of the image the zones were drawn on (px)"),
    )

    sample_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("sample document"),
        help_text=_("Document used for previewing zones in the editor"),
    )

    enabled = models.BooleanField(_("enabled"), default=True)

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
        db_index=True,
        editable=False,
    )

    updated = models.DateTimeField(
        _("updated"),
        auto_now=True,
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("OCR template")
        verbose_name_plural = _("OCR templates")

    def __str__(self) -> str:
        return f"{self.name} ({self.document_type})"


class OcrTemplateZone(models.Model):
    """
    A rectangular region within a document page to OCR and extract into a custom field.
    Coordinates are relative to the source image dimensions stored on the template.
    """

    template = models.ForeignKey(
        OcrTemplate,
        on_delete=models.CASCADE,
        related_name="zones",
        verbose_name=_("template"),
    )

    name = models.CharField(
        _("zone name"),
        max_length=128,
        help_text=_("Descriptive name for this zone (e.g. 'Invoice Number')"),
    )

    class TargetType(models.TextChoices):
        CUSTOM_FIELD = ("custom_field", _("Custom field"))
        TITLE = ("title", _("Title"))
        ASN = ("asn", _("Archive serial number"))
        CREATED = ("created", _("Date created"))

    target = models.CharField(
        _("target"),
        max_length=20,
        choices=TargetType.choices,
        default=TargetType.CUSTOM_FIELD,
        help_text=_(
            "Where the extracted value is written: a custom field, or a "
            "built-in document field (title, ASN, created date)",
        ),
    )

    custom_field = models.ForeignKey(
        "documents.CustomField",
        on_delete=models.CASCADE,
        related_name="ocr_zones",
        verbose_name=_("custom field"),
        null=True,
        blank=True,
        help_text=_("Target custom field (only used when target is 'custom_field')"),
    )

    page = models.IntegerField(
        _("page"),
        null=True,
        blank=True,
        help_text=_("Page (1 = first, -1 = last; blank uses the template default)"),
    )

    x = models.PositiveIntegerField(_("x"), help_text=_("Left edge (px)"))
    y = models.PositiveIntegerField(_("y"), help_text=_("Top edge (px)"))
    width = models.PositiveIntegerField(
        _("width"),
        validators=[MinValueValidator(1)],
        help_text=_("Zone width (px)"),
    )
    height = models.PositiveIntegerField(
        _("height"),
        validators=[MinValueValidator(1)],
        help_text=_("Zone height (px)"),
    )

    # Per-zone source dimensions for coordinate scaling.
    # Stored from the page image the zone was drawn on.
    # If null, falls back to the template's source_width/source_height.
    # This handles PDFs with mixed page sizes (e.g. landscape + portrait,
    # or different paper formats across pages).
    zone_source_width = models.PositiveIntegerField(
        _("zone source width"),
        null=True,
        blank=True,
        help_text=_("Width of the page image this zone was drawn on (px). "
                     "Falls back to template source_width if unset."),
    )
    zone_source_height = models.PositiveIntegerField(
        _("zone source height"),
        null=True,
        blank=True,
        help_text=_("Height of the page image this zone was drawn on (px). "
                     "Falls back to template source_height if unset."),
    )

    ocr_language = models.CharField(
        _("OCR language"),
        max_length=20,
        default="deu+eng",
        help_text=_("Tesseract language code(s), e.g. 'deu+eng'"),
    )

    class TransformType(models.TextChoices):
        NONE = ("none", _("None"))
        STRIP = ("strip", _("Strip whitespace"))
        UPPERCASE = ("uppercase", _("Uppercase"))
        LOWERCASE = ("lowercase", _("Lowercase"))
        NUMERIC = ("numeric", _("Numeric only"))
        DATE = ("date", _("Parse date"))
        QR_CODE = ("qr_code", _("Read QR/barcode"))
        QR_CODE_RAW = ("qr_code_raw", _("Read QR/barcode (raw)"))

    transform = models.CharField(
        _("transform"),
        max_length=20,
        choices=TransformType.choices,
        default=TransformType.STRIP,
    )

    date_format = models.CharField(
        _("date format"),
        max_length=64,
        blank=True,
        default="",
        help_text=_(
            "Python strptime format for the 'Parse date' transform "
            "(e.g. %d.%m.%Y). Blank = auto-detect.",
        ),
    )

    validation_regex = models.CharField(
        _("validation regex"),
        max_length=256,
        blank=True,
        default="",
        help_text=_("Optional regex pattern — extracted text is only accepted if it matches"),
    )

    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ("template", "order")
        verbose_name = _("OCR template zone")
        verbose_name_plural = _("OCR template zones")

    def __str__(self) -> str:
        return f"{self.template.name} → {self.name}"
