---
sidebar_position: 6
title: Multi-Tenant Architecture
description: Comprehensive overview of multi-tenant design, Tenant model, tenant isolation mechanisms, and implementation patterns
---

# Multi-Tenant Architecture

This document provides a comprehensive overview of Paless's multi-tenant architecture, design principles, and implementation patterns. It covers the Tenant model, isolation mechanisms, and how multi-tenancy integrates with other system components.

## Architecture Overview

Paless implements multi-tenancy using a **segregated database approach** with three complementary isolation layers:

1. **Application Layer**: TenantAwareManager filters all ORM queries automatically
2. **Database Layer**: PostgreSQL Row-Level Security (RLS) policies prevent cross-tenant access
3. **Request Layer**: TenantMiddleware establishes request context and validates tenant access

```
┌─────────────────────────────────────────────────────┐
│         Client Requests (Users)                     │
│  - Web: tenant-a.example.com                        │
│  - API: X-Tenant-ID header                          │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  TenantMiddleware                                   │
│  - Resolve tenant from subdomain/header             │
│  - Validate tenant is active                        │
│  - Set request.tenant context                       │
│  - Set thread-local storage for ORM                 │
│  - Set PostgreSQL session variable for RLS         │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  Application Layer (Views/Serializers)              │
│  - Use TenantAwareManager for queries               │
│  - Automatic WHERE tenant_id = current_tenant      │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  ORM Layer (Django Models)                          │
│  - TenantAwareManager applies filtering             │
│  - ForeignKey to Tenant model                       │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  PostgreSQL Database with RLS                       │
│  - Row-Level Security policies                      │
│  - SET app.current_tenant = tenant_id               │
│  - RLS prevents bypassing ORM filters               │
└─────────────────────────────────────────────────────┘
```

## Tenant Model

The `Tenant` model represents a tenant (organization, account, or instance) in the system:

```python
class Tenant(models.Model):
    """
    Multi-tenant model for subdomain-based tenant isolation.

    Each tenant represents an independent organization or account
    with isolated data and request context.
    """
    # Unique identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Identification
    name = models.CharField(
        max_length=255,
        verbose_name="Tenant Name",
        help_text="Human-readable name for the tenant (e.g., 'Acme Corporation')"
    )

    # Routing
    subdomain = models.CharField(
        max_length=63,
        unique=True,
        db_index=True,
        verbose_name="Subdomain",
        help_text="Unique subdomain for tenant routing (e.g., 'acme')"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this tenant is active and can be accessed"
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        ordering = ["subdomain"]

    def __str__(self):
        return f"{self.name} ({self.subdomain})"
```

### Field Descriptions

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| `id` | UUID | Primary Key | Unique tenant identifier across the system |
| `name` | CharField(255) | Required | Human-readable tenant name for admin UI |
| `subdomain` | CharField(63) | Unique, Indexed | Route tenant requests; must match host subdomain |
| `is_active` | Boolean | Default: True | Disable access without deleting tenant data |
| `created_at` | DateTime | Auto | Audit trail for tenant creation |
| `updated_at` | DateTime | Auto | Audit trail for tenant modifications |

### Subdomain Naming Conventions

Subdomains must follow DNS naming rules and Paless conventions:

- **Allowed**: Lowercase alphanumeric + hyphens: `acme`, `tenant-a`, `customer-123`
- **Not Allowed**: Uppercase, underscores, dots: `Acme`, `tenant_a`, `tenant.a`

```python
# Valid subdomains
Tenant.objects.create(name="Acme Corp", subdomain="acme")
Tenant.objects.create(name="Widget Inc", subdomain="widget-inc")
Tenant.objects.create(name="Customer 123", subdomain="customer-123")

# Invalid subdomains (would fail DNS resolution)
Tenant.objects.create(name="Invalid", subdomain="ACME")  # Uppercase
Tenant.objects.create(name="Invalid", subdomain="acme_corp")  # Underscore
```

## Isolation Mechanisms

### 1. Application Layer Isolation (ORM Filtering)

TenantAwareManager automatically filters all queries to the current tenant:

```python
from documents.managers import TenantAwareManager

class Document(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)

    # Tenant-aware: Automatically filters by current tenant
    objects = TenantAwareManager()

    # Bypass filtering (use with caution!)
    all_objects = models.Manager()
```

**How it works:**

