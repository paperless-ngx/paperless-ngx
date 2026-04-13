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
        default=0,
        help_text=_("Default page index for zones (0-indexed, -1 for last page)"),
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

    custom_field = models.ForeignKey(
        "documents.CustomField",
        on_delete=models.CASCADE,
        related_name="ocr_zones",
        verbose_name=_("custom field"),
    )

    page = models.IntegerField(
        _("page"),
        null=True,
        blank=True,
        help_text=_("Page index override (leave blank to use template default)"),
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
        DATE_DMY = ("date_dmy", _("Parse date (DD.MM.YYYY)"))
        DATE_YMD = ("date_ymd", _("Parse date (YYYY-MM-DD)"))

    transform = models.CharField(
        _("transform"),
        max_length=20,
        choices=TransformType.choices,
        default=TransformType.STRIP,
    )

    order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ("template", "order")
        verbose_name = _("OCR template zone")
        verbose_name_plural = _("OCR template zones")

    def __str__(self) -> str:
        return f"{self.template.name} → {self.name}"
