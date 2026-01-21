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
| Low      | 1 |
| Info     | 0 |

---

## Deferred Findings by Task

### Task: 2477b28f...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Add tenant_id to ShareLink model. ShareLinks reference Documents, so tenant_id can be populated from

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A04:2021 - Insecure Design (OWASP Top 10) | The backfill migration iterates over ShareLinks one-by-one with individual saves | `src/documents/migrations/1088_backfill_sharelink_tenant_id.py:16-19` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures (OWASP Top 10) | SharedLinkView (public share link access endpoint) does not log access attempts. | `src/documents/views.py:2813-2823` |
| MEDIUM | A05:2021 - Security Misconfiguration (OWASP Top 10) | The RLS policy migration uses 'true' as the second argument to current_setting() | `src/documents/migrations/1090_add_rls_policy_for_sharelink.py:42` |
| LOW | A04:2021 - Insecure Design (OWASP Top 10) | ShareLink model doesn't track access counts or implement rate limiting. A malici | `src/documents/models.py:715-764` |

