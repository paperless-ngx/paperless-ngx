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
| Medium   | 2 |
| Low      | 2 |
| Info     | 1 |

---

## Deferred Findings by Task

### Task: 9f2eeca4...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Add tenant_id field to Django's User model and filter the UserViewSet to only return users belonging to the current tenant

**Status**: ✅ RESOLVED - All HIGH and MEDIUM severity findings addressed in final revision

| Severity | Category | Description | Location | Status |
|----------|----------|-------------|----------|--------|
| INFO | A01:2021 – Broken Access Control (OWASP) | User tenant isolation uses application-layer filtering only (no PostgreSQL RLS). Future enhancement: Add RLS policies to auth_user and paperless_userprofile tables for defense-in-depth. | `src/paperless/views.py:128-169` | Accepted for dev stage |
| LOW | A09:2021 – Security Logging and Monitoring Failures (OWASP) | Comprehensive audit logging implemented for user access events, but PostgreSQL-level RLS violations cannot be logged without RLS policies. | `src/paperless/views.py:126,142-167,184-189` | Partially addressed |

**Implementation Notes**:
- All acceptance criteria met with comprehensive test coverage (342 lines, 8 test cases)
- Superuser policy explicitly defined (superusers bypass tenant filtering)
- Audit logging implemented for tenant isolation events
- Defensive programming includes null checks for missing UserProfile
- Signal handler includes fallback to default tenant
- See [User Tenant Isolation](./user-tenant-isolation.md) for full documentation

---

### Task: 50709538...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Add tenant_id to Workflow and related models (WorkflowTrigger, WorkflowAction) by changing their bas

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A01:2021 – Broken Access Control (OWASP) | The backfill migration relies on M2M relationships (WorkflowTrigger/WorkflowActi | `src/documents/migrations/1096_backfill_workflow_tenant_id.py:46-72` |
| HIGH | A04:2021 – Insecure Design (OWASP) | RLS policies use current_setting('app.current_tenant', true) with the 'missing_o | `src/documents/migrations/1098_add_rls_policy_for_workflow_models.py:47-48` |
| MEDIUM | A07:2021 – Identification and Authentication Failures (OWASP) | The thread-local tenant context in base.py could be subject to race conditions o | `src/documents/models/base.py:36-64` |
| MEDIUM | A09:2021 – Security Logging and Monitoring Failures (OWASP) | No audit logging or monitoring for tenant context changes, RLS policy violations | `src/documents/models/base.py, src/documents/migrations/1098_add_rls_policy_for_workflow_models.py` |
| LOW | A05:2021 – Security Misconfiguration (OWASP) | Test file imports Tenant model that is used in production but tests don't verify | `src/documents/tests/test_workflow_tenant_isolation.py:33-45` |

