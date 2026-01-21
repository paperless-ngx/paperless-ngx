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

#### TenantManager: Automatic Query Filtering

All models inheriting from `ModelWithOwner` use `TenantManager` for automatic tenant isolation:

```python
from documents.models.base import ModelWithOwner, TenantManager

class Document(ModelWithOwner):
    title = models.CharField(max_length=255)
    content = models.TextField()

    # Tenant-aware: Automatically filters by current tenant
    objects = TenantManager()

    # Bypass filtering (use with caution!)
    all_objects = models.Manager()
```

**How it works:**

1. TenantMiddleware sets thread-local context via `set_current_tenant_id(tenant_id)`
2. TenantManager reads thread-local context in `get_queryset()`
3. All queries automatically add WHERE clause: `.filter(tenant_id=current_tenant_id)`
4. If no tenant context is set, returns empty queryset (security by default)

```python
# Automatic filtering example
class DocumentListView(APIView):
    def get(self, request):
        # request.tenant = <Tenant: Acme (acme)>
        # Thread-local storage: tenant_id = <UUID>

        # These queries are automatically filtered by TenantManager
        docs = Document.objects.all()  # Only this tenant's docs
        doc = Document.objects.get(id=123)  # Only searches this tenant's docs

        # To access all tenants (admin/superuser only!)
        all_docs = Document.all_objects.all()  # Unfiltered
```

#### tenant_id Field and Thread-Local Storage

The `ModelWithOwner` base class includes:

```python
class ModelWithOwner(models.Model):
    """Base model for tenant-aware document models."""

    # Tenant reference for data isolation
    tenant_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the tenant that owns this object"
    )

    # Owner of the object
    owner = models.ForeignKey(User, on_delete=models.PROTECT)

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
            raise ValueError("tenant_id must be set before saving")

        super().save(*args, **kwargs)
```

**Key behaviors:**

- `tenant_id` is automatically populated from thread-local storage on save
- `tenant_id` is indexed for query performance and composite key filtering
- Raises `ValueError` if tenant_id is None (prevents orphaned records)
- All related fields (ForeignKey, ManyToMany) inherit tenant filtering through relationships

```python
# Thread-local storage helpers (from documents.models.base)
from documents.models.base import get_current_tenant_id, set_current_tenant_id

# Middleware sets tenant context
set_current_tenant_id(request.tenant_id)  # Called by TenantMiddleware

# Models retrieve context for auto-population
tenant_id = get_current_tenant_id()  # Used in ModelWithOwner.save()

# ORM manager retrieves context for filtering
current_tenant_id = get_current_tenant_id()  # Used in TenantManager.get_queryset()
```

### 2. Database Layer Isolation (Row-Level Security)

PostgreSQL Row-Level Security (RLS) provides database-level defense-in-depth enforcement of tenant isolation. This is the critical security layer that protects against ORM bypasses.

#### How RLS Works

RLS uses PostgreSQL session variables to filter data at the database kernel level:

```sql
-- Middleware sets session variable for each request
SET app.current_tenant = 'acme-tenant-uuid';

-- RLS policy on all tenant-aware tables
CREATE POLICY tenant_isolation_policy ON documents_document
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

-- Force RLS to prevent superuser/admin bypass
ALTER TABLE documents_document FORCE ROW LEVEL SECURITY;
```

**Policy Components:**
- **FOR ALL**: Applies to SELECT, INSERT, UPDATE, and DELETE
- **USING clause**: Filters rows for SELECT/UPDATE/DELETE operations
- **WITH CHECK clause**: Validates rows for INSERT/UPDATE operations
- **FORCE ROW LEVEL SECURITY**: Prevents even superusers from bypassing RLS

#### Tenant-Aware Tables Protected by RLS

Migration 1081 enables RLS on these tables:

| Table | Model | Purpose |
|-------|-------|---------|
| `documents_document` | Document | Primary document records |
| `documents_tag` | Tag | Document categorization tags |
| `documents_correspondent` | Correspondent | External sender/recipient organizations |
| `documents_documenttype` | DocumentType | Document classification types |
| `documents_savedview` | SavedView | User-defined document queries |
| `documents_storagepath` | StoragePath | Document storage locations |
| `documents_paperlesstask` | PaperlessTask | Async task tracking |

#### Benefits

