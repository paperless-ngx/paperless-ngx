---
sidebar_position: 3
title: Thread-Local Tenant Context
description: Critical implementation details for shared thread-local storage between middleware and ORM managers
keywords: [tenant isolation, thread-local, middleware, TenantManager, bugfix]
---

# Thread-Local Tenant Context: Shared Storage Implementation

## Overview

This document explains the **critical requirement** for shared thread-local storage between `TenantMiddleware` and `TenantManager` to ensure proper tenant isolation in multi-tenant deployments.

:::danger Critical Bug Pattern
Using separate `threading.local()` instances in middleware and ORM managers will **silently break tenant isolation**, allowing potential cross-tenant data access. This bug was discovered and fixed in January 2026.
:::

## The Bug: Separate Thread-Local Storage

### What Went Wrong

Prior to the fix, the system had **two separate** thread-local storage instances:

```python
# ❌ WRONG: In src/paperless/middleware.py (before fix)
import threading
_thread_locals = threading.local()  # Middleware's own storage

def set_current_tenant(tenant):
    _thread_locals.tenant = tenant
    _thread_locals.tenant_id = tenant.id if tenant else None

# ❌ WRONG: In src/documents/models/base.py (separate storage)
import threading
_thread_local = threading.local()  # Different storage instance!

def get_current_tenant_id():
    return getattr(_thread_local, 'tenant_id', None)
```

### Why This Failed

Each `threading.local()` call creates a **separate storage namespace** for the thread. When middleware set tenant context in its own `_thread_locals`, the TenantManager reading from `_thread_local` would **always see None**.

```
Request Flow (BROKEN):
┌─────────────────────────────────────────────────────────────┐
│ 1. Request arrives: GET /api/documents/123/thumb/          │
│    Host: tenant-a.localhost:8000                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. TenantMiddleware extracts subdomain                      │
│    - Resolves: tenant_id = 13 (tenant-a)                    │
│    - Sets: middleware._thread_locals.tenant_id = 13 ❌      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. View calls: Document.objects.get(id=123)                 │
│    - TenantManager calls: get_current_tenant_id()           │
│    - Reads: base._thread_local.tenant_id                    │
│    - Result: None ❌ (different storage!)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Query Result: Empty queryset (security by default)       │
│    - User sees: 404 Not Found ❌                            │
│    - Expected: Document thumbnail from tenant-a             │
└─────────────────────────────────────────────────────────────┘
```

### Impact

This bug affected:
- **Document thumbnails**: `/api/documents/{id}/thumb/` returned 404
- **All tenant-scoped queries**: Any query using `TenantManager` would filter by `tenant_id = None`
- **Silent failure**: No errors logged, just empty results

## The Fix: Shared Thread-Local Storage

### Correct Implementation

The fix ensures middleware and TenantManager **share the same thread-local storage**:

```python
# ✅ CORRECT: Define thread-local storage ONCE in base.py
# File: src/documents/models/base.py
import threading

_thread_local = threading.local()  # Single source of truth

def get_current_tenant_id():
    """Get current tenant ID from shared thread-local storage."""
    return getattr(_thread_local, 'tenant_id', None)

def set_current_tenant_id(tenant_id):
    """Set current tenant ID in shared thread-local storage."""
    _thread_local.tenant_id = tenant_id
```

```python
# ✅ CORRECT: Import and use base.py functions in middleware
# File: src/paperless/middleware.py
from documents.models.base import set_current_tenant_id as set_tenant_id_in_base

class TenantMiddleware:
    def __call__(self, request):
        # ... resolve tenant from subdomain or header ...

        # ✅ Use shared function from base.py
        set_tenant_id_in_base(tenant.id if tenant else None)

        try:
            response = self.get_response(request)
        finally:
            # ✅ Clean up using same shared function
            set_tenant_id_in_base(None)

        return response
```

### Corrected Flow

```
Request Flow (FIXED):
┌─────────────────────────────────────────────────────────────┐
│ 1. Request arrives: GET /api/documents/123/thumb/          │
│    Host: tenant-a.localhost:8000                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. TenantMiddleware extracts subdomain                      │
│    - Resolves: tenant_id = 13 (tenant-a)                    │
│    - Calls: set_tenant_id_in_base(13) ✅                    │
│    - Sets: base._thread_local.tenant_id = 13 ✅             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. View calls: Document.objects.get(id=123)                 │
│    - TenantManager calls: get_current_tenant_id()           │
│    - Reads: base._thread_local.tenant_id                    │
│    - Result: 13 ✅ (same storage!)                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Query Executes:                                          │
│    SELECT * FROM document WHERE id=123 AND tenant_id=13 ✅  │
│    - PostgreSQL RLS also filters by tenant_id=13           │
│    - User sees: Document thumbnail ✅                       │
└─────────────────────────────────────────────────────────────┘
```

## Testing the Fix

### Verification Test

The fix includes a comprehensive test to verify thread-local context sharing:

