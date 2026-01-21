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
| HIGH | A01:2021 - Broken Access Control (OWASP Top 10) | Race condition risk with thread-local storage cleanup. TenantMiddleware clears t | `src/paperless/middleware.py:136` |
| MEDIUM | A01:2021 - Broken Access Control (OWASP Top 10) | The `all_objects` manager provides unrestricted access to all tenant data withou | `src/documents/models.py:138` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures (OWASP Top 10) | No logging when TenantManager returns empty queryset due to missing tenant conte | `src/documents/models.py:92-94` |
| LOW | A04:2021 - Insecure Design (OWASP Top 10) | ModelWithOwner.save() auto-populates tenant_id from thread-local storage (line 1 | `src/documents/models.py:143-159` |
| LOW | A09:2021 - Security Logging and Monitoring Failures (OWASP Top 10) | Tests directly manipulate thread-local storage without going through middleware, | `src/documents/tests/test_tenant_manager.py:51` |

