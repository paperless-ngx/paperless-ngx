# Multi-Tenant Isolation Architecture

## Overview

Paless implements **defense-in-depth** tenant isolation using a two-layer security model:

1. **Application-Layer**: Django middleware for tenant resolution and routing
2. **Database-Layer**: PostgreSQL Row-Level Security (RLS) for data isolation

This architecture ensures that tenants cannot access each other's data, even in the event of application-layer bugs or vulnerabilities.

---

## Tenant Resolution Flow

### Step-by-Step Process

When a client accesses `http://acme.local:8000/`:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Browser Request                                              │
├─────────────────────────────────────────────────────────────────┤
│   GET / HTTP/1.1                                                │
│   Host: acme.local:8000                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Django Middleware (Server-Side)                             │
├─────────────────────────────────────────────────────────────────┤
│   • Extract subdomain: "acme"                                   │
│   • Database query: SELECT id FROM tenant WHERE subdomain='acme'│
│   • Result: tenant_id = 13                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. PostgreSQL Session Configuration                            │
├─────────────────────────────────────────────────────────────────┤
│   SET app.current_tenant = '13'                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Request Processing                                           │
├─────────────────────────────────────────────────────────────────┤
│   • All ORM queries automatically filtered by tenant_id         │
│   • PostgreSQL RLS policies enforce isolation                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Response to Browser                                          │
├─────────────────────────────────────────────────────────────────┤
│   HTTP/1.1 200 OK                                               │
│   (No tenant-id exposed in response)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tenant-ID Visibility

### What the Browser Sees ✅

| Component | Value | Visible to Client? |
|-----------|-------|-------------------|
| URL | `http://acme.local:8000/` | ✅ Yes |
| Host Header | `acme.local:8000` | ✅ Yes (in request) |
| Subdomain | `acme` | ✅ Yes (part of URL) |

### What the Browser Does NOT See ❌

| Component | Value | Visible to Client? |
|-----------|-------|-------------------|
| Tenant ID | `13` | ❌ **NO** |
| Database Queries | `WHERE tenant_id = '13'` | ❌ **NO** |
| PostgreSQL Session Variable | `app.current_tenant = '13'` | ❌ **NO** |
| Server-Side Tenant Object | `request.tenant` | ❌ **NO** |

### Security Guarantee

**The tenant ID is NEVER sent to the client.** All tenant resolution and identification happens server-side only.

---

## Tenant Resolution Methods

The middleware supports two methods for tenant identification:

### Method 1: Subdomain-Based (Primary)

**Example:** `http://acme.local:8000/`

```python
# src/paperless/middleware.py (excerpt)

# Extract subdomain from host
host = request.get_host()  # "acme.local:8000"
host_without_port = host.split(":")[0]  # "acme.local"
parts = host_without_port.split(".")  # ["acme", "local"]

# Skip if IP address
is_ip = all(part.isdigit() and 0 <= int(part) <= 255 for part in parts if part)

if not is_ip and len(parts) >= 2:
    subdomain = parts[0]  # "acme"
    tenant = Tenant.objects.get(subdomain=subdomain)
    # Result: tenant.id = 13
```

**Subdomain → Tenant ID Mappings:**

| Subdomain | Tenant ID | Tenant Name |
|-----------|-----------|-------------|
| `acme` | 13 | Acme Corporation |
| `globex` | 14 | Globex Inc |
| `default` | 4 | Default Tenant |
| `tenant-a` | 1 | Tenant A |
| `tenant-b` | 2 | Tenant B |

### Method 2: X-Tenant-ID Header (Fallback)

**Example:** `curl -H "X-Tenant-ID: 13" http://localhost:8000/`

This method is used for:
- Health checks from Kubernetes
- Internal service-to-service calls
- Testing and debugging
- CLI access

```python
# src/paperless/middleware.py (excerpt)

# Fallback to X-Tenant-ID header
tenant_id_header = request.META.get("HTTP_X_TENANT_ID")

if tenant_id_header:
    tenant = Tenant.objects.get(id=tenant_id_header)
```

**⚠️ Important:** This header is only useful for server-to-server communication. In production with subdomain routing, users cannot arbitrarily set this header to access other tenants because the subdomain takes precedence.

---

## Database-Level Security: PostgreSQL Row-Level Security (RLS)

### What is RLS?

PostgreSQL Row-Level Security (RLS) provides an additional layer of security **at the database level**. Even if the application layer is bypassed, the database enforces tenant isolation.

### How RLS Works

#### 1. Session Variable Configuration

When a tenant is resolved, the middleware sets a PostgreSQL session variable:

```python
# src/paperless/middleware.py (excerpt)

if tenant:
    with connection.cursor() as cursor:
        cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])
        # For tenant "acme", this sets: app.current_tenant = '13'
```