- **Defense-in-Depth**: Protects against ORM filter bypasses via raw SQL
- **Database-Level Enforcement**: Isolation enforced at kernel, not application layer
- **Auditable Security**: All queries respect tenant_id regardless of origin
- **Minimal Performance Impact**: ~1-2% overhead on PostgreSQL per benchmarks
- **Superuser Protection**: FORCE ROW LEVEL SECURITY prevents admin bypasses

#### When RLS Applies

RLS protects all data access:
- Direct SQL queries bypass ORM
- Materialized views and stored procedures
- Database migrations with raw SQL
- Direct database CLI access
- Debugging with psql or database clients
- Any query executed through the database connection

#### Limitations (PostgreSQL Specific)

:::info
RLS is a PostgreSQL 9.5+ feature. Non-PostgreSQL databases (SQLite, MySQL) do not support RLS, so tenant isolation relies solely on application-layer filtering.
:::

```python
# In migration 1081, RLS is skipped for non-PostgreSQL databases
if not is_postgresql(schema_editor):
    return  # Skip RLS setup
```

#### Verifying RLS Status

Check if RLS is enabled and forced on a table:

```sql
-- Check RLS status
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname = 'documents_document';

-- Check if policies exist
SELECT tablename, policyname
FROM pg_policies
WHERE tablename = 'documents_document';
```

Example output:
```
   relname     | relrowsecurity | relforcerowsecurity
-----------------+-----------------+---------------------
documents_document |       t         |         t
```

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

## Database-Level Isolation with Row-Level Security

### Migration 1081: Enable PostgreSQL RLS

The migration file `src/documents/migrations/1081_enable_row_level_security.py` implements database-level tenant isolation:

#### Forward Migration (Enable RLS)

The forward migration runs only on PostgreSQL databases and:

1. **Enables Row-Level Security** on each table
2. **Creates tenant_isolation_policy** with both USING and WITH CHECK clauses
3. **Forces RLS** to prevent superuser/admin bypasses

```python
# Key operations in migration
for table in ['documents_document', 'documents_tag', ...]:
    # Enable RLS
    cursor.execute("ALTER TABLE {} ENABLE ROW LEVEL SECURITY".format(table))

    # Create policy with idempotent DROP+CREATE
    cursor.execute("""
        CREATE POLICY tenant_isolation_policy ON {}
            FOR ALL
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Force RLS (prevent superuser bypass)
    cursor.execute("ALTER TABLE {} FORCE ROW LEVEL SECURITY".format(table))
```

**Safety Features:**
- Idempotent: Drops policy before creating (safe to re-run)
- PostgreSQL-only: Skips for SQLite/MySQL databases
- Connection-specific: `current_setting('app.current_tenant', true)` uses request context

#### Reverse Migration (Disable RLS)

The reverse migration safely disables RLS:

1. **Drops tenant_isolation_policy** from all tables
2. **Disables FORCE RLS** flag
3. **Disables Row-Level Security** entirely

```python
# Reversal operations
for table in ['documents_document', 'documents_tag', ...]:
    cursor.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON {}".format(table))
    cursor.execute("ALTER TABLE {} NO FORCE ROW LEVEL SECURITY".format(table))
    cursor.execute("ALTER TABLE {} DISABLE ROW LEVEL SECURITY".format(table))
```

:::warning
Reversing this migration removes database-level isolation. Use only for migrations to non-PostgreSQL databases.
:::

### Deploying RLS Policies

#### Prerequisites

1. **PostgreSQL 9.5+** installed and running
2. **Database connection** with privileges to modify table policies
3. **All tenants created** before enabling RLS (existing data must have tenant_id)
4. **TenantMiddleware configured** to set PostgreSQL session variables

#### Deployment Steps

```bash
# 1. Verify PostgreSQL version
psql -U postgres -c "SELECT version();"

# 2. Backup database (recommended)
pg_dump -U postgres -d your_db > backup.sql

# 3. Run migration
python manage.py migrate documents

# 4. Verify RLS is enabled
python manage.py shell <<EOF
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT tablename, policyname
        FROM pg_policies
        WHERE tablename LIKE 'documents_%'
    """)
    for row in cursor.fetchall():
        print(f"Table: {row[0]}, Policy: {row[1]}")
EOF

# 5. Test tenant isolation
python manage.py test documents.tests.test_rls_tenant_isolation
```

#### Verification Checklist

- [ ] Migration runs without errors
- [ ] All 7 tables have `tenant_isolation_policy` enabled
- [ ] All 7 tables have RLS forced (`relforcerowsecurity = true`)
- [ ] Tests in `test_rls_tenant_isolation.py` pass
- [ ] Existing data queries return correct tenant isolation
- [ ] Direct SQL queries respect RLS policies
- [ ] Superuser cannot bypass RLS with direct queries

