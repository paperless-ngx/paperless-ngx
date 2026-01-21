---
sidebar_position: 8
title: TenantMiddleware and Subdomain Routing
description: Configure TenantMiddleware for subdomain-based multi-tenant isolation and request context injection
---

# TenantMiddleware and Subdomain Routing

This document describes the TenantMiddleware system that enables subdomain-based tenant resolution and automatic request context injection for Paless multi-tenant deployments.

## Overview

TenantMiddleware is a Django middleware that resolves tenants from incoming requests and establishes a request context for tenant isolation. It supports two tenant resolution strategies:

1. **Subdomain Routing** (Primary): Extract tenant from the request subdomain (e.g., `tenant-a.example.com`)
2. **X-Tenant-ID Header** (Fallback): Extract tenant from HTTP header for ingress routing scenarios

This enables:
- Multi-tenant architecture with subdomain-based isolation
- Automatic ORM filtering by tenant (via thread-local storage)
- Row-Level Security (RLS) integration with PostgreSQL
- Support for both direct subdomain requests and ingress routing

## Architecture

### Request Flow

```
Incoming Request
    ↓
TenantMiddleware
    ├─ Extract subdomain from host
    │  (e.g., "tenant-a.example.com" → "tenant-a")
    │  or fallback to X-Tenant-ID header
    ├─ Lookup tenant in database
    ├─ Validate tenant is active
    ├─ Set request.tenant and request.tenant_id
    ├─ Set thread-local context for ORM filtering
    └─ Set PostgreSQL session variable for RLS
         ↓
    Request Handler (with tenant context)
         ↓
    Response
         ↓
    Clean up thread-local storage
```

### Components

#### Tenant Model

The `Tenant` model represents a tenant in the system:

```python
class Tenant(models.Model):
    """Multi-tenant model for subdomain-based tenant isolation."""
    name = models.CharField(max_length=255)  # Human-readable name
    subdomain = models.CharField(max_length=63, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Key Fields:**
- `name`: Human-readable tenant identifier (e.g., "Acme Corporation")
- `subdomain`: Unique subdomain for tenant routing (e.g., "acme")
- `is_active`: Whether the tenant can be accessed (false blocks all requests)
- `created_at`, `updated_at`: Audit timestamps

#### TenantMiddleware

The middleware class that handles tenant resolution:

```python
class TenantMiddleware:
    """
    Middleware to resolve and enforce tenant isolation based on subdomain routing.

    Resolves tenant from:
    1. Subdomain (primary): Extract from request.get_host()
    2. X-Tenant-ID header (fallback): For ingress routing

    Sets:
    - request.tenant: The resolved Tenant object
    - request.tenant_id: The tenant's ID
    - Thread-local storage for ORM filtering
    """
```

#### Thread-Local Storage Helpers

Helper functions manage request context across the application:

```python
def get_current_tenant_id():
    """Get the current tenant ID from thread-local storage."""
    return getattr(_thread_local, "tenant_id", None)

def set_current_tenant_id(tenant_id):
    """Set the current tenant ID in thread-local storage."""
    _thread_local.tenant_id = tenant_id
```

These are used by tenant-aware ORM managers to automatically filter queries by tenant.

:::warning Critical Implementation Detail
The middleware **must use** `set_current_tenant_id()` from `documents.models.base` to share thread-local storage with `TenantManager`. Using a separate `threading.local()` instance will break tenant isolation. See [Thread-Local Tenant Context](../security/thread-local-tenant-context.md) for details.
:::

## Configuration

### 1. Register Middleware

Add `TenantMiddleware` to `MIDDLEWARE` in `settings.py`, positioned **after** `AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'paperless.middleware.TenantMiddleware',  # Add here
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 2. Configure Allowed Hosts

For subdomain routing to work, update `ALLOWED_HOSTS` to accept subdomains:

