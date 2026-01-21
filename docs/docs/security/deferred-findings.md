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
| Low      | 1 |
| Info     | 0 |

---

## Deferred Findings by Task

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

