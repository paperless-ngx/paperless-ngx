---
sidebar_position: 3
title: Tenant-Aware Models (ModelWithOwner)
description: Comprehensive guide to implementing and working with ModelWithOwner base class for automatic tenant isolation
---

# Tenant-Aware Models (ModelWithOwner)

This guide explains how to work with the `ModelWithOwner` base class for automatic tenant isolation in multi-tenant deployments.

## Overview

`ModelWithOwner` is an abstract base class that provides:

1. **Automatic tenant_id field** - UUID field that identifies the tenant
2. **Automatic owner field** - ForeignKey to Django User
3. **TenantManager** - Auto-filters queries by current tenant
4. **Thread-local integration** - Auto-populates tenant_id from request context
5. **Database indexes** - Optimized queries for tenant + owner patterns

```python
from documents.models.base import ModelWithOwner

class Document(ModelWithOwner):
    """Inherits automatic tenant isolation from ModelWithOwner."""
    title = models.CharField(max_length=255)
    content = models.TextField()
```

## Implementation Details

### ModelWithOwner Definition

```python
# In src/documents/models/base.py
class ModelWithOwner(models.Model):
    """
    Abstract base class for tenant-aware document models.

    Provides:
    - tenant_id: UUID field for tenant isolation
    - owner: User who owns the object
    - objects: TenantManager for automatic filtering
    - all_objects: Standard manager for admin access
    """

    # Tenant identifier - auto-populated from thread-local context
    tenant_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the tenant that owns this object"
    )

    # Owner user
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        help_text="The user who owns this object"
    )

    # Managers
    objects = TenantManager()  # Tenant-aware queries
    all_objects = models.Manager()  # Unfiltered (admin only)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['tenant_id', 'owner']),
        ]

    def save(self, *args, **kwargs):
        """Auto-populate tenant_id from thread-local context."""
        if self.tenant_id is None:
            self.tenant_id = get_current_tenant_id()

        if self.tenant_id is None:
            raise ValueError(
                "tenant_id must be set before saving. "
                "Ensure TenantMiddleware is active and tenant_id "
                "is in thread-local storage."
            )

        super().save(*args, **kwargs)
```

### TenantManager Implementation

```python
# In src/documents/models/base.py
class TenantManager(models.Manager):
    """
    Custom manager that automatically filters queries by current tenant.

    Security Model:
    - If tenant context is set: Returns only current tenant's objects
    - If tenant context is None: Returns empty queryset (security by default)

    This prevents accidental data leaks when tenant context is not established.
    """

    def get_queryset(self):
        """Filter queryset by current tenant context."""
        qs = super().get_queryset()
        tenant_id = get_current_tenant_id()

        if tenant_id is None:
            # Security by default: No tenant context = no data
            return qs.none()

        return qs.filter(tenant_id=tenant_id)
```

### Thread-Local Storage Helpers

```python
# In src/documents/models/base.py
import threading

_thread_local = threading.local()

def get_current_tenant_id():
    """Get the current tenant ID from thread-local storage."""
    return getattr(_thread_local, 'tenant_id', None)

def set_current_tenant_id(tenant_id):
    """Set the current tenant ID in thread-local storage."""
    _thread_local.tenant_id = tenant_id
```

## Models Inheriting from ModelWithOwner

All of these models use automatic tenant isolation:

| Model | Purpose | Filtering |
|-------|---------|-----------|
| `Correspondent` | External organizations | Automatically filtered |
| `Tag` | Document tags (hierarchical) | Automatically filtered |
| `DocumentType` | Document classifications | Automatically filtered |
| `StoragePath` | File storage locations | Automatically filtered |
| `Document` | Primary document records | Automatically filtered |
| `SavedView` | User-defined searches | Automatically filtered |
| `PaperlessTask` | Async task records | Automatically filtered |

## Usage Examples

### Creating Records