```python
# Allow all subdomains
ALLOWED_HOSTS = ['*.example.com', 'example.com', 'localhost', '*.localhost']

# For development with ports
ALLOWED_HOSTS = ['*.localhost:*', '127.0.0.1', 'localhost']
```

### 3. Create Tenants

Use the Django admin or management command to create tenants:

```bash
# Via Django shell
python manage.py shell
>>> from paperless.models import Tenant
>>> Tenant.objects.create(name="Acme Corp", subdomain="acme")
>>> Tenant.objects.create(name="Widget Inc", subdomain="widgets")
```

### 4. Configure DNS or Hosts File

For local development, add subdomain entries to `/etc/hosts`:

```
127.0.0.1 localhost
127.0.0.1 tenant-a.localhost
127.0.0.1 tenant-b.localhost
127.0.0.1 acme.localhost
```

For production, configure DNS wildcard records:

```dns
*.example.com  A  203.0.113.1
example.com    A  203.0.113.1
```

## Tenant Resolution

### Subdomain Extraction Logic

The middleware extracts the subdomain from the request host:

1. Get the full host from `request.get_host()` (e.g., `tenant-a.localhost:8000`)
2. Remove port: `tenant-a.localhost`
3. Split by dots: `['tenant-a', 'localhost']`
4. Use first part as subdomain: `tenant-a`

```python
host = request.get_host()  # "tenant-a.localhost:8000"
host_without_port = host.split(":")[0]  # "tenant-a.localhost"
parts = host_without_port.split(".")  # ["tenant-a", "localhost"]
subdomain = parts[0]  # "tenant-a"
```

### Resolution Priority

1. **Subdomain**: If the request has a subdomain, look up the tenant by subdomain
2. **X-Tenant-ID Header**: If no subdomain, check for `X-Tenant-ID` header
3. **No Tenant**: If neither is present, continue without tenant context

### Error Handling

The middleware returns specific HTTP responses for error conditions:

| Condition | Status | Response |
|-----------|--------|----------|
| Subdomain/header present but tenant not found | 403 | "Tenant not found" |
| Tenant exists but is inactive | 403 | "Tenant is inactive" |
| Database/lookup error | 500 | "Internal server error" |

## Usage Examples

### Example 1: Subdomain Routing (Development)

**Request**: `GET http://tenant-a.localhost:8000/documents/`

```python
# In your view/serializer
class DocumentListView(APIView):
    def get(self, request):
        tenant = request.tenant  # <Tenant: Acme Corp (acme)>
        tenant_id = request.tenant_id  # UUID

        # ORM queries automatically filtered by tenant via TenantAwareManager
        docs = Document.objects.all()  # Only this tenant's documents
        return Response(DocumentSerializer(docs, many=True).data)
```

### Example 2: Header-Based Routing (Ingress)

**Request**: `GET http://api.example.com/documents/` with header `X-Tenant-ID: acme-tenant-uuid`

```
GET /documents/ HTTP/1.1
Host: api.example.com
X-Tenant-ID: 550e8400-e29b-41d4-a716-446655440000

→ Middleware resolves tenant by UUID
→ Sets request.tenant and thread-local context
→ ORM automatically filters documents for this tenant
```

### Example 3: Admin/Non-Tenant Requests

**Request**: `GET http://localhost:8000/admin/`

```
Host: localhost
No subdomain, no X-Tenant-ID header
→ request.tenant = None
→ request.tenant_id = None
→ Middleware continues without tenant context
→ Views can handle non-tenant requests (e.g., admin panel)
```

## Integration with ORM

### Tenant-Aware Managers

Models with multi-tenant support use `TenantAwareManager`:

```python
from documents.managers import TenantAwareManager

class Document(models.Model):
    tenant = models.ForeignKey('paperless.Tenant', ...)
    title = models.CharField(...)

    objects = TenantAwareManager()
    all_objects = models.Manager()  # Unfiltered access
```

### Automatic Filtering

