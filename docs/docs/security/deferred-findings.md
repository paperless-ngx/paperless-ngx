---
sidebar_position: 99
title: Security Debt Tracker
description: Deferred security findings to address before production
---

# Security Debt Tracker

This document tracks security findings that were deferred during development.
These issues should be addressed before moving to production.

:::caution Security Debt
The findings below represent known security issues that have been accepted
for the current development stage but **must be resolved before production**.
:::

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 2 |
| Medium   | 1 |
| Low      | 2 |
| Info     | 1 |

---

## Deferred Findings by Task

### Task: Multi-Tenant Architecture Implementation (41fae4c5...)

**Date**: 2026-01-21
**Stage**: dev
**Description**: Add tenant_id column to all models inheriting from ModelWithOwner and implement tenant-aware ORM managers

#### Finding 1: Race Condition in TenantMiddleware Cleanup

| | |
|---|---|
| **Severity** | HIGH |
| **Category** | A01:2021 - Broken Access Control |
| **Location** | `src/paperless/middleware.py:136` |
| **Description** | Potential race condition in TenantMiddleware's finally block when clearing thread-local storage. If two requests are processed concurrently on different threads, thread-local cleanup is safe. However, if async/await context switching occurs within a thread, clearing the context could affect sibling tasks. |
| **Impact** | In async deployments, a sibling coroutine could execute with missing tenant context, causing TenantManager to return empty querysets or raise errors. |
| **Mitigation** | Currently, Paless uses synchronous WSGI deployment. For async deployments, migrate to context vars (contextvars module) instead of thread-local storage. |
| **Status** | DEFERRED - Implement for async support |

#### Finding 2: Unrestricted Access via all_objects Manager

| | |
|---|---|
| **Severity** | HIGH |
| **Category** | A01:2021 - Broken Access Control |
| **Location** | `src/documents/models/base.py:147` (ModelWithOwner class), `src/documents/models.py:32-34` (imports) |
| **Description** | The `all_objects` manager provides unfiltered access to all records across all tenants. While necessary for admin operations, this manager can be misused in production code to bypass tenant isolation. |
| **Impact** | Admin code using `Document.all_objects.all()` could expose cross-tenant data in logs, reports, or exports. |
| **Current Implementation** | Both managers exist but `all_objects` is not protected by authorization checks. |
| **Mitigation** | Implementation in `src/documents/models/base.py` includes documentation warnings. Authorization checks must be applied at view/serializer level. |
| **Status** | DEFERRED - Implement role-based access control for all_objects |

```python
# In src/documents/models/base.py (ModelWithOwner)
class ModelWithOwner(models.Model):
    objects = TenantManager()         # ✅ Tenant-aware (filtered)
    all_objects = models.Manager()    # ❌ Unfiltered - admin only!
```

**Required Security Pattern**:
```python
# ✅ REQUIRED: Authorization check before using all_objects
@require_superuser
def admin_export(request):
    # Only superusers can access all_objects
    docs = Document.all_objects.all()  # Exports ALL tenants' data
    return export_as_csv(docs)
```

#### Finding 3: Silent Empty Queryset on Missing Tenant Context

| | |
|---|---|
| **Severity** | MEDIUM |
| **Category** | A09:2021 - Security Logging and Monitoring Failures |
| **Location** | `src/documents/models/base.py:94-105` (TenantManager.get_queryset) |
| **Description** | When tenant context is missing (None), TenantManager silently returns empty queryset without logging or alerts. This "security by default" behavior is safe but lacks visibility into configuration errors. |
| **Current Behavior** |  |
| ```python
# In src/documents/models/base.py (TenantManager)
def get_queryset(self):
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return super().get_queryset().none()  # Silent, no logging
    return super().get_queryset().filter(tenant_id=tenant_id)
``` |
| **Impact** | Silent failures make it hard to detect when TenantMiddleware is misconfigured or not running. |
| **Mitigation** | Implement optional logging in TenantManager when tenant context is missing. |
| **Status** | DEFERRED - Add debug logging for missing tenant context |

