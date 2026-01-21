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

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| LOW | A01:2021 – Broken Access Control | Superuser tenant isolation not explicitly defined - superusers may be limited to | `src/paperless/views.py:121-137` |
| LOW | A07:2021 – Identification and Authentication Failures | Users without profiles (edge case) could cause issues - get_queryset filters by  | `src/paperless/views.py:135` |
| INFO | A09:2021 – Security Logging and Monitoring | No audit logging for cross-tenant access attempts or tenant filtering events | `src/paperless/views.py:121-137` |
| INFO | A05:2021 – Security Misconfiguration | Tests use HTTP_X_TENANT_ID header for testing but production deployment should e | `src/paperless/middleware.py:54` |