1. TenantMiddleware sets thread-local context: `set_current_tenant(current_tenant)`
2. TenantAwareManager reads thread-local context: `get_current_tenant_id()`
3. All queries automatically add WHERE clause: `.filter(tenant_id=current_tenant.id)`

```python
# Automatic filtering example
class RequestHandler(APIView):
    def get(self, request):
        # request.tenant = <Tenant: Acme (acme)>

        # These queries are automatically filtered
        docs = Document.objects.all()  # Only this tenant's docs
        doc = Document.objects.get(id=123)  # Only searches this tenant

        # To access all tenants (dangerous!)
        all_docs = Document.all_objects.all()  # Unfiltered
```

### 2. Database Layer Isolation (Row-Level Security)

PostgreSQL Row-Level Security provides defense-in-depth:

```sql
-- Set session variable from middleware
SET app.current_tenant = 'acme-tenant-uuid';

-- RLS policy prevents cross-tenant access
CREATE POLICY documents_tenant_isolation
    ON documents.document
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

**Benefits:**
- Prevents ORM filter bypasses via raw SQL
- Enforces isolation at database level
- Auditable security boundary
- Performance: Minimal overhead (one session variable)

**When RLS Applies:**
- Direct SQL queries bypass ORM
- Materialized views or stored procedures
- Database migrations with raw SQL
- Debugging with direct database access

### 3. Request Context Isolation

TenantMiddleware ensures request context is properly scoped:

```python
# In request processing
request.tenant = <Tenant object>
request.tenant_id = <UUID>

# In thread-local storage (for background tasks)
_thread_locals.tenant = <Tenant object>
_thread_locals.tenant_id = <UUID>
```

**Isolation guarantees:**
- Each request has exactly one tenant context
- Background tasks see request tenant
- Database queries use request tenant
- After request completes, context is cleared

## Model Patterns

### Pattern 1: Simple Tenant Ownership

Models owned by a tenant with automatic filtering:

```python
class Document(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()

    objects = TenantAwareManager()
    all_objects = models.Manager()

# Usage
doc = Document.objects.get(id=123)  # Automatically filtered by tenant
# SELECT * FROM document WHERE id=123 AND tenant_id=<current_tenant>
```

### Pattern 2: Tenant Ownership via Parent Model

Models that inherit tenant from parent:

```python
class DocumentTag(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    objects = TenantAwareManager()
    all_objects = models.Manager()

# Usage
# TenantAwareManager filters on document.tenant_id
tag = DocumentTag.objects.filter(name="important").first()
# Filters to current tenant's documents only
```

### Pattern 3: Non-Tenant Models

Models that should be visible to all tenants:

```python
class DocumentTemplate(models.Model):
    """System-wide document template (no tenant_id)"""
    name = models.CharField(max_length=255)
    content = models.TextField()

    objects = models.Manager()  # No TenantAwareManager

# Usage
template = DocumentTemplate.objects.get(name="invoice")
# Not filtered by tenant - same template for all tenants
```

### Pattern 4: Shared Models with Tenant Customization

Models with both shared and per-tenant data:

```python
class Settings(models.Model):
    # Shared system-wide settings
    max_file_size = models.IntegerField()

    objects = models.Manager()

class TenantSettings(models.Model):
    # Per-tenant customization
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    custom_branding = models.JSONField()

    objects = TenantAwareManager()
    all_objects = models.Manager()
```

## Thread-Local Storage

TenantMiddleware uses Python's `threading.local()` to maintain request context:

```python
import threading

# Module-level thread-local storage
_thread_locals = threading.local()

def set_current_tenant(tenant):
    """Set tenant in thread-local storage (called by middleware)."""
    _thread_locals.tenant = tenant
    _thread_locals.tenant_id = tenant.id if tenant else None

def get_current_tenant():
    """Get tenant from thread-local storage (used by ORM manager)."""
    return getattr(_thread_locals, "tenant", None)

def get_current_tenant_id():
    """Get tenant ID from thread-local storage."""
    return getattr(_thread_locals, "tenant_id", None)
```

### Why Thread-Local Storage?

- **Request Isolation**: Each request/thread has its own context
- **ORM Integration**: Managers can access context without passing arguments
- **Background Tasks**: Celery tasks inherit request context
- **Database Queries**: Context available to all query points

### Lifecycle

```
Request arrives
    ↓
TenantMiddleware.__call__()
    ├─ Resolve tenant from subdomain/header
    ├─ set_current_tenant(tenant)  ← Set context
    ├─ Process request (views, serializers access context)
    └─ set_current_tenant(None)  ← Clear context
    ↓
Response returned
```

## Tenant Lifecycle

### Creating a Tenant

```bash
# Option 1: Django admin UI
# Navigate to /admin/paperless/tenant/ and create new tenant

# Option 2: Django shell
python manage.py shell
>>> from paperless.models import Tenant
>>> Tenant.objects.create(
...     name="Acme Corporation",
...     subdomain="acme",
...     is_active=True
... )

# Option 3: Management command (if created)
python manage.py create_tenant --name "Acme" --subdomain "acme"
```

### Activating/Deactivating a Tenant

```python
# Deactivate tenant (blocks all requests with 403)
tenant = Tenant.objects.get(subdomain="acme")
tenant.is_active = False
tenant.save()

# Reactivate tenant
tenant.is_active = True
tenant.save()
```

### Deleting a Tenant

```python
# Option 1: Soft delete (keep data)
tenant.is_active = False
tenant.save()

# Option 2: Hard delete (cascade deletes all tenant data)
tenant.delete()  # Deletes tenant and all related documents, tags, etc.
```

:::danger
Hard deleting a tenant deletes ALL tenant data. Use soft delete (is_active = False) for reversible deactivation.
:::

## Integration Points

### With TenantMiddleware

Automatically resolves and validates tenant:

```python
from paperless.middleware import get_current_tenant_id

def my_view(request):
    tenant = request.tenant  # Set by middleware
    tenant_id = request.tenant_id  # Set by middleware
```

### With ORM Managers

Automatically filters queries:

```python
from documents.managers import TenantAwareManager

class Document(models.Model):
    objects = TenantAwareManager()

# Automatic filtering
docs = Document.objects.all()  # Only current tenant's docs
```

### With PostgreSQL RLS

Enforces isolation at database:

```python
# Middleware sets session variable
cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])