```python
from documents.models import Document, Correspondent
from documents.models.base import get_current_tenant_id

# ✅ Correct - tenant_id auto-populated
# Assumes TenantMiddleware has set tenant context
doc = Document.objects.create(
    title="Invoice 2024",
    content="...",
    owner=request.user
    # tenant_id automatically populated from thread-local
)

# ✅ Also correct - explicit tenant_id (rare)
from paperless.models import Tenant

tenant = Tenant.objects.get(subdomain='acme')
with set_tenant_context(tenant.id):
    doc = Document.objects.create(
        title="Invoice 2024",
        content="...",
        owner=request.user
    )

# ❌ Wrong - No tenant context set
# This will raise ValueError: tenant_id must be set before saving
doc = Document(
    title="Invoice 2024",
    content="...",
    owner=request.user
)
doc.save()  # ValueError!
```

### Querying Records

```python
from documents.models import Document

# ✅ Automatic filtering by current tenant
docs = Document.objects.all()
# SELECT * FROM document WHERE tenant_id = <current_tenant_id>

# ✅ Get specific document (from current tenant only)
doc = Document.objects.get(id='550e8400-e29b-41d4-a716-446655440000')
# Filters by both id AND tenant_id

# ✅ Filter documents by custom criteria
docs = Document.objects.filter(title__icontains='invoice')
# Still filtered by tenant_id automatically

# ❌ Cross-tenant access (use all_objects to bypass)
all_docs = Document.all_objects.all()  # Returns from ALL tenants!
# Only use this in admin code with proper authorization
```

### Related Queries

```python
from documents.models import Document, DocumentType, Tag

# Get a document (automatically filtered by tenant)
doc = Document.objects.get(id=doc_id)

# ✅ Related queries inherit tenant filtering
document_type = doc.document_type  # From same tenant only
tags = doc.tags.all()  # Only this tenant's tags

# The ORM automatically adds tenant filtering to related queries
# SELECT * FROM tag WHERE document_id = 123 AND tenant_id = <current_tenant>
```

### Filtering with Owner

```python
from documents.models import Document
from django.contrib.auth.models import User

# ✅ Combine tenant and owner filtering
user = User.objects.get(username='alice')

# Get documents created by a specific user in current tenant
docs = Document.objects.filter(owner=user)
# SELECT * FROM document WHERE tenant_id = <current> AND owner_id = <user_id>

# Multiple criteria still work
docs = Document.objects.filter(
    owner=user,
    document_type__name='Invoice'
)
```

## Integration with TenantMiddleware

The `TenantMiddleware` automatically sets up tenant context for each request:

```python
# In settings.py
MIDDLEWARE = [
    # ... other middleware ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'paperless.middleware.TenantMiddleware',  # Must be after auth middleware
    # ... other middleware ...
]

# In paperless/middleware.py
class TenantMiddleware:
    def __call__(self, request):
        # 1. Extract tenant from subdomain or X-Tenant-ID header
        # 2. Set request.tenant and request.tenant_id
        # 3. Set thread-local context: set_current_tenant_id(tenant_id)
        # 4. Process request (models use this context)
        # 5. Clear context: set_current_tenant_id(None)

        from documents.models.base import set_current_tenant_id

        # Middleware sets tenant context
        if tenant:
            set_current_tenant_id(tenant.id)

        try:
            response = self.get_response(request)
        finally:
            # Always clear context after request
            set_current_tenant_id(None)

        return response
```

## Working with Tenant Context in Views

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from documents.models import Document
from documents.models.base import get_current_tenant_id

class DocumentListView(APIView):
    def get(self, request):
        # TenantMiddleware has already set thread-local context
        tenant_id = get_current_tenant_id()

        if not tenant_id:
            return Response(
                {"error": "No tenant context"},
                status=400
            )

        # Query automatically filtered by tenant
        docs = Document.objects.filter(owner=request.user)

        return Response({
            "tenant_id": str(tenant_id),
            "documents": [
                {"id": str(doc.id), "title": doc.title}
                for doc in docs
            ]
        })

