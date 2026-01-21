from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

# Import and re-export Tenant and TenantGroup for backward compatibility
from documents.models import Tenant, TenantGroup

DEFAULT_SINGLETON_INSTANCE_ID = 1


class AbstractSingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Always save as the first and only model
        """
        self.pk = DEFAULT_SINGLETON_INSTANCE_ID
        super().save(*args, **kwargs)


class OutputTypeChoices(models.TextChoices):
    """
    Matches to --output-type
    """

    PDF = ("pdf", _("pdf"))
    PDF_A = ("pdfa", _("pdfa"))
    PDF_A1 = ("pdfa-1", _("pdfa-1"))
    PDF_A2 = ("pdfa-2", _("pdfa-2"))
    PDF_A3 = ("pdfa-3", _("pdfa-3"))


class ModeChoices(models.TextChoices):
    """
    Matches to --skip-text, --redo-ocr, --force-ocr
    and our own custom setting
    """

    SKIP = ("skip", _("skip"))
    REDO = ("redo", _("redo"))
    FORCE = ("force", _("force"))
    SKIP_NO_ARCHIVE = ("skip_noarchive", _("skip_noarchive"))


class ArchiveFileChoices(models.TextChoices):
    """
    Settings to control creation of an archive PDF file
    """

    NEVER = ("never", _("never"))
    WITH_TEXT = ("with_text", _("with_text"))
    ALWAYS = ("always", _("always"))


class CleanChoices(models.TextChoices):
    """
    Matches to --clean, --clean-final
    """

    CLEAN = ("clean", _("clean"))
    FINAL = ("clean-final", _("clean-final"))
    NONE = ("none", _("none"))


class ColorConvertChoices(models.TextChoices):
    """
    Refer to the Ghostscript documentation for valid options
    """

    UNCHANGED = ("LeaveColorUnchanged", _("LeaveColorUnchanged"))
    RGB = ("RGB", _("RGB"))
    INDEPENDENT = ("UseDeviceIndependentColor", _("UseDeviceIndependentColor"))
    GRAY = ("Gray", _("Gray"))
    CMYK = ("CMYK", _("CMYK"))


class LLMEmbeddingBackend(models.TextChoices):
    OPENAI = ("openai", _("OpenAI"))
    HUGGINGFACE = ("huggingface", _("Huggingface"))


class LLMBackend(models.TextChoices):
    """
    Matches to --llm-backend
    """

    OPENAI = ("openai", _("OpenAI"))
    OLLAMA = ("ollama", _("Ollama"))


class ApplicationConfiguration(AbstractSingletonModel):
    """
    Settings which are common across more than 1 parser
    """

    output_type = models.CharField(
        verbose_name=_("Sets the output PDF type"),
        null=True,
        blank=True,
        max_length=8,
        choices=OutputTypeChoices.choices,
    )

    """
    Settings for the Tesseract based OCR parser
    """

    pages = models.PositiveIntegerField(
        verbose_name=_("Do OCR from page 1 to this value"),
        null=True,
        validators=[MinValueValidator(1)],
    )

    language = models.CharField(
        verbose_name=_("Do OCR using these languages"),
        null=True,
        blank=True,
        max_length=32,
    )

    mode = models.CharField(
        verbose_name=_("Sets the OCR mode"),
        null=True,
        blank=True,
        max_length=16,
        choices=ModeChoices.choices,
    )

    skip_archive_file = models.CharField(
        verbose_name=_("Controls the generation of an archive file"),
        null=True,
        blank=True,
        max_length=16,
        choices=ArchiveFileChoices.choices,
    )

    image_dpi = models.PositiveIntegerField(
        verbose_name=_("Sets image DPI fallback value"),
        null=True,
        validators=[MinValueValidator(1)],
    )

    # Can't call it clean, that's a model method
    unpaper_clean = models.CharField(
        verbose_name=_("Controls the unpaper cleaning"),
        null=True,
        blank=True,
        max_length=16,
        choices=CleanChoices.choices,
    )

    deskew = models.BooleanField(verbose_name=_("Enables deskew"), null=True)

    rotate_pages = models.BooleanField(
        verbose_name=_("Enables page rotation"),
        null=True,
    )

    rotate_pages_threshold = models.FloatField(
        verbose_name=_("Sets the threshold for rotation of pages"),
        null=True,
        validators=[MinValueValidator(0.0)],
    )

    max_image_pixels = models.FloatField(
        verbose_name=_("Sets the maximum image size for decompression"),
        null=True,
        validators=[MinValueValidator(0.0)],
    )

    color_conversion_strategy = models.CharField(
        verbose_name=_("Sets the Ghostscript color conversion strategy"),
        blank=True,
        null=True,
        max_length=32,
        choices=ColorConvertChoices.choices,
    )

    user_args = models.JSONField(
        verbose_name=_("Adds additional user arguments for OCRMyPDF"),
        null=True,
    )

    """
    Settings for the Paperless application
    """

    app_title = models.CharField(
        verbose_name=_("Application title"),
        null=True,
        blank=True,
        max_length=48,
    )

    app_logo = models.FileField(
        verbose_name=_("Application logo"),
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "png", "gif", "svg"]),
        ],
        upload_to="logo/",
    )

    """
    Settings for the barcode scanner
    """

    # PAPERLESS_CONSUMER_ENABLE_BARCODES
    barcodes_enabled = models.BooleanField(
        verbose_name=_("Enables barcode scanning"),
        null=True,
    )

    # PAPERLESS_CONSUMER_BARCODE_TIFF_SUPPORT
    barcode_enable_tiff_support = models.BooleanField(
        verbose_name=_("Enables barcode TIFF support"),
        null=True,
    )

    # PAPERLESS_CONSUMER_BARCODE_STRING
    barcode_string = models.CharField(
        verbose_name=_("Sets the barcode string"),
        null=True,
        blank=True,
        max_length=32,
    )

    # PAPERLESS_CONSUMER_BARCODE_RETAIN_SPLIT_PAGES
    barcode_retain_split_pages = models.BooleanField(
        verbose_name=_("Retains split pages"),
        null=True,
    )

    # PAPERLESS_CONSUMER_ENABLE_ASN_BARCODE
    barcode_enable_asn = models.BooleanField(
        verbose_name=_("Enables ASN barcode"),
        null=True,
    )

    # PAPERLESS_CONSUMER_ASN_BARCODE_PREFIX
    barcode_asn_prefix = models.CharField(
        verbose_name=_("Sets the ASN barcode prefix"),
        null=True,
        blank=True,
        max_length=32,
    )

    # PAPERLESS_CONSUMER_BARCODE_UPSCALE
    barcode_upscale = models.FloatField(
        verbose_name=_("Sets the barcode upscale factor"),
        null=True,
        validators=[MinValueValidator(1.0)],
    )

    # PAPERLESS_CONSUMER_BARCODE_DPI
    barcode_dpi = models.PositiveIntegerField(
        verbose_name=_("Sets the barcode DPI"),
        null=True,
        validators=[MinValueValidator(1)],
    )

    # PAPERLESS_CONSUMER_BARCODE_MAX_PAGES
    barcode_max_pages = models.PositiveIntegerField(
        verbose_name=_("Sets the maximum pages for barcode"),
        null=True,
        validators=[MinValueValidator(1)],
    )

    # PAPERLESS_CONSUMER_ENABLE_TAG_BARCODE
    barcode_enable_tag = models.BooleanField(
        verbose_name=_("Enables tag barcode"),
        null=True,
    )

    # PAPERLESS_CONSUMER_TAG_BARCODE_MAPPING
    barcode_tag_mapping = models.JSONField(
        verbose_name=_("Sets the tag barcode mapping"),
        null=True,
    )

    """
    AI related settings
    """

    ai_enabled = models.BooleanField(
        verbose_name=_("Enables AI features"),
        null=True,
        default=False,
    )

    llm_embedding_backend = models.CharField(
        verbose_name=_("Sets the LLM embedding backend"),
        blank=True,
        null=True,
        max_length=128,
        choices=LLMEmbeddingBackend.choices,
    )

    llm_embedding_model = models.CharField(
        verbose_name=_("Sets the LLM embedding model"),
        blank=True,
        null=True,
        max_length=128,
    )

    llm_backend = models.CharField(
        verbose_name=_("Sets the LLM backend"),
        blank=True,
        null=True,
        max_length=128,
        choices=LLMBackend.choices,
    )

    llm_model = models.CharField(
        verbose_name=_("Sets the LLM model"),
        blank=True,
        null=True,
        max_length=128,
    )

    llm_api_key = models.CharField(
        verbose_name=_("Sets the LLM API key"),
        blank=True,
        null=True,
        max_length=1024,
    )

    llm_endpoint = models.CharField(
        verbose_name=_("Sets the LLM endpoint, optional"),
        blank=True,
        null=True,
        max_length=256,
    )

    class Meta:
        verbose_name = _("paperless application settings")

    def __str__(self) -> str:  # pragma: no cover
        return "ApplicationConfiguration"


class UserProfile(models.Model):
    """
    User profile extending Django's User model with tenant_id.

    This model provides multi-tenant isolation for users by associating
    each user with a specific tenant via tenant_id field.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_("user"),
    )

    tenant_id = models.UUIDField(
        db_index=True,
        null=False,
        blank=False,
        verbose_name=_("tenant"),
        help_text=_("Tenant to which this user belongs"),
    )

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")
        indexes = [
            models.Index(fields=['tenant_id'], name='userprofile_tenant_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} - Tenant {self.tenant_id}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create UserProfile when User is created.

    This handler ensures every user (except system users) has a UserProfile
    with a tenant_id. It attempts to get tenant_id from request context,
    falling back to default tenant if unavailable.
    """
    if created and instance.username not in ["consumer", "AnonymousUser"]:
        # Import here to avoid circular imports
        from documents.models.base import get_current_tenant_id
        from documents.models import Tenant
        import logging

        logger = logging.getLogger(__name__)

        # Check if profile already exists (unlikely but defensive)
        if hasattr(instance, 'profile'):
            return

        tenant_id = get_current_tenant_id()

        # If no tenant context, try to get default tenant
        if not tenant_id:
            try:
                default_tenant = Tenant.objects.filter(subdomain='default').first()
                if default_tenant:
                    tenant_id = default_tenant.id
                    logger.warning(
                        f"User {instance.username} created without tenant context. "
                        f"Assigned to default tenant {tenant_id}."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get default tenant for user {instance.username}: {e}"
                )

        # Create profile if we have a tenant_id
        if tenant_id:
            try:
                UserProfile.objects.create(user=instance, tenant_id=tenant_id)
                logger.info(f"Created UserProfile for {instance.username} with tenant {tenant_id}")
            except Exception as e:
                logger.error(
                    f"Failed to create UserProfile for user {instance.username}: {e}"
                )
