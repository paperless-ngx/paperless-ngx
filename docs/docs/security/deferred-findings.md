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
| Info     | 2 |

---

## Deferred Findings by Task

### Task: 98326f02...

**Date**: 2026-01-20
**Stage**: dev
**Description**: Prepare PostgreSQL database for multi-tenancy by verifying schema compatibility and adding necessary

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| MEDIUM | A01:2021 - Broken Access Control | SQL schema file contains GRANT statements to 'paperless_app' user with broad per | `docs/database-schema/paperless_schema_baseline.sql:5321-5500+` |
| HIGH | A01:2021 - Broken Access Control | The schema contains sensitive authentication tables (auth_user, authtoken_token, | `docs/database-schema/paperless_schema_baseline.sql:199,287,2220` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | The verification script checks for errors in PostgreSQL logs but uses a simple g | `scripts/verify-db-preparation.sh:130` |
| LOW | A04:2021 - Insecure Design | The verification script uses hardcoded namespace ('paless'), pod name ('postgres | `scripts/verify-db-preparation.sh:9-12` |
| INFO | A02:2021 - Cryptographic Failures | Documentation mentions pgcrypto extension for 'encryption and hashing' but doesn | `docs/multi-tenant-db-preparation.md:30-34` |
| INFO | A05:2021 - Security Misconfiguration | Documentation shows max_connections=100 which may be insufficient for a multi-te | `docs/multi-tenant-db-preparation.md:116,156-165` |