```python
# File: src/paperless/tests/test_middleware.py
def test_tenant_manager_receives_correct_context(self):
    """
    Test that TenantManager receives tenant context from middleware.

    This test verifies the fix for the bug where middleware used its own
    thread-local storage instead of the one used by TenantManager.
    """
    # Create documents for both tenants
    set_current_tenant_id(self.tenant_a.id)
    doc_a = Document.objects.create(
        title="Document A",
        tenant_id=self.tenant_a.id,
        owner=user,
    )

    set_current_tenant_id(self.tenant_b.id)
    doc_b = Document.objects.create(
        title="Document B",
        tenant_id=self.tenant_b.id,
        owner=user,
    )

    set_current_tenant_id(None)

    # Create request for tenant A
    request = self.factory.get("/", HTTP_HOST="tenant-a.localhost:8000")

    # Create a get_response that queries documents
    def check_tenant_manager(req):
        # Inside request processing, TenantManager should filter by tenant A
        documents = Document.objects.all()
        self.assertEqual(documents.count(), 1)  # Only tenant A's doc
        self.assertEqual(documents.first().id, doc_a.id)
        self.assertEqual(documents.first().title, "Document A")

        # Verify tenant_id matches
        current_tenant_id = get_current_tenant_id()
        self.assertEqual(current_tenant_id, self.tenant_a.id)

        return type('obj', (object,), {'status_code': 200})()

    self.middleware.get_response = check_tenant_manager
    response = self.middleware(request)

    # Verify response was successful
    self.assertEqual(response.status_code, 200)

    # After request, thread-local should be cleaned up
    self.assertIsNone(get_current_tenant_id())
```

### Manual Verification

Test tenant isolation manually:

```bash
# 1. Create test documents for different tenants
python manage.py shell

from documents.models import Document, Tenant
from documents.models.base import set_current_tenant_id
from django.contrib.auth.models import User

user = User.objects.first()

# Create documents
set_current_tenant_id(Tenant.objects.get(subdomain='tenant-a').id)
doc_a = Document.objects.create(title="Tenant A Doc", owner=user)

set_current_tenant_id(Tenant.objects.get(subdomain='tenant-b').id)
doc_b = Document.objects.create(title="Tenant B Doc", owner=user)

set_current_tenant_id(None)
exit()

# 2. Test thumbnail access
# Should succeed (tenant A can see their document):
curl -v http://tenant-a.localhost:8000/api/documents/{doc_a_id}/thumb/

# Should fail 404 (tenant A cannot see tenant B's document):
curl -v http://tenant-a.localhost:8000/api/documents/{doc_b_id}/thumb/
```

## Best Practices

### ✅ DO: Use Shared Thread-Local Functions

```python
# ✅ CORRECT: Import from base.py
from documents.models.base import (
    get_current_tenant_id,
    set_current_tenant_id,
)

class MyMiddleware:
    def __call__(self, request):
        # Use shared function
        set_current_tenant_id(tenant.id)

        try:
            response = self.get_response(request)
        finally:
            set_current_tenant_id(None)

        return response
```

### ❌ DON'T: Create Your Own Thread-Local Storage

```python
# ❌ WRONG: Creating separate thread-local storage
import threading

_my_thread_locals = threading.local()  # Different storage!

def set_tenant(tenant_id):
    _my_thread_locals.tenant_id = tenant_id  # Won't be seen by TenantManager!
```

### ✅ DO: Clean Up Thread-Local Context

```python
# ✅ CORRECT: Always clean up in finally block
set_current_tenant_id(tenant.id)

try:
    response = self.get_response(request)
finally:
    # Always clean up, even if exception occurs
    set_current_tenant_id(None)
```

### ❌ DON'T: Leave Thread-Local Context Set

```python
# ❌ WRONG: Not cleaning up
set_current_tenant_id(tenant.id)
response = self.get_response(request)
# Context leaks to next request in thread pool! 🔥
return response
```

## Architecture Principles

### Single Source of Truth

**Rule**: Thread-local storage for tenant context MUST be defined in **exactly one place**:

- ✅ **Defined in**: `src/documents/models/base.py`
- ✅ **Used by**: Middleware, ORM managers, views, tests
- ❌ **Never**: Create additional `threading.local()` instances for tenant context

### Import Direction

```
┌─────────────────────────────────────────────────────────────┐
│                 documents.models.base.py                    │
│                                                             │
│  _thread_local = threading.local()  ← Single source        │
│                                                             │
│  def get_current_tenant_id(): ...                           │
│  def set_current_tenant_id(tenant_id): ...                  │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Import
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ↓                   ↓                   ↓
┌────────────┐    ┌──────────────┐    ┌──────────────┐
│ Middleware │    │ TenantManager│    │   Views      │
└────────────┘    └──────────────┘    └──────────────┘
```

### Why This Matters

1. **Thread Safety**: Each HTTP request runs in its own thread (or is reused from thread pool)
2. **Isolation**: Thread-local ensures tenant context doesn't leak between requests
3. **Shared State**: Using same storage ensures middleware and ORM see same tenant_id
4. **Clean Separation**: Views don't need to pass tenant_id explicitly