#### Finding 4: Implicit Tenant Auto-Population

| | |
|---|---|
| **Severity** | LOW |
| **Category** | A04:2021 - Insecure Design |
| **Location** | `src/documents/models/base.py:163-187` (ModelWithOwner.save) |
| **Description** | ModelWithOwner.save() automatically populates tenant_id from thread-local storage without explicit parameter. Implicit auto-population could be confusing for developers. |
| **Current Implementation** |  |
| ```python
# In src/documents/models/base.py (ModelWithOwner)
def save(self, *args, **kwargs):
    if self.tenant_id is None:
        self.tenant_id = get_current_tenant_id()  # Implicit!
    if self.tenant_id is None:
        raise ValueError(
            f"tenant_id cannot be None for {self.__class__.__name__}. "
            f"Set tenant_id explicitly or use set_current_tenant_id()."
        )
    super().save(*args, **kwargs)
``` |
| **Impact** | Developers may not realize tenant_id is auto-populated, leading to confusion when debugging. |
| **Mitigation** | Documentation and clear error messages explain the auto-population behavior. |
| **Status** | DEFERRED - Consider explicit tenant_id parameter for clarity |

#### Finding 5: Test Code Directly Manipulates Thread-Local Storage

| | |
|---|---|
| **Severity** | LOW |
| **Category** | A09:2021 - Security Logging and Monitoring Failures |
| **Location** | `src/documents/tests/test_tenant_manager.py:51` (test setup/teardown) |
| **Description** | Test code directly calls `set_current_tenant_id()` to manipulate thread-local context. While necessary for testing, this pattern could be replicated in production code. |
| **Impact** | Low - Tests are isolated from production. However, this pattern could be misused in management commands or background tasks. |
| **Mitigation** | Document that `set_current_tenant_id()` should only be used in tests and management commands, never in views. |
| **Status** | DEFERRED - Add explicit developer warnings |

#### Finding 6: Thread-Local Storage Fragility in Async Environments

| | |
|---|---|
| **Severity** | INFO |
| **Category** | A04:2021 - Insecure Design |
| **Location** | `src/documents/models/base.py:36` (thread-local definition), `src/paperless/middleware.py:14` (middleware import) |
| **Description** | The thread-local storage pattern (`threading.local()`) is inherently fragile in async/coroutine environments where multiple coroutines run on the same thread. Python's contextvars module is safer for async. |
| **Current Status** | Not an issue in current WSGI deployment. Will become critical if migrating to async. |
| **Migration Path** | Replace `threading.local()` with `contextvars.ContextVar()` for async support. |
| **Status** | DEFERRED - Implement for async/ASGI support |

**Recommended Refactor**:
```python
# Future: Replace thread-local with context vars
import contextvars

_tenant_context: contextvars.ContextVar = contextvars.ContextVar(
    'tenant_id', default=None
)

def get_current_tenant_id():
    return _tenant_context.get()

def set_current_tenant_id(tenant_id):
    return _tenant_context.set(tenant_id)
```

---

## Summary of Deferred Security Findings

| Finding | Severity | Status | Action Item |
|---------|----------|--------|-------------|
| TenantMiddleware race condition in async | HIGH | DEFERRED | Migrate to contextvars for async/ASGI |
| Unrestricted all_objects access | HIGH | DEFERRED | Implement role-based access control |
| Silent empty queryset on missing tenant | MEDIUM | DEFERRED | Add debug logging to TenantManager |
| Implicit tenant auto-population | LOW | DEFERRED | Consider explicit parameter support |
| Test thread-local manipulation | LOW | DEFERRED | Document usage guidelines |
| Thread-local fragility in async | INFO | DEFERRED | Plan contextvars migration |

All findings are **DEVELOPMENT STAGE** (dev) and must be addressed before production deployment.

