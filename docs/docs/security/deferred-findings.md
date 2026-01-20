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

### Task: 0a156b7f...

**Date**: 2026-01-20
**Stage**: dev
**Description**: Deploy separated web, worker, and scheduler components to K3s and verify they work together correctl

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A05:2021 - Security Misconfiguration | Ingress allows access without host header (fallback rule at lines 24-32). This c | `k8s/base/web-ingress.yaml:24-32` |
| HIGH | A05:2021 - Security Misconfiguration | Ingress lacks TLS configuration, exposing all traffic including authentication c | `k8s/base/web-ingress.yaml:1-33` |
| MEDIUM | A05:2021 - Security Misconfiguration | Ingress missing security-related annotations: rate limiting, CORS headers, secur | `k8s/base/web-ingress.yaml:8-10` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | No Ingress access logging configuration or monitoring. Unable to track unauthori | `k8s/base/web-ingress.yaml:1-33` |
| LOW | A05:2021 - Security Misconfiguration | Ingress proxy-body-size set to 100m allows large upload sizes which could be use | `k8s/base/web-ingress.yaml:10` |
| INFO | A04:2021 - Insecure Design | Ingress uses local domain (paless.local) suitable for DEV but will need proper D | `k8s/base/web-ingress.yaml:14` |