## Debugging Thread-Local Issues

### Symptoms of Broken Thread-Local Sharing

| Symptom | Likely Cause |
|---------|--------------|
| Queries return empty results despite middleware setting tenant | Separate thread-local storage |
| Thumbnails return 404 for valid documents | TenantManager not receiving tenant context |
| `get_current_tenant_id()` returns None in views | Middleware using different storage |
| Tests pass but production fails | Test code sets context correctly, middleware doesn't |

### Debugging Steps

1. **Check thread-local storage identity**:

```python
# In middleware
from documents.models.base import _thread_local as base_thread_local
import paperless.middleware

# Are these the same object?
print(id(base_thread_local))  # Should match
print(id(paperless.middleware._thread_local))  # If exists, BUG!
```

2. **Trace tenant context flow**:

```python
# Add logging
import logging
logger = logging.getLogger(__name__)

# In middleware
set_current_tenant_id(tenant.id)
logger.debug(f"Middleware set tenant_id: {get_current_tenant_id()}")

# In TenantManager.get_queryset()
logger.debug(f"TenantManager sees tenant_id: {get_current_tenant_id()}")

# Should be the same value!
```

3. **Verify imports**:

```bash
# Check middleware imports
grep -n "set_current_tenant_id\|get_current_tenant_id" src/paperless/middleware.py

# Should show:
# from documents.models.base import set_current_tenant_id as set_tenant_id_in_base
```

## Migration Guide

If you have custom middleware or managers that need tenant context:

### Before (Broken)

```python
# ❌ Custom middleware with own thread-local
import threading

_my_thread_local = threading.local()

class MyMiddleware:
    def __call__(self, request):
        _my_thread_local.tenant_id = request.tenant.id
        # ...
```

### After (Fixed)

```python
# ✅ Use shared thread-local from base.py
from documents.models.base import set_current_tenant_id

class MyMiddleware:
    def __call__(self, request):
        set_current_tenant_id(request.tenant.id)

        try:
            response = self.get_response(request)
        finally:
            set_current_tenant_id(None)

        return response
```

## Security Implications

### Defense-in-Depth

The shared thread-local storage is the **first layer** of tenant isolation:

1. **Application Layer** (Thread-local + TenantManager): ✅ Filters queries by tenant_id
2. **Database Layer** (PostgreSQL RLS): ✅ Double-checks tenant_id in SQL

If thread-local sharing is broken:
- ❌ Application layer fails (empty results)
- ✅ Database layer still protects (RLS prevents cross-tenant access)

### Why Both Layers Matter

```python
# Scenario: Thread-local sharing broken

# Application layer
tenant_id = get_current_tenant_id()  # Returns None (bug!)
docs = Document.objects.all()  # Returns empty queryset (security by default)

# But if using all_objects bypass:
docs = Document.all_objects.get(id=123)  # Would bypass TenantManager
# PostgreSQL RLS still enforces: WHERE tenant_id = current_setting('app.current_tenant')::uuid
# ✅ Query filtered by database layer
```

**Defense-in-depth**: Even with application layer bugs, database RLS prevents cross-tenant access.

## Related Changes

The fix included several related updates:

1. **Middleware** (`src/paperless/middleware.py:8,97,113`):
   - Import `set_current_tenant_id` from `documents.models.base`
   - Remove middleware's own thread-local storage
   - Use shared function for setting/clearing context

2. **Tests** (`src/paperless/tests/test_middleware.py:232-293`):
   - New test: `test_tenant_manager_receives_correct_context()`
   - Verifies `Document.objects.all()` correctly filtered by tenant
   - Confirms thread-local cleanup after request

3. **Kubernetes Deployments** (`k8s/base/*.yaml`):
   - Updated to use latest image tag
   - Fixed health check probes (no longer require X-Tenant-ID header)

## See Also

- [TenantMiddleware Configuration](../deployment/tenant-middleware-configuration.md) - Middleware setup and routing
- [Tenant-Aware Models](../development/tenant-aware-models.md) - ModelWithOwner and TenantManager usage
- [Multi-Tenant Isolation](./tenant-isolation.md) - Overall architecture and security model
- [PostgreSQL RLS](../deployment/postgres-statefulset.md) - Database-layer isolation

## Summary

:::tip Key Takeaways
1. **Never create separate `threading.local()` instances** for tenant context
2. **Always import** `get_current_tenant_id()` and `set_current_tenant_id()` from `documents.models.base`
3. **Always clean up** thread-local context in `finally` blocks
4. **Test with** `test_tenant_manager_receives_correct_context()` pattern
5. **Remember**: This is defense-in-depth — PostgreSQL RLS provides backup protection
:::

**Bug Fix Reference**: Commit 232aae117 (January 2026)
**Related Task**: 92b83a10-a7fa-4327-aee5-baa0e82e3991

---

**Last Updated**: 2026-01-21
