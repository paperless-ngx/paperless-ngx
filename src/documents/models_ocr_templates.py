"""
OCR Template models for zone-based extraction.

An OcrTemplate is linked to a DocumentType. When a document of that type is consumed,
each zone in the template is cropped from the document image and OCR'd separately.
The extracted text is written to the configured custom field.
"""

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
    )

    # Which page to extract from (0-indexed, -1 = last page)
    default_page = models.IntegerField(
        _("default page"),
        default=0,
        help_text=_("Default page index for zones (0-indexed, -1 for last page)"),
    )

    # Source image dimensions the zones were drawn on (for coordinate scaling)
    source_width = models.IntegerField(
        _("source width"),
        help_text=_("Width of the image the zones were drawn on"),
    )

    source_height = models.IntegerField(
        _("source height"),
        help_text=_("Height of the image the zones were drawn on"),
    )

    enabled = models.BooleanField(_("enabled"), default=True)

    created = models.DateTimeField(
        _("created"),
        default=timezone.now,
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

    # Target custom field to write the extracted value to
    custom_field = models.ForeignKey(
        "documents.CustomField",
        on_delete=models.CASCADE,
        related_name="ocr_zones",
        verbose_name=_("custom field"),
    )

    # Page override (None = use template default)
    page = models.IntegerField(
        _("page"),
        null=True,
        blank=True,
        help_text=_("Page index override (leave blank to use template default)"),
    )

    # Zone coordinates (pixels relative to source_width/source_height)
    x = models.IntegerField(_("x"), help_text=_("Left edge (px)"))
    y = models.IntegerField(_("y"), help_text=_("Top edge (px)"))
    width = models.IntegerField(_("width"), help_text=_("Zone width (px)"))
    height = models.IntegerField(_("height"), help_text=_("Zone height (px)"))

    # OCR configuration per zone
    ocr_language = models.CharField(
        _("OCR language"),
        max_length=20,
        default="deu+eng",
        help_text=_("Tesseract language code(s), e.g. 'deu+eng'"),
    )

    # Optional post-processing
    TRANSFORM_CHOICES = [
        ("none", _("None")),
        ("strip", _("Strip whitespace")),
        ("uppercase", _("Uppercase")),
        ("lowercase", _("Lowercase")),
        ("numeric", _("Numeric only")),
        ("date_dmy", _("Parse date (DD.MM.YYYY)")),
        ("date_ymd", _("Parse date (YYYY-MM-DD)")),
    ]

    transform = models.CharField(
        _("transform"),
        max_length=20,
        choices=TRANSFORM_CHOICES,
        default="strip",
    )

    order = models.IntegerField(_("order"), default=0)

    class Meta:
        ordering = ("template", "order")
        verbose_name = _("OCR template zone")
        verbose_name_plural = _("OCR template zones")

    def __str__(self) -> str:
        return f"{self.template.name} → {self.name}"
