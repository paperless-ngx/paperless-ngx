import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


def validate_subdomain(value):
    """
    Validate that subdomain contains only lowercase alphanumeric characters and hyphens.
    """
    if not re.match(r'^[a-z0-9-]+$', value):
        raise ValidationError(
            _('Subdomain must contain only lowercase alphanumeric characters and hyphens.'),
            code='invalid_subdomain',
        )


class Tenant(models.Model):
    """
    Tenant model for multi-tenant architecture.
    Each tenant represents an isolated organization with its own data and settings.
    """

    REGION_CHOICES = [
        ('eu', _('Europe')),
        ('us', _('United States')),
        ('asia', _('Asia')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID'),
    )

    name = models.CharField(
        _('name'),
        max_length=128,
        help_text=_('Organization name'),
    )

    subdomain = models.SlugField(
        _('subdomain'),
        max_length=63,
        unique=True,
        validators=[validate_subdomain],
        help_text=_('Subdomain for routing (e.g., "acme")'),
    )

    region = models.CharField(
        _('region'),
        max_length=10,
        choices=REGION_CHOICES,
        default='us',
        help_text=_('Region for multi-region support'),
    )

    max_storage_gb = models.IntegerField(
        _('max storage GB'),
        default=10,
        help_text=_('Storage quota in GB'),
    )

    max_documents = models.IntegerField(
        _('max documents'),
        default=10000,
        help_text=_('Maximum number of documents'),
    )

    max_users = models.IntegerField(
        _('max users'),
        default=10,
        help_text=_('Maximum number of user seats'),
    )

    theme_color = models.CharField(
        _('theme color'),
        max_length=7,
        default='#17541f',
        help_text=_('Branding theme color (hex format)'),
    )

    app_title = models.CharField(
        _('app title'),
        max_length=128,
        default='Paperless-ngx',
        help_text=_('Application title for branding'),
    )

    logo_url = models.URLField(
        _('logo URL'),
        blank=True,
        help_text=_('Custom logo URL'),
    )

    custom_css = models.TextField(
        _('custom CSS'),
        blank=True,
        help_text=_('Custom CSS styling'),
    )

    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Enable or disable tenant'),
    )

    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )

    class Meta:
        db_table = 'tenants'
        verbose_name = _('tenant')
        verbose_name_plural = _('tenants')
        indexes = [
            models.Index(fields=['subdomain'], name='tenant_subdomain_idx'),
            models.Index(fields=['region'], name='tenant_region_idx'),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.subdomain})"

    @property
    def storage_container(self):
        """
        Returns the MinIO bucket name for this tenant.
        Format: paperless-{tenant_id}
        """
        return f"paperless-{self.id}"
