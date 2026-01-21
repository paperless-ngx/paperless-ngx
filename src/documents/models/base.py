"""
Base models and managers for documents app.

This module provides:
- TenantManager: Automatic tenant filtering for ORM queries
- ModelWithOwner: Base model with owner and tenant_id fields

Tenant Isolation Model:
-----------------------
All models inheriting from ModelWithOwner automatically filter queries by the
current tenant context set by TenantMiddleware. This provides transparent
tenant isolation at the ORM level.

Usage:
    # Standard queries automatically filtered by current tenant
    documents = Document.objects.all()  # Only returns current tenant's documents

    # Bypass filtering (admin/superuser only)
    all_documents = Document.all_objects.all()  # Returns documents from all tenants

    # Related queries also respect tenant filtering
    tags = document.tags.all()  # Only returns tags belonging to current tenant

The tenant context is set by TenantMiddleware via set_current_tenant_id().
All subsequent ORM queries are automatically filtered without needing manual
.filter(tenant_id=...) calls.
"""

import threading

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

# Thread-local storage for current tenant
_thread_local = threading.local()


def get_current_tenant_id():
    """
    Get the current tenant ID from thread-local storage.

    Returns:
        UUID or None: The current tenant ID, or None if no tenant is set.

    Note:
        This is typically set by TenantMiddleware for each request.
    """
    return getattr(_thread_local, 'tenant_id', None)


def set_current_tenant_id(tenant_id):
    """
    Set the current tenant ID in thread-local storage.

    Args:
        tenant_id: UUID of the tenant to set as current, or None to clear.

    Note:
        This is typically called by TenantMiddleware for each request.
        Setting this affects all subsequent ORM queries using TenantManager.
    """
    _thread_local.tenant_id = tenant_id


class TenantManager(models.Manager):
    """
    Custom manager that automatically filters queries by current tenant context.

    This manager provides transparent tenant isolation by automatically adding
    tenant_id filters to all queries. The tenant context is retrieved from
    thread-local storage set by TenantMiddleware.

    Behavior:
        - If tenant context is set: Returns only objects belonging to current tenant
        - If tenant context is None: Returns empty queryset (security by default)

    Security Model:
        - TenantMiddleware sets tenant context from subdomain or X-Tenant-ID header
        - All queries using this manager are automatically scoped to current tenant
        - Related queries (ForeignKey, ManyToMany) also inherit tenant filtering
        - Use all_objects manager to bypass filtering (admin operations only)

    Example:
        class Document(ModelWithOwner):
            objects = TenantManager()  # Tenant-aware queries
            all_objects = models.Manager()  # Bypass tenant filtering

        # In view (tenant context set by middleware):
        docs = Document.objects.all()  # Only current tenant's documents
        all_docs = Document.all_objects.all()  # All documents (admin only)
    """

    def get_queryset(self):
        """
        Return queryset filtered by current tenant context.

        Returns:
            QuerySet: Filtered by tenant_id if tenant context is set,
                     otherwise returns empty queryset (security by default).
        """
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return super().get_queryset().filter(tenant_id=tenant_id)

        # Return empty queryset if no tenant context (security by default)
        # This prevents accidental data leaks when tenant context is missing
        return super().get_queryset().none()


class ModelWithOwner(models.Model):
    """
    Abstract base model with owner and tenant_id fields.

    Provides:
        - owner: Optional ForeignKey to User
        - tenant_id: Required UUID field for tenant isolation
        - objects: TenantManager for automatic tenant filtering
        - all_objects: Standard manager that bypasses tenant filtering

    The tenant_id is automatically populated from thread-local storage on save.
    All queries using the default 'objects' manager are automatically filtered
    by the current tenant context.

    Tenant Isolation:
        - Default 'objects' manager uses TenantManager (automatic filtering)
        - 'all_objects' manager bypasses filtering (for admin operations)
        - tenant_id auto-populated from current tenant context on save
        - Raises ValueError if saved without tenant_id

    Example:
        class Document(ModelWithOwner):
            title = models.CharField(max_length=200)

        # Automatic tenant filtering
        set_current_tenant_id(tenant.id)
        docs = Document.objects.all()  # Only current tenant's documents

        # Bypass filtering (admin only)
        all_docs = Document.all_objects.all()  # All documents
    """

    # Tenant-aware manager (default) - automatically filters by current tenant
    objects = TenantManager()

    # Bypass manager - returns all objects regardless of tenant (admin/superuser only)
    all_objects = models.Manager()

    owner = models.ForeignKey(
        User,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name=_("owner"),
    )

    tenant_id = models.UUIDField(
        db_index=True,
        verbose_name=_("tenant"),
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Override save to auto-populate tenant_id from thread-local storage.

        Raises:
            ValueError: If tenant_id is None after attempting auto-population.

        Note:
            Explicitly set tenant_id values are preserved and not overridden.
        """
        # Auto-populate tenant_id if not set
        if self.tenant_id is None:
            self.tenant_id = get_current_tenant_id()

        # Raise error if tenant_id is still None
        if self.tenant_id is None:
            raise ValueError(
                f"tenant_id cannot be None for {self.__class__.__name__}. "
                f"Set tenant_id explicitly or use set_current_tenant_id()."
            )

        super().save(*args, **kwargs)