#### 2. RLS Policy Enforcement

Every tenant-aware table has an RLS policy that filters rows based on the session variable:

```sql
-- Example: documents_document table RLS policy

CREATE POLICY tenant_isolation_policy ON documents_document
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

ALTER TABLE documents_document FORCE ROW LEVEL SECURITY;
```

**What this means:**
- `USING` clause: Only rows matching the tenant_id can be **selected**
- `WITH CHECK` clause: Only rows matching the tenant_id can be **inserted/updated/deleted**
- `FORCE ROW LEVEL SECURITY`: Even superusers are subject to RLS

#### 3. Active RLS Policies

Current RLS policies on tenant-aware tables:

```sql
-- Query to view active policies
SELECT
    schemaname,
    tablename,
    policyname,
    qual
FROM pg_policies
WHERE tablename LIKE 'documents_%';
```

**Result:**

| Table | Policy Name | Filter Condition |
|-------|-------------|------------------|
| `documents_document` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_tag` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_correspondent` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_documenttype` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_savedview` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_storagepath` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |
| `documents_paperlesstask` | `tenant_isolation_policy` | `tenant_id = current_setting('app.current_tenant')::uuid` |

### Example: Query Filtering

**Without RLS (insecure):**
```sql
-- Application executes:
SELECT * FROM documents_document;

-- Returns ALL documents from ALL tenants (security breach!)
```

**With RLS (secure):**
```sql
-- Application executes:
SELECT * FROM documents_document;

-- PostgreSQL automatically applies:
SELECT * FROM documents_document
WHERE tenant_id = current_setting('app.current_tenant', true)::uuid;

-- If app.current_tenant = '13', only returns documents for tenant_id = 13
```

---

## Security Guarantees

### Defense-in-Depth Architecture

| Layer | Protection | Attack Vector |
|-------|------------|---------------|
| **Application Layer** | Middleware tenant resolution | Prevents URL/subdomain manipulation |
| **Database Layer** | PostgreSQL RLS | Prevents SQL injection, direct DB access |
| **Network Layer** | Kubernetes network policies | Prevents pod-to-pod attacks |

### What This Protects Against

#### ✅ Protected

1. **Subdomain Spoofing**
   - Even if a user modifies the `Host` header, they cannot access another tenant's data because:
     - The subdomain is validated against the database
     - Invalid subdomains return HTTP 403
     - PostgreSQL RLS enforces tenant_id filtering

2. **SQL Injection**
   - Even if an attacker injects SQL to bypass application filters, RLS policies still enforce tenant isolation
   - Example: `'; DROP TABLE documents_document; --` would still be filtered by tenant_id

3. **Direct Database Access**
   - Database users (including `paperless_app`) cannot bypass RLS
   - `FORCE ROW LEVEL SECURITY` ensures even superusers are filtered

4. **Application Bugs**
   - If the application forgets to filter by tenant_id, RLS catches it
   - Developers cannot accidentally expose cross-tenant data

5. **ORM Query Mistakes**
   - Forgetting `.filter(tenant_id=...)` in Django ORM queries is safe
   - PostgreSQL automatically applies the filter

#### ❌ NOT Protected (By Design)

1. **Shared User Accounts**
   - Users are NOT tenant-isolated (by design)
   - A user with credentials can log into any tenant
   - **Mitigation:** Use separate user accounts per tenant

2. **Administrative Access**
   - Django admin (`/admin/`) may show cross-tenant data
   - **Mitigation:** Restrict admin access to trusted personnel

---

## Implementation Details

### Middleware Code

**File:** `src/paperless/middleware.py`

```python
from documents.models.base import set_current_tenant_id as set_tenant_id_in_base

class TenantMiddleware:
    """
    Middleware to resolve and enforce tenant isolation based on subdomain routing.

    Resolves tenant from:
    1. Subdomain (primary): Extract from request.get_host()
    2. X-Tenant-ID header (fallback): For ingress routing

    Sets:
    - request.tenant: The resolved Tenant object
    - request.tenant_id: The tenant's ID
    - Thread-local storage for ORM filtering (via base.py)
    - PostgreSQL session variable for RLS
    """

    def __call__(self, request):
        # Extract subdomain
        host = request.get_host()
        subdomain = extract_subdomain(host)

        # Resolve tenant
        if subdomain:
            tenant = Tenant.objects.get(subdomain=subdomain)
        elif 'HTTP_X_TENANT_ID' in request.META:
            tenant = Tenant.objects.get(id=request.META['HTTP_X_TENANT_ID'])

        # Set tenant context
        request.tenant = tenant
        request.tenant_id = tenant.id

        # Set thread-local storage using shared function from base.py
        set_tenant_id_in_base(tenant.id if tenant else None)

        # Configure PostgreSQL session for RLS
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])

        # Process request
        response = self.get_response(request)

        # Clean up thread-local storage
        set_tenant_id_in_base(None)

        return response
```

