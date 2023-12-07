from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

DEFAULT_SINGLETON_INSTANCE_ID = 1


class OcrSettings(models.Model):
    class OutputTypeChoices(models.TextChoices):
        PDF = ("pdf", _("pdf"))
        PDF_A = ("pdfa", _("pdfa"))
        PDF_A1 = ("pdfa-1", _("pdfa-1"))
        PDF_A2 = ("pdfa-2", _("pdfa-2"))
        PDF_A3 = ("pdfa-3", _("pdfa-3"))

    class ModeChoices(models.TextChoices):
        SKIP = ("skip", _("skip"))
        SKIP_NO_ARCHIVE = ("skip_noarchive", _("skip_noarchive"))
        REDO = ("redo", _("redo"))
        FORCE = ("force", _("force"))

    class ArchiveFileChoices(models.TextChoices):
        NEVER = ("never", _("never"))
        WITH_TEXT = ("with_text", _("with_text"))
        ALWAYS = ("always", _("always"))

    class CleanChoices(models.TextChoices):
        CLEAN = ("clean", _("clean"))
        FINAL = ("clean-final", _("clean-final"))
        NONE = ("none", _("none"))

    class ColorConvertChoices(models.TextChoices):
        UNCHANGED = ("LeaveColorUnchanged", _("LeaveColorUnchanged"))
        RGB = ("RGB", _("RGB"))
        INDEPENDENT = ("UseDeviceIndependentColor", _("UseDeviceIndependentColor"))
        GRAY = ("Gray", _("Gray"))
        CMYK = ("CMYK", _("CMYK"))

    pages = models.PositiveIntegerField(null=True, blank=True)

    language = models.CharField(null=True, blank=True, max_length=32)

    output_type = models.CharField(
        null=True,
        blank=True,
        max_length=8,
        choices=OutputTypeChoices.choices,
    )

    mode = models.CharField(
        null=True,
        blank=True,
        max_length=8,
        choices=ModeChoices.choices,
    )

    skip_archive_file = models.CharField(
        null=True,
        blank=True,
        max_length=16,
        choices=ArchiveFileChoices.choices,
    )

    image_dpi = models.PositiveIntegerField(null=True)

    unpaper_clean = models.CharField(
        null=True,
        blank=True,
        max_length=16,
        choices=CleanChoices.choices,
    )

    deskew = models.BooleanField(null=True)

    rotate_pages = models.BooleanField(null=True)

    rotate_pages_threshold = models.FloatField(
        null=True,
        validators=[MinValueValidator(0.0)],
    )

    max_image_pixels = models.FloatField(
        null=True,
        validators=[MinValueValidator(1_000_000.0)],
    )

    color_conversion_strategy = models.CharField(
        blank=True,
        null=True,
        max_length=32,
        choices=ColorConvertChoices.choices,
    )

    user_args = models.JSONField(null=True)

    class Meta:
        verbose_name = _("ocr settings")

    def __str__(self) -> str:
        return ""

    def save(self, *args, **kwargs):
        if not self.pk and OcrSettings.objects.exists():
            # if you'll not check for self.pk
            # then error will also be raised in the update of exists model
            raise ValidationError(
                "There is can be only one JuicerBaseSettings instance",
            )
        return super().save(*args, **kwargs)

    @classmethod
    def object(cls):
        return cls._default_manager.all().first()  # Since only one item
