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
| Medium   | 1 |
| Low      | 2 |
| Info     | 1 |

---

## Deferred Findings by Task

### Task: 194402b8...

**Date**: 2026-01-21
**Stage**: dev
**Description**: Implement per-tenant classifier model files to prevent data leakage. Currently, settings.MODEL_FILE 

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A01:2021 - Broken Access Control | Tenant isolation bypass in conditionals.py. The suggestions_etag() and suggestio | `src/documents/conditionals.py:25,51` |
| MEDIUM | A04:2021 - Insecure Design | Migration script uses hardcoded Django path. The script contains hardcoded path  | `scripts/migrate_classifier_to_tenant.py:15` |
| LOW | A09:2021 - Security Logging and Monitoring | Migration script catches broad exceptions without proper security logging. When  | `scripts/migrate_classifier_to_tenant.py:65-67` |
| LOW | A04:2021 - Insecure Design | Race condition in directory creation. get_tenant_model_file() creates directorie | `src/documents/classifier.py:61` |
| INFO | Best Practice | Missing input validation on tenant_id parameter. Multiple functions accept tenan | `src/documents/classifier.py:44,78,167,218` |