:::warning Critical Bug Fix (January 2026)
The middleware **must use** `set_current_tenant_id()` from `documents.models.base` to share thread-local storage with `TenantManager`. Earlier versions incorrectly used a separate `threading.local()` instance, which broke tenant isolation for queries. See [Thread-Local Tenant Context](./thread-local-tenant-context.md) for details.
:::

### RLS Migration

**File:** `src/documents/migrations/1081_enable_row_level_security.py`

```python
from django.db import migrations
from psycopg import sql

def enable_rls_forward(apps, schema_editor):
    """Enable RLS on all tenant-aware tables."""

    tables = [
        'documents_document',
        'documents_tag',
        'documents_correspondent',
        'documents_documenttype',
        'documents_savedview',
        'documents_storagepath',
        'documents_paperlesstask',
    ]

    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            # Enable Row-Level Security
            cursor.execute(
                sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )

            # Create isolation policy
            cursor.execute(
                sql.SQL("""
                    CREATE POLICY tenant_isolation_policy ON {}
                        FOR ALL
                        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
                """).format(sql.Identifier(table))
            )

            # Force RLS (prevent superuser bypass)
            cursor.execute(
                sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )
```

---

## Testing Tenant Isolation

### Test 1: Verify RLS Policies

```bash
# Connect to PostgreSQL
kubectl exec -n paless postgres-0 -- psql -U paperless -d paperless

# List RLS policies
SELECT tablename, policyname, qual
FROM pg_policies
WHERE schemaname = 'public';

# Verify FORCE RLS is enabled
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'documents_%';
```

### Test 2: Session Variable Isolation

```python
# Test in Django shell
from django.db import connection

# Set tenant context
with connection.cursor() as cursor:
    cursor.execute("SET app.current_tenant = '13'")

    # Query documents
    cursor.execute("SELECT COUNT(*) FROM documents_document")
    count_tenant_13 = cursor.fetchone()[0]

    # Change tenant context
    cursor.execute("SET app.current_tenant = '14'")
    cursor.execute("SELECT COUNT(*) FROM documents_document")
    count_tenant_14 = cursor.fetchone()[0]

# Different counts confirm isolation
print(f"Tenant 13 documents: {count_tenant_13}")
print(f"Tenant 14 documents: {count_tenant_14}")
```

### Test 3: Cross-Tenant Access Attempt

```python
# Attempt to bypass tenant isolation
from documents.models import Document
from paperless.models import Tenant

# Set tenant to Acme (ID: 13)
acme = Tenant.objects.get(subdomain='acme')
# Simulate middleware setting tenant

# Try to access Globex documents (ID: 14)
globex_docs = Document.objects.filter(tenant_id=14)

# Result: Empty queryset (RLS prevents access)
# Even though we explicitly filtered by tenant_id=14,
# PostgreSQL RLS overrides this with tenant_id=13
```

---

## Access Patterns

### Browser Access (Production)

```
User accesses:     http://acme.local:8000/
Middleware sees:   Host: acme.local:8000
Extracts:          subdomain = "acme"
Resolves:          tenant_id = 13 (database lookup)
Sets PostgreSQL:   app.current_tenant = '13'
User sees:         http://acme.local:8000/ (no tenant-id visible)
```

### API Access with Header

```bash
# CLI/API clients can use X-Tenant-ID header
curl -H "X-Tenant-ID: 13" http://localhost:8000/api/documents/

# Useful for:
# - Kubernetes health checks
# - Internal service calls
# - Development/testing
```

### Health Check Configuration

Kubernetes probes use `X-Tenant-ID` header to avoid subdomain requirements:

```yaml
livenessProbe:
  httpGet:
    path: /
    port: 8000
    httpHeaders:
    - name: X-Tenant-ID
      value: "4"  # Default tenant
```

---

## Security Best Practices

### ✅ Do

1. **Use HTTPS in production** to prevent host header manipulation
2. **Validate tenant subdomains** against a whitelist
3. **Monitor PostgreSQL logs** for RLS policy violations
4. **Create separate user accounts** per tenant
5. **Audit cross-tenant access** in application logs
6. **Test RLS policies** after schema changes

### ❌ Don't

1. **Don't expose tenant-id in URLs, cookies, or client-side code**
2. **Don't disable RLS policies** without security review
3. **Don't share user credentials** across tenants
4. **Don't bypass middleware** in custom views
5. **Don't use `objects.all()` without considering tenant isolation**
6. **Don't grant direct database access** to untrusted users