class DocumentDetailView(APIView):
    def get(self, request, doc_id):
        # Get document from current tenant only
        # Raises Document.DoesNotExist if not found
        doc = Document.objects.get(id=doc_id)

        return Response({
            "id": str(doc.id),
            "title": doc.title,
            "tenant_id": str(doc.tenant_id)
        })
```

## Testing with Tenant Context

```python
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from documents.models import Document
from documents.models.base import set_current_tenant_id
from paperless.models import Tenant

class DocumentTestCase(TestCase):
    def setUp(self):
        # Create test tenants
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            subdomain="tenant-a"
        )
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            subdomain="tenant-b"
        )

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )

    def test_document_creation_with_tenant_context(self):
        # Set tenant context for current request
        set_current_tenant_id(self.tenant_a.id)

        try:
            # Create document - tenant_id auto-populated
            doc = Document.objects.create(
                title="Test Doc",
                owner=self.user
            )

            assert doc.tenant_id == self.tenant_a.id
        finally:
            set_current_tenant_id(None)

    def test_tenant_isolation_in_queries(self):
        # Create documents for different tenants
        set_current_tenant_id(self.tenant_a.id)
        try:
            doc_a = Document.objects.create(
                title="Doc A",
                owner=self.user
            )
        finally:
            set_current_tenant_id(None)

        set_current_tenant_id(self.tenant_b.id)
        try:
            doc_b = Document.objects.create(
                title="Doc B",
                owner=self.user
            )
        finally:
            set_current_tenant_id(None)

        # Verify isolation
        set_current_tenant_id(self.tenant_a.id)
        try:
            # Can only see tenant A's documents
            docs = Document.objects.all()
            assert docs.count() == 1
            assert docs[0].id == doc_a.id
        finally:
            set_current_tenant_id(None)

    def test_queryset_empty_without_tenant_context(self):
        # Create a document with tenant context
        set_current_tenant_id(self.tenant_a.id)
        try:
            Document.objects.create(
                title="Test Doc",
                owner=self.user
            )
        finally:
            set_current_tenant_id(None)

        # Query without tenant context
        # Should return empty (security by default)
        set_current_tenant_id(None)
        docs = Document.objects.all()
        assert docs.count() == 0
