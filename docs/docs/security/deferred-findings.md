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

### Task: 41fae4c5...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Implement tenant-aware ORM managers to automatically filter queries by current tenant context

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A01:2021 - Broken Access Control | Race condition in TenantMiddleware cleanup at line 136. The middleware clears th | `src/paperless/middleware.py:136` |
| HIGH | A01:2021 - Broken Access Control | The all_objects manager (line 147 in base.py, line 138 in models.py) provides un | `src/documents/models/base.py:147, src/documents/models.py:138` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | TenantManager silently returns empty queryset when tenant context is missing (li | `src/documents/models/base.py:92-108, src/documents/models.py:92-94` |
| LOW | A04:2021 - Insecure Design | ModelWithOwner.save() auto-populates tenant_id from thread-local storage with im | `src/documents/models/base.py:163-187` |
| LOW | A09:2021 - Security Logging and Monitoring Failures | Test code directly manipulates thread-local storage using set_current_tenant_id( | `src/documents/tests/test_tenant_manager.py:51` |
| INFO | A04:2021 - Insecure Design | Thread-local storage pattern is inherently fragile in async/multi-threaded envir | `src/documents/models/base.py:36, src/paperless/middleware.py:14` |

