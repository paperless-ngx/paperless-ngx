from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class OcrSettings(models.Model):
    class OutputTypeChoices(models.TextChoices):
        PDF = ("pdf", _("pdf"))
        PDF_A = ("pdfa", _("pdfa"))
        PDF_A1 = ("pdfa-1", _("pdfa-1"))
        PDF_A2 = ("pdfa-2", _("pdfa-2"))
        PDF_A3 = ("pdfa-3", _("pdfa-3"))

    class ModeChoices(models.TextChoices):
        SKIP = ("skip", _("pdf"))
        REDO = ("redo", _("pdfa"))
        FORCE = ("force", _("pdfa-1"))

    class ArchiveFileChoices(models.TextChoices):
        NEVER = ("never", _("pdf"))
        WITH_TEXT = ("with_text", _("pdfa"))
        ALWAYS = ("always", _("pdfa-1"))

    pages = models.PositiveIntegerField(null=True)
    language = models.CharField(null=True, blank=True, max_length=32)
    output_type = models.CharField(
        max_length=10,
        choices=OutputTypeChoices.choices,
        default=OutputTypeChoices.PDF_A,
    )
    mode = models.CharField(
        max_length=50,
        choices=ModeChoices.choices,
        default=ModeChoices.SKIP,
    )
    skip_archive_file = models.CharField(
        max_length=50,
        choices=ArchiveFileChoices.choices,
        default=ArchiveFileChoices.NEVER,
    )
    image_dpi = models.PositiveIntegerField(null=True)
    clean = models.CharField(null=True, blank=True)
    deskew = models.BooleanField(default=True)
    rotate_pages = models.BooleanField(default=True)
    rotate_pages_threshold = models.FloatField(
        default=12.0,
        validators=[MinValueValidator(0.0)],
    )
    max_image_pixel = models.PositiveBigIntegerField(
        null=True,
        validators=[MinValueValidator(1_000_000.0)],
    )
    color_conversion_strategy = models.CharField(blank=True, null=True)
    user_args = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = _("ocr settings")

    def __str__(self) -> str:
        return ""
