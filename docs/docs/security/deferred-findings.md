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
| High     | 1 |
| Medium   | 2 |
| Low      | 2 |
| Info     | 0 |

---

## Deferred Findings by Task

### Task: 41fae4c5...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Implement tenant-aware ORM managers to automatically filter queries by current tenant context

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A01:2021 - Broken Access Control | Race condition risk in TenantMiddleware cleanup. The middleware clears thread-lo | `src/paperless/middleware.py:136` |
| MEDIUM | A01:2021 - Broken Access Control | The all_objects manager bypasses tenant filtering without access control enforce | `src/documents/models/base.py:144` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | TenantManager returns empty queryset when tenant context is missing (security by | `src/documents/models/base.py:92-105` |
| LOW | A04:2021 - Insecure Design | ModelWithOwner.save() auto-populates tenant_id from thread-local storage with im | `src/documents/models/base.py:163-184` |
| LOW | A09:2021 - Security Logging and Monitoring Failures | Test code directly manipulates thread-local storage using set_current_tenant_id( | `src/documents/tests/test_tenant_manager.py:51` |