Queries are automatically filtered by the current tenant:

```python
# These queries are automatically filtered by current tenant
documents = Document.objects.all()
doc = Document.objects.get(id=123)  # Only searches current tenant's docs

# To bypass filtering (dangerous!)
documents = Document.all_objects.all()
```

The automatic filtering uses the thread-local storage set by the middleware, ensuring tenant isolation even in background tasks.

### Row-Level Security (RLS) Integration

For PostgreSQL deployments, TenantMiddleware sets a session variable that RLS policies use to enforce tenant isolation at the database level:

```python
# In middleware (sets PostgreSQL session variable)
if tenant:
    with connection.cursor() as cursor:
        cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])
```

This variable is used by RLS policies on all tenant-aware tables:

```sql
-- RLS policy (created by Migration 1081)
CREATE POLICY tenant_isolation_policy ON documents_document
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

**How it works:**
1. Middleware sets `app.current_tenant` session variable from resolved tenant
2. All queries use this session variable in RLS filters
3. Database kernel enforces: only return/allow rows where `tenant_id = current_setting('app.current_tenant')`
4. This provides defense-in-depth: even if ORM filter is bypassed, RLS prevents cross-tenant access

**Benefits:**
- Database-level enforcement (not just application-level)
- Protects raw SQL queries, migrations, and direct database access
- Minimal performance overhead (~1-2% per PostgreSQL benchmarks)
- Automatically applied to all RLS-enabled tables
- FORCE ROW LEVEL SECURITY prevents superuser/admin bypass

## Ingress Routing Configuration

For Kubernetes ingress deployments, use header-based tenant resolution instead of subdomains:

### Kubernetes Ingress Example

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: paless-ingress
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: paless
                port:
                  number: 8000
    # Add ingress controller to set X-Tenant-ID header
    # (varies by ingress controller)
```

### Ingress Controller Configuration

Configure your ingress controller to inject the tenant header. Example for NGINX:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: paless-ingress
  annotations:
    nginx.ingress.kubernetes.io/configuration-snippet: |
      # Extract tenant from path/hostname and set header
      set $tenant_id "default-tenant";
      proxy_set_header X-Tenant-ID $tenant_id;
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: paless
                port:
                  number: 8000