#### Rollback Procedure

If you need to rollback the RLS migration:

```bash
# Reverse the migration
python manage.py migrate documents 1080

# Verify RLS is disabled
psql -U postgres -d your_db -c "
    SELECT relname, relrowsecurity
    FROM pg_class
    WHERE relname LIKE 'documents_%';"

# RLS should show 'f' (false) for relrowsecurity
```

## ModelWithOwner Base Class

The `ModelWithOwner` abstract base class provides automatic tenant isolation for all inherited models:

```python
from documents.models.base import ModelWithOwner, TenantManager

class Document(ModelWithOwner):
    """Document inherits tenant isolation from ModelWithOwner."""
    title = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        verbose_name = "document"
        verbose_name_plural = "documents"
```

**What ModelWithOwner provides:**

| Field | Type | Description | Behavior |
|-------|------|-------------|----------|
| `tenant_id` | UUID | Tenant identifier | Auto-populated from thread-local storage |
| `owner` | ForeignKey | User who owns the object | Explicitly set by application |
| `objects` | TenantManager | Tenant-aware manager | Automatic filtering by current tenant |
| `all_objects` | Manager | Unfiltered manager | Bypasses tenant filtering (admin only) |

**All models inheriting from ModelWithOwner:**

- `Correspondent` - External correspondents
- `Tag` - Document tags with hierarchical support
- `DocumentType` - Document classification types
- `StoragePath` - Document file storage locations
- `Document` - Primary document records
- `SavedView` - User-defined document views
- `PaperlessTask` - Async task tracking

### Data Migration for tenant_id

When upgrading to tenant-aware models, Django migrations automatically handle the schema changes:

```bash
python manage.py migrate documents
```

This runs three migrations in sequence:

1. **Migration 1078**: Add nullable `tenant_id` column
   - Adds `tenant_id` UUIDField with default=None
   - Creates indexes on `tenant_id` and composite `[tenant_id, owner]`
   - Allows existing records to have NULL temporarily

2. **Migration 1079**: Backfill tenant_id with default tenant
   - Creates default tenant if it doesn't exist
   - Associates all existing records with default tenant
   - Ensures backward compatibility with single-tenant data

3. **Migration 1080**: Make tenant_id non-nullable
   - Sets NOT NULL constraint on `tenant_id` column
   - Prevents orphaned records without tenant ownership
   - Enforces tenant isolation at database level

Example migration code:

```python
# Migration 1078: Add nullable tenant_id field
from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='document',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                default=None,
                null=True,  # Temporarily nullable
            ),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['tenant_id'], name='doc_tenant_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(
                fields=['tenant_id', 'owner'],
                name='doc_tenant_owner_idx'
            ),
        ),
    ]

# Migration 1079: Backfill with default tenant
def create_default_tenant(apps, schema_editor):
    Tenant = apps.get_model('paperless', 'Tenant')
    default_tenant, _ = Tenant.objects.get_or_create(
        subdomain='default',
        defaults={'name': 'Default Tenant', 'is_active': True}
    )
    return default_tenant

def backfill_tenant_id(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    default_tenant = create_default_tenant(apps, schema_editor)
    Document.objects.filter(tenant_id__isnull=True).update(
        tenant_id=default_tenant.id
    )

# Migration 1080: Make tenant_id non-nullable
class Migration(migrations.Migration):
    operations = [
        migrations.AlterField(
            model_name='document',
            name='tenant_id',
            field=models.UUIDField(
                db_index=True,
                null=False,  # No longer nullable
            ),
        ),
    ]
```

## Model Patterns

### Pattern 1: Simple Tenant Ownership

Models owned by a tenant with automatic filtering via ModelWithOwner:

