"""
TenantGroup model for tenant-scoped group management.

This module provides:
- TenantGroup: A tenant-aware group model that provides automatic tenant isolation
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from documents.models.base import ModelWithOwner


class TenantGroup(ModelWithOwner):
    """
    Tenant-aware group model that provides automatic tenant isolation.

    This model replaces django.contrib.auth.models.Group for tenant-scoped
    group management. It inherits from ModelWithOwner to get:
    - Automatic tenant_id field
    - TenantManager for automatic tenant filtering
    - owner field for tracking who created the group

    All queries using TenantGroup.objects will be automatically filtered
    by the current tenant context set by TenantMiddleware.

    Example:
        # In view (tenant context set by middleware):
        groups = TenantGroup.objects.all()  # Only current tenant's groups

        # Create new group (tenant_id auto-populated):
        group = TenantGroup.objects.create(name="Editors")

        # Bypass tenant filtering (admin only):
        all_groups = TenantGroup.all_objects.all()
    """

    name = models.CharField(
        max_length=150,
        verbose_name=_("name"),
        help_text=_("The name of the group within this tenant"),
    )

    # Many-to-many relationship for permissions
    # Uses related_name to avoid conflicts with Django's Group model
    permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_("permissions"),
        blank=True,
        related_name="tenant_groups",
    )

    users = models.ManyToManyField(
        'auth.User',
        verbose_name=_("users"),
        blank=True,
        related_name="tenant_groups",
        help_text=_("Users in this tenant group"),
    )

    class Meta:
        verbose_name = _("tenant group")
        verbose_name_plural = _("tenant groups")
        # Ensure group names are unique within a tenant
        unique_together = [["tenant_id", "name"]]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def natural_key(self):
        """Return natural key for serialization."""
        return (self.name, str(self.tenant_id))
