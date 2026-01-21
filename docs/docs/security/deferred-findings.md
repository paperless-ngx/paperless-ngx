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
| High     | 0 |
| Medium   | 0 |
| Low      | 2 |
| Info     | 2 |

---

## Deferred Findings by Task

### Task: 9f2eeca4...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Add tenant_id field to Django's User model and filter the UserViewSet to only return users belonging

**Status**: ✅ HIGH and MEDIUM severity issues resolved

#### Resolved Issues (2026-01-21)

| Severity | Category | Description | Resolution | Commit |
|----------|----------|-------------|------------|--------|
| ~~HIGH~~ | ~~A01:2021 – Broken Access Control~~ | ~~UserViewSet.get_queryset() filters by profile__tenant_id but doesn't handle users without UserProfile~~ | Added `profile__isnull=False` filter to prevent RelatedObjectDoesNotExist errors. Users without profiles are now excluded from results. | src/paperless/views.py:152-155 |
| ~~HIGH~~ | ~~A01:2021 – Broken Access Control~~ | ~~Superuser tenant isolation policy is undefined~~ | Implemented explicit policy: Superusers bypass tenant filtering and can see all users across all tenants. Added audit logging for superuser access. | src/paperless/views.py:136-141 |
| ~~MEDIUM~~ | ~~A01:2021 – Broken Access Control~~ | ~~UserProfile signal handler relies on thread-local storage which could fail in async contexts~~ | Enhanced signal handler with fallback to default tenant and comprehensive error logging. Added defensive checks to prevent profile creation failures. | src/paperless/models.py:379-435 |
| ~~MEDIUM~~ | ~~A09:2021 – Security Logging and Monitoring~~ | ~~No audit logging for tenant isolation events~~ | Added comprehensive audit logging for: user list access (filtered by tenant), superuser bypass events, user creation with tenant assignment, user updates, and failed authorization attempts. | src/paperless/views.py:123-190 |

#### Remaining Issues (Low Priority)

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| LOW | A05:2021 – Security Misconfiguration | TenantMiddleware accepts X-Tenant-ID header as fallback mechanism. While useful for testing, this could potentially be exploited via header injection in production environments. Consider restricting this to non-production environments. | `src/paperless/middleware.py:54-79` |
| LOW | A04:2021 – Insecure Design | UserProfile tenant_id field uses null=False in model definition. Migration 0007 includes data migration to backfill existing users to default tenant, ensuring no NULL values exist. | `src/documents/migrations/1078_add_tenant_id_to_models.py:17, src/paperless/migrations/0007_userprofile.py:49` |
| INFO | A08:2021 – Software and Data Integrity Failures | No database-level Row-Level Security (RLS) enforcement. While middleware sets PostgreSQL session variable (app.current_tenant), PostgreSQL RLS policies are not yet configured. This is defense-in-depth; application-level filtering is currently active. | `src/paperless/middleware.py:100-107` |
| INFO | A09:2021 – Security Logging and Monitoring | Test suite uses HTTP_X_TENANT_ID header for testing but this pattern may leak into production code. Tests are properly isolated and this is acceptable for development stage. | `src/paperless/tests/test_user_tenant_filtering.py:76, 99, 130` |