```

## Debugging

### Enable Debug Logging

Set `DEBUG = True` in settings to see detailed middleware logs:

```python
LOGGING = {
    'version': 1,
    'loggers': {
        'paperless.middleware': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

### Check Middleware Processing

The middleware logs:
- Tenant resolution from subdomain
- Tenant resolution from header
- Tenant lookup failures
- Inactive tenant access attempts
- Thread-local context setup

Example logs:
```
[INFO] Resolved tenant from subdomain 'acme': Acme Corporation (ID: 550e8400-e29b-41d4-a716-446655440000)
[DEBUG] Request processed for tenant: Acme Corporation (ID: 550e8400-e29b-41d4-a716-446655440000)
[WARNING] Tenant not found for subdomain: invalid-tenant
[WARNING] Attempted access to inactive tenant: Old Corp (ID: ...)
```

## Security Considerations

### Tenant Isolation Enforcement

1. **Application Layer**: TenantAwareManager filters all ORM queries
2. **Database Layer**: Row-Level Security policies (PostgreSQL)
3. **Request Level**: `request.tenant` context available to views

### Inactive Tenant Protection

Inactive tenants are blocked at the middleware level:

```python
if tenant and not tenant.is_active:
    return HttpResponse("Tenant is inactive", status=403)
```

### Header Injection Prevention

In ingress scenarios, validate that the X-Tenant-ID header comes from a trusted source:

```python
# Option 1: Only trust from ingress controller internal network
# Configure at network policy level

# Option 2: Validate header signature
# (requires coordination with ingress controller)
```

## Troubleshooting

### Subdomain Not Resolving

**Problem**: Requests to `tenant-a.localhost:8000` fail with "Tenant not found"

**Solutions**:
1. Check `/etc/hosts` has the subdomain entry
2. Verify the tenant exists in database: `Tenant.objects.filter(subdomain='tenant-a')`
3. Check middleware logging for extraction issues
4. Verify `ALLOWED_HOSTS` includes `*.localhost:*`

### Tenant Not Found on Valid Subdomain

**Problem**: Valid subdomain returns 403 "Tenant not found"

**Solutions**:
1. Check tenant exists: `python manage.py shell` → `Tenant.objects.get(subdomain='acme')`
2. Check tenant is active: `tenant.is_active == True`
3. Check database connectivity in middleware logs
4. Verify subdomain extraction: add debug logging to `__call__` method

### Header Routing Not Working

**Problem**: X-Tenant-ID header is ignored

**Solutions**:
1. Verify header format: Must be `X-Tenant-ID: <uuid>`
2. Check header is present in request: Use browser dev tools
3. Verify tenant UUID is valid in database
4. Check middleware is not matching a subdomain first (subdomain takes priority)

### Cross-Tenant Data Visible

**Problem**: User can see another tenant's documents

**Solutions**:
1. Verify TenantAwareManager is used on all queryable models
2. Check that models reference `Tenant` correctly in ForeignKey
3. Verify RLS policies are enabled (PostgreSQL)
4. Check thread-local context is being set: `get_current_tenant_id()`

## Performance

### Middleware Overhead

- **Subdomain extraction**: O(1) string operations
- **Tenant lookup**: O(1) database query (indexed on subdomain)
- **Thread-local storage**: O(1) dictionary access
- **PostgreSQL RLS**: One SQL SET command

**Impact**: Negligible for typical request processing

### Query Performance

With TenantAwareManager:
- Automatic filtering adds one additional WHERE clause
- No performance penalty vs. manual filtering
- RLS policies may add minimal overhead on PostgreSQL

### Optimization Tips

1. Cache tenant objects if doing frequent lookups
2. Use select_related/prefetch_related to reduce queries
3. Index tenant foreign keys appropriately
4. Monitor slow query logs for cross-tenant issues

## Migration Guide

### Upgrading to TenantMiddleware

If migrating from a non-tenant system:

1. **Add Tenant model**: Run migration `0006_tenant.py`
2. **Create default tenant**: Create a tenant for existing data
3. **Migrate data**: Associate existing data with the default tenant
4. **Register middleware**: Add to `MIDDLEWARE` list
5. **Update ALLOWED_HOSTS**: Support subdomains
6. **Test thoroughly**: Verify tenant isolation works
7. **Deploy**: Use blue-green deployment to verify

### Data Migration Example

```python
# In a Django data migration
from django.db import migrations
from paperless.models import Tenant

def create_default_tenant(apps, schema_editor):
    Tenant.objects.create(
        name="Default",
        subdomain="default",
        is_active=True
    )

def migrate_documents(apps, schema_editor):
    Tenant = apps.get_model('paperless', 'Tenant')
    Document = apps.get_model('documents', 'Document')
    default_tenant = Tenant.objects.get(subdomain='default')

    # Assign all documents to default tenant
    Document.objects.all().update(tenant=default_tenant)

class Migration(migrations.Migration):
    dependencies = [...]

    operations = [
        migrations.RunPython(create_default_tenant),
        migrations.RunPython(migrate_documents),
    ]
```

---

## See Also

- [Thread-Local Tenant Context](../security/thread-local-tenant-context.md) - **Critical**: Shared storage implementation
- [Tenant Model Documentation](./multi-tenant-architecture.md)
- [MinIO Multi-Tenant Storage](./minio-multi-tenant.md)
- [PostgreSQL Row-Level Security](./postgres-statefulset.md)
- [Kubernetes Ingress Configuration](./kubernetes-guide.md)

**Last Updated**: 2026-01-21