```

## Data Migration for tenant_id

When upgrading to tenant-aware models, Django runs three migrations:

### Migration 1078: Add nullable tenant_id

```sql
ALTER TABLE document ADD COLUMN tenant_id UUID DEFAULT NULL;
CREATE INDEX doc_tenant_idx ON document(tenant_id);
CREATE INDEX doc_tenant_owner_idx ON document(tenant_id, owner_id);
```

### Migration 1079: Backfill tenant_id

```sql
-- Create default tenant if missing
INSERT INTO paperless_tenant (id, name, subdomain, is_active, created_at, updated_at)
VALUES ('<uuid>', 'Default', 'default', true, NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Assign all documents to default tenant
UPDATE document SET tenant_id = '<default_tenant_uuid>' WHERE tenant_id IS NULL;
```

### Migration 1080: Make tenant_id non-nullable

```sql
ALTER TABLE document ALTER COLUMN tenant_id SET NOT NULL;
```

## Troubleshooting

### ValueError: tenant_id must be set before saving

**Problem**: Getting this error when creating objects

```python
>>> doc = Document.objects.create(title="...", owner=user)
ValueError: tenant_id must be set before saving
```

**Solution**: Ensure TenantMiddleware is active and setting thread-local context

```python
from documents.models.base import get_current_tenant_id

# Check if tenant context is set
tenant_id = get_current_tenant_id()
if not tenant_id:
    # TenantMiddleware not running or not configured
    # Set context manually for testing/management commands
    from documents.models.base import set_current_tenant_id
    set_current_tenant_id('<tenant-id>')
```

### Querying returns no objects

**Problem**: Queries return empty results even though data exists

```python
>>> Document.objects.count()  # Returns 0 even though data exists
```

**Cause**: Tenant context not set or set to wrong tenant

**Solution**: Verify tenant context

```python
from documents.models.base import get_current_tenant_id

print(get_current_tenant_id())  # Should be UUID, not None

# For management commands, set context manually:
from documents.models.base import set_current_tenant_id
set_current_tenant_id('<correct-tenant-uuid>')
```

### Management commands fail with tenant_id errors

**Problem**: Running management commands fails due to tenant context

```bash
$ python manage.py some_command
ValueError: tenant_id must be set before saving
```

**Solution**: Set tenant context in management command

```python
# In management/commands/my_command.py
from django.core.management.base import BaseCommand
from documents.models.base import set_current_tenant_id
from paperless.models import Tenant

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Get default tenant or first tenant
        tenant = Tenant.objects.first()

        # Set context for all operations
        set_current_tenant_id(tenant.id)

        try:
            # Your command logic here
            pass
        finally:
            set_current_tenant_id(None)
```

## Security Considerations

### ✅ DO's

- ✅ Always inherit from `ModelWithOwner` for tenant-aware models
- ✅ Use `objects` manager (TenantManager) for normal queries
- ✅ Rely on automatic tenant filtering
- ✅ Set tenant context in views and management commands
- ✅ Document when using `all_objects` with explanation

### ❌ DON'Ts

- ❌ Don't manually add `.filter(tenant_id=...)` (already handled by TenantManager)
- ❌ Don't use `all_objects` without admin-only authorization
- ❌ Don't query without setting tenant context first
- ❌ Don't bypass TenantManager unless you know why
- ❌ Don't assume tenant_id will be set - handle ValueError

## Performance Tips

1. **Use select_related/prefetch_related** to reduce queries
2. **Index tenant_id and owner** (already done by ModelWithOwner)
3. **Use composite indexes** for common query patterns
4. **Avoid querying all_objects** in production (performance impact)
5. **Monitor slow queries** for missing tenant_id filters

## Database-Level Protection with PostgreSQL RLS

:::info
While TenantManager provides application-level filtering, PostgreSQL Row-Level Security (RLS) provides an additional security layer at the database level. This is important for defense-in-depth.
:::

### How RLS Complements ModelWithOwner

```
Application Layer (TenantManager)
    ↓ Auto-filters queries by thread-local tenant_id
PostgreSQL RLS Layer
    ↓ Double-checks tenant_id column matches session variable
Database Results
    ↓ Defense-in-depth: bypassing one layer is prevented by the other
```

### Enabling RLS on New Models

When creating new tenant-aware models:

1. Inherit from `ModelWithOwner` (provides `tenant_id` field)
2. Run migrations to create the table
3. Add the model's table to Migration 1081 (RLS migration)
4. Or manually enable RLS on the table:

```sql
-- Enable RLS on new table
ALTER TABLE new_model ENABLE ROW LEVEL SECURITY;

-- Create isolation policy
CREATE POLICY tenant_isolation_policy ON new_model
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

-- Force RLS
ALTER TABLE new_model FORCE ROW LEVEL SECURITY;
```

### Non-PostgreSQL Databases

For SQLite/MySQL deployments:
- RLS is not available
- Rely on application-level filtering via TenantManager
- Be extra careful with raw SQL queries (no database-level protection)
- Consider adding audit logging to detect policy bypasses

```python
# Example: Audit raw SQL queries in non-PostgreSQL environments
import logging

logger = logging.getLogger('security')

def audit_raw_query(query):
    logger.warning(
        f"Raw SQL query executed: {query[:100]}...",
        extra={'query_type': 'RAW_SQL'}
    )
```

## See Also

- [Multi-Tenant Architecture](../deployment/multi-tenant-architecture.md) - Overall design with RLS details
- [Database-Level Isolation](../deployment/multi-tenant-architecture.md#database-level-isolation-with-row-level-security) - RLS implementation guide
- [TenantMiddleware Configuration](../deployment/tenant-middleware-configuration.md) - Request routing
- [Security Best Practices](../deployment/multi-tenant-architecture.md#security-best-practices) - Security guidelines
- [RLS Tests](../../src/documents/tests/test_rls_tenant_isolation.py) - Test suite verifying RLS policies

**Last Updated**: 2026-01-21