```python
from documents.models.base import ModelWithOwner, TenantManager

class Document(ModelWithOwner):
    """Document with tenant isolation from ModelWithOwner."""
    title = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        verbose_name = "document"
        verbose_name_plural = "documents"

# Usage
doc = Document.objects.get(id=123)  # Automatically filtered by current tenant
# SELECT * FROM document WHERE id=123 AND tenant_id=<current_tenant_id>

# Access all documents (admin only!)
all_docs = Document.all_objects.all()  # No tenant filtering
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

## Migration Sequence and Data Consistency

Understanding the migration sequence is important for understanding how RLS integrates with tenant isolation:

### Complete Migration Sequence

| Migration | Purpose | Tenant Isolation Method |
|-----------|---------|------------------------|
| **1078** | Add nullable `tenant_id` field | Application-level (manual filters) |
| **1079** | Backfill with default tenant | Application-level (manual filters) |
| **1080** | Make `tenant_id` non-nullable | Application-level (ORM filtering) |
| **1081** | Enable PostgreSQL RLS policies | **Database-level + Application-level (Defense-in-depth)** |

### Data Consistency Guarantees

```
Before Migration 1081:
┌─────────────────────────────────┐
│ Data without tenant_id          │
│ (Single-tenant or insecure)     │
└─────────────────────────────────┘
         ↓ Run Migrations 1078-1080
┌─────────────────────────────────┐
│ Data with tenant_id field       │
│ (Tenant isolation via ORM)      │
└─────────────────────────────────┘
         ↓ Run Migration 1081
┌─────────────────────────────────┐
│ Data with RLS policies enforced │
│ (Defense-in-depth isolation)    │
└─────────────────────────────────┘
```

### Testing Multi-Layer Isolation

After deployment, verify the three isolation layers work together:

```python
from django.test import TestCase, TransactionTestCase
from documents.models import Document
from documents.models.base import set_current_tenant_id
from paperless.models import Tenant
from django.db import connection