# RLS policies use the variable
# SELECT * FROM document WHERE tenant_id = current_setting('app.current_tenant')
```

### With Celery Tasks

Background tasks inherit request context:

```python
@shared_task
def process_document(doc_id):
    # get_current_tenant() returns request's tenant
    current_tenant_id = get_current_tenant_id()

    # Query automatically filtered
    doc = Document.objects.get(id=doc_id)
```

## Data Isolation Verification

### Verify Application Layer Filtering

```python
# Check that queries are filtered
from django.test import RequestFactory
from paperless.middleware import TenantMiddleware
from documents.models import Document

# Create test data
tenant_a = Tenant.objects.create(name="A", subdomain="a")
tenant_b = Tenant.objects.create(name="B", subdomain="b")

doc_a = Document.objects.create(tenant=tenant_a, title="A's Doc")
doc_b = Document.objects.create(tenant=tenant_b, title="B's Doc")

# Simulate tenant A request
factory = RequestFactory()
request = factory.get("/", HTTP_HOST="a.localhost")
middleware = TenantMiddleware(lambda r: None)
middleware.get_response = lambda r: type('', (), {})()
middleware(request)

# Verify filtering
docs = Document.objects.all()
assert len(docs) == 1
assert docs[0].title == "A's Doc"
```

### Verify Database Layer Isolation

```sql
-- Connect as tenant A
SET app.current_tenant = '<tenant-a-uuid>';
SELECT * FROM document;  -- Only tenant A's docs

-- Connect as tenant B
SET app.current_tenant = '<tenant-b-uuid>';
SELECT * FROM document;  -- Only tenant B's docs
```

## Performance Considerations

### Query Overhead

- **Additional WHERE clause**: Negligible (indexed column)
- **RLS policy evaluation**: ~1-2% overhead (PostgreSQL benchmarks)
- **Thread-local lookup**: O(1) dictionary access

### Optimization Tips

1. **Index tenant columns**: Ensure `tenant_id` is indexed
2. **Use select_related**: Reduce database round-trips
3. **Cache frequently accessed tenants**: Reduce lookups
4. **Monitor slow queries**: Check for missing indexes

### Scaling Considerations

- Each tenant gets independent ORM query
- No single tenant impacts others
- Horizontal scaling: Add more workers
- Database scaling: Use PostgreSQL replication

## Security Best Practices

### 1. Always Use TenantAwareManager

```python
# ✅ Correct
class Document(models.Model):
    objects = TenantAwareManager()