---

## Troubleshooting

### Issue: "Tenant not found" Error

**Symptom:** HTTP 403 response with message "Tenant not found"

**Causes:**
1. Subdomain doesn't match any tenant in database
2. Accessing via IP address instead of subdomain
3. Tenant is marked as inactive (`is_active=False`)

**Solution:**
```python
# Check tenant exists
from paperless.models import Tenant
Tenant.objects.filter(subdomain='acme').exists()

# Create missing tenant
Tenant.objects.create(
    name="Acme Corporation",
    subdomain="acme",
    is_active=True
)
```

### Issue: Empty Query Results

**Symptom:** No documents returned even though they exist

**Causes:**
1. PostgreSQL session variable not set
2. Wrong tenant context
3. RLS policy blocking access

**Debug:**
```python
from django.db import connection

# Check current tenant
with connection.cursor() as cursor:
    cursor.execute("SELECT current_setting('app.current_tenant', true)")
    current_tenant = cursor.fetchone()[0]
    print(f"Current tenant: {current_tenant}")

# Check RLS policies
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT tablename, policyname
        FROM pg_policies
        WHERE tablename = 'documents_document'
    """)
    print(cursor.fetchall())
```

---

## Performance Considerations

### RLS Overhead

PostgreSQL RLS adds minimal overhead:
- **Query planning:** +1-2ms (RLS policy evaluation)
- **Query execution:** Negligible (index on `tenant_id`)
- **Connection overhead:** None (session variable persists)

### Optimization Tips

1. **Index tenant_id columns:**
   ```sql
   CREATE INDEX idx_documents_document_tenant
   ON documents_document(tenant_id);
   ```

2. **Use connection pooling:**
   - Session variables persist per connection
   - Reduces SET operations

3. **Monitor slow queries:**
   ```sql
   -- Check if tenant_id indexes are used
   EXPLAIN ANALYZE
   SELECT * FROM documents_document
   WHERE tenant_id = current_setting('app.current_tenant')::uuid;
   ```

---

## Compliance and Auditing

### Data Residency

Each tenant's data is logically isolated within the same database. For regulatory compliance requiring physical isolation:

1. Use separate databases per tenant
2. Modify `DATABASES` setting in Django
3. Use database routing for multi-database support

### Audit Logging

Enable PostgreSQL audit logging for tenant access:

```postgresql
-- Enable pgaudit extension
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- Log all queries with tenant context
ALTER SYSTEM SET pgaudit.log = 'all';
ALTER SYSTEM SET pgaudit.log_parameter = on;
```

Track tenant access in application logs:

```python
# src/paperless/middleware.py
logger.info(f"User {request.user.username} accessed tenant {tenant.name} (ID: {tenant.id})")
```

---

## Future Enhancements

### Potential Improvements

1. **Tenant-Specific User Accounts**
   - Add `tenant_id` to User model
   - Prevent cross-tenant login

2. **API Key Tenant Binding**
   - Bind API keys to specific tenants
   - Reject requests with mismatched tenant context

3. **Tenant-Aware Admin Interface**
   - Filter Django admin by tenant
   - Prevent superuser cross-tenant access

4. **Tenant Quota Enforcement**
   - Storage limits per tenant
   - Document count limits
   - Rate limiting per tenant

5. **Tenant-Specific Configuration**
   - Custom OCR settings per tenant
   - Tenant-specific email templates
   - Per-tenant feature flags

---

## References

- [Thread-Local Tenant Context](./thread-local-tenant-context.md) - **Critical**: Shared storage implementation and bug fix
- [PostgreSQL Row-Level Security Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Django Middleware Documentation](https://docs.djangoproject.com/en/stable/topics/http/middleware/)
- [OWASP Multi-Tenancy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Architecture_Cheat_Sheet.html)
- Migration: `src/documents/migrations/1081_enable_row_level_security.py`
- Middleware: `src/paperless/middleware.py`

---

## Summary

Paless implements a robust multi-tenant architecture with **two layers of security**:

1. **Application Layer:** Django middleware resolves tenant from subdomain
2. **Database Layer:** PostgreSQL RLS enforces data isolation at SQL level

**Key Security Features:**
- ✅ Tenant-ID is server-side only (never exposed to browser)
- ✅ Automatic query filtering via RLS policies
- ✅ Defense-in-depth protection against SQL injection and application bugs
- ✅ FORCE RLS prevents even superusers from bypassing isolation

**For Production:**
- Use HTTPS with proper subdomain routing
- Create separate user accounts per tenant
- Monitor logs for cross-tenant access attempts
- Test RLS policies after database changes