class DefenseInDepthTest(TransactionTestCase):
    """Verify all three isolation layers work correctly."""

    def test_orm_filters_by_default(self):
        """Layer 1: ORM (TenantManager) filters automatically."""
        set_current_tenant_id(self.tenant_a.id)
        doc_a = Document.objects.create(...)

        set_current_tenant_id(self.tenant_b.id)
        # ORM manager blocks access
        assert Document.objects.filter(id=doc_a.id).count() == 0

    def test_rls_prevents_raw_sql_bypass(self):
        """Layer 2: RLS prevents bypassing ORM with raw SQL."""
        set_current_tenant_id(self.tenant_a.id)
        doc_a = Document.objects.create(...)

        # Try to bypass ORM with raw SQL
        set_current_tenant_id(self.tenant_b.id)
        with connection.cursor() as cursor:
            # RLS policy blocks this query
            cursor.execute("SELECT COUNT(*) FROM documents_document")
            count = cursor.fetchone()[0]
            assert count == 0  # RLS prevented access

    def test_postgresql_session_variable_isolation(self):
        """Layer 3: PostgreSQL session variable enforces tenant context."""
        # Verify that switching tenant_id also switches database context
        set_current_tenant_id(self.tenant_a.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant')")
            tenant = cursor.fetchone()[0]
            assert tenant == str(self.tenant_a.id)
```

## Security Best Practices

### 1. Always Inherit from ModelWithOwner

```python
# ✅ Correct - Inherit from ModelWithOwner for automatic tenant isolation
from documents.models.base import ModelWithOwner

class Document(ModelWithOwner):
    title = models.CharField(max_length=255)
    # Automatically gets:
    # - tenant_id field with auto-population from thread-local
    # - objects = TenantManager() for automatic filtering
    # - all_objects manager for admin access

# ❌ Wrong - Manual tenant field without proper manager
class Document(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    # Missing TenantManager - queries NOT filtered by tenant!
```

### 2. Understanding TenantManager Security

TenantManager implements **security by default**:

```python
from documents.models.base import TenantManager, get_current_tenant_id

class TenantManager(models.Manager):
    def get_queryset(self):
        tenant_id = get_current_tenant_id()

        if tenant_id is None:
            # ⚠️ No tenant context = return EMPTY queryset
            # Prevents accidental data leaks when tenant context is missing
            return super().get_queryset().none()

        # ✅ Tenant context set = filter by tenant
        return super().get_queryset().filter(tenant_id=tenant_id)
```

**Key security properties:**

- **Default to deny**: No tenant context → empty queryset (prevents leaks)
- **Automatic filtering**: Don't need to remember `.filter(tenant_id=...)`
- **Related query filtering**: ForeignKey/ManyToMany inherit filtering
- **Performance**: Single indexed WHERE clause on tenant_id

**Verify tenant context is set:**

```python
from documents.models.base import get_current_tenant_id

# In views/serializers
tenant_id = get_current_tenant_id()
if tenant_id is None:
    raise Exception("No tenant context! TenantMiddleware may not be configured")

# Only safe to query if tenant_id is set
docs = Document.objects.all()
```

### 3. Validate Tenant in Views (Defense in Depth)

```python
# ✅ Correct - TenantManager handles filtering automatically
def get_document(request, doc_id):
    # TenantManager ensures this document belongs to current tenant
    doc = Document.objects.get(id=doc_id)
    return DocumentSerializer(doc).data
    # If doc doesn't exist for current tenant, raises Document.DoesNotExist
```

**Don't need manual tenant validation:**

```python
# ❌ Not necessary - TenantManager guarantees isolation
def get_document(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    if doc.tenant_id != request.tenant_id:  # Redundant!
        raise PermissionDenied()
    return DocumentSerializer(doc).data

# ✅ Trust the ORM manager - it handles it
def get_document(request, doc_id):
    doc = Document.objects.get(id=doc_id)  # Already filtered
    return DocumentSerializer(doc).data
```

### 4. Never Bypass TenantManager Without Good Reason

```python
# ❌ DANGEROUS - Unfiltered access across all tenants
docs = Document.all_objects.all()
for doc in docs:  # Iterates through ALL tenants' documents!
    process(doc)

# ✅ Correct - Use tenant-aware manager
docs = Document.objects.all()  # Automatically filtered

# ✅ If you need admin access, explicitly document it
# ADMIN ONLY: Access all documents across all tenants
@require_superuser
def admin_report(request):
    docs = Document.all_objects.all()  # Explicitly unfiltered
    return render(request, 'admin_report.html', {'docs': docs})
```

### 5. Protect Inactive Tenants

```python
# Middleware automatically blocks inactive tenants (TenantMiddleware)
# Additional safety: Verify at ORM level

# ❌ ANTI-PATTERN: Inactive tenants not protected
Document.objects.all()  # Returns docs from inactive tenant if no tenant context!

# ✅ TenantManager handles this: Empty queryset if no tenant context
# Middleware must set tenant context first, and validate is_active
```

### 6. Audit Tenant-Aware Operations

```python
import logging

logger = logging.getLogger(__name__)

# Log model saves with tenant context
from documents.models.base import get_current_tenant_id

class Document(ModelWithOwner):
    def save(self, *args, **kwargs):
        # Auto-populate tenant_id from thread-local
        super().save(*args, **kwargs)
        logger.info(
            f"Saved document {self.id} for tenant {self.tenant_id}",
            extra={'tenant_id': str(self.tenant_id)}
        )

# Log tenant context changes
class TenantMiddleware:
    def __call__(self, request):
        tenant_id = get_current_tenant_id()
        logger.debug(
            f"Request processed for tenant {tenant_id}",
            extra={'tenant_id': str(tenant_id) if tenant_id else 'None'}
        )
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

## Testing RLS Policies

The test suite in `src/documents/tests/test_rls_tenant_isolation.py` verifies that RLS policies work correctly:

```python
# Key tests verify:
- RLS is enabled and forced on all tenant-aware tables
- tenant_isolation_policy exists on all tables
- Cross-tenant access is blocked at database level
- Direct SQL queries respect RLS policies
- Multiple objects per tenant are isolated correctly
```

To run the RLS tests:

```bash
python manage.py test documents.tests.test_rls_tenant_isolation --verbosity=2
```

## Integration with Multi-Tenant System

The three isolation layers work together:

```
Application Request
    ↓
TenantMiddleware
├─ Resolve tenant from subdomain/header
├─ Set thread-local context
└─ Set PostgreSQL session variable (app.current_tenant)
    ↓
ORM Query (with TenantManager)
├─ Auto-filters by thread-local tenant_id
└─ Sends query to database
    ↓
PostgreSQL Database
├─ Receives query with current_tenant session variable
├─ RLS policy evaluates for each row
├─ Only returns rows where tenant_id matches current_tenant
└─ Result set respects isolation
    ↓
Application receives filtered data
    (Defense-in-depth: multiple layers prevent leaks)
```

## See Also

- [TenantMiddleware and Subdomain Routing](./tenant-middleware-configuration.md) - Request-level tenant resolution
- [Tenant-Aware Models (ModelWithOwner)](../development/tenant-aware-models.md) - Application-layer isolation
- [MinIO Multi-Tenant Storage](./minio-multi-tenant.md) - Per-tenant storage buckets
- [Redis and Celery Configuration](./redis-celery-configuration.md) - Background task tenant context

**Last Updated**: 2026-01-21