# ❌ Wrong (uses default manager, bypasses filtering)
class Document(models.Model):
    pass  # No TenantAwareManager
```

### 2. Validate Tenant in Views

```python
# ✅ Correct - Verify tenant matches request
def get_document(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    assert doc.tenant == request.tenant  # Extra safety
    return DocumentSerializer(doc).data

# ✅ Also correct - Trust ORM filtering
def get_document(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    return DocumentSerializer(doc).data  # ORM ensures tenant match
```

### 3. Never Bypass TenantAwareManager

```python
# ❌ DANGEROUS - Bypasses tenant filtering
docs = Document.all_objects.all()  # Unfiltered access!

# ✅ Correct - Use tenant-aware manager
docs = Document.objects.all()  # Filtered by tenant
```

### 4. Protect Inactive Tenants

```python
# Middleware automatically blocks inactive tenants
if tenant and not tenant.is_active:
    return HttpResponse("Tenant is inactive", status=403)

# But verify in ORM queries too
class TenantAwareManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            tenant__is_active=True  # Additional safety
        )
```

### 5. Audit Tenant Changes

```python
# Log tenant activation/deactivation
class Tenant(models.Model):
    def save(self, *args, **kwargs):
        if not self.pk:
            logger.info(f"Creating tenant: {self.name} ({self.subdomain})")
        elif self.is_active != self.__dict__.get('is_active'):
            logger.warning(f"Tenant {self.name} access changed to: {self.is_active}")
        super().save(*args, **kwargs)
```

## Migration Guide

### Upgrading Existing Installation

If migrating from single-tenant to multi-tenant:

1. **Run migration**: Add `Tenant` model via `0006_tenant.py`
2. **Create default tenant**: All existing data belongs to default tenant
3. **Populate tenant_id**: Associate existing records with tenant
4. **Register middleware**: Add `TenantMiddleware` to `MIDDLEWARE`
5. **Update models**: Add `TenantAwareManager` to model classes
6. **Configure DNS**: Set up subdomain routing

### Example Migration

```python
# In Django data migration
from django.db import migrations

def create_default_tenant(apps, schema_editor):
    Tenant = apps.get_model('paperless', 'Tenant')
    Tenant.objects.create(
        name="Default",
        subdomain="default",
        is_active=True
    )

def migrate_documents(apps, schema_editor):
    Tenant = apps.get_model('paperless', 'Tenant')
    Document = apps.get_model('documents', 'Document')
    default_tenant = Tenant.objects.get(subdomain='default')

    Document.objects.all().update(tenant=default_tenant)

class Migration(migrations.Migration):
    dependencies = [...]
    operations = [
        migrations.RunPython(create_default_tenant),
        migrations.RunPython(migrate_documents),
    ]
```

## Troubleshooting

### Queries Return Wrong Tenant's Data

**Symptom**: User from Tenant A sees Tenant B's documents

**Diagnosis**:
1. Check if model uses `TenantAwareManager`
2. Verify middleware is registered
3. Check thread-local context: `get_current_tenant_id()`

**Fix**:
1. Add `TenantAwareManager` to model
2. Verify middleware position (after AuthenticationMiddleware)
3. Check RLS policies are enabled

### Cannot Access Tenant Data

**Symptom**: User gets "Object does not exist" error

**Diagnosis**:
1. Verify tenant is active
2. Check tenant is passed in ForeignKey
3. Verify ORM query uses `.filter(tenant=...)`

**Fix**:
1. Activate tenant: `tenant.is_active = True`
2. Create document with correct tenant
3. Use ORM query with explicit tenant filter

### Tenant Middleware Not Filtering

**Symptom**: Middleware processes request but no filtering occurs

**Diagnosis**:
1. Check middleware is registered
2. Verify TenantAwareManager is used
3. Check thread-local storage is set

**Fix**:
1. Add `TenantMiddleware` to `MIDDLEWARE` list
2. Use `TenantAwareManager()` on models
3. Verify `set_current_tenant()` is called

---

## See Also

- [TenantMiddleware and Subdomain Routing](./tenant-middleware-configuration.md) - Request-level tenant resolution
- [PostgreSQL StatefulSet](./postgres-statefulset.md) - RLS policy configuration
- [MinIO Multi-Tenant Storage](./minio-multi-tenant.md) - Per-tenant storage buckets
- [Redis and Celery Configuration](./redis-celery-configuration.md) - Background task tenant context

**Last Updated**: 2026-01-21
