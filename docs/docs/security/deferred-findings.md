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
| Info     | 1 |

---

## Deferred Findings by Task

### Task: e239d66d...

**Date**: 2026-01-20
**Stage**: dev
**Description**: Add tenant_id column to all models inheriting from ModelWithOwner and create data migration

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A01:2021 - Broken Access Control (OWASP) | No row-level security enforcement for foreign key relationships. Models like Doc | `src/documents/models.py:206-241` |
| HIGH | A03:2021 - Injection (OWASP) | Data migration uses filter() + update() pattern which is vulnerable to race cond | `src/documents/migrations/1079_create_default_tenant_and_backfill.py:41-47` |
| MEDIUM | A01:2021 - Broken Access Control (OWASP) | ManyToManyField relationships lack tenant isolation. Document.tags, WorkflowActi | `src/documents/models.py:254-259` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures (OWASP) | Missing audit logging for tenant context changes. Thread-local tenant_id changes | `src/documents/models.py:43-50` |
| LOW | A04:2021 - Insecure Design (OWASP) | ModelWithOwner.tenant_id allows null=True in model definition, contradicting the | `src/documents/models.py:63-67` |
| INFO | Security Best Practice | Verification script uses kubectl exec to run Python code in production pods. Whi | `verify_tenant_id_implementation.sh:86-170` |

