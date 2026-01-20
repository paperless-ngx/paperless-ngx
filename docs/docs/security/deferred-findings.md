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
| High     | 3 |
| Medium   | 4 |
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
| HIGH | A01:2021 - Broken Access Control | PAPERLESS_ALLOWED_HOSTS is set to '*' which disables Django's host header valida | `k8s/base/configmap.yaml:40` |
| HIGH | A05:2021 - Security Misconfiguration | Services are exposed via NodePort (port 30080) which exposes the application on  | `k8s/base/service.yaml:9-13` |
| HIGH | A05:2021 - Security Misconfiguration | No Pod Security Standards or Security Contexts are defined for the main applicat | `k8s/base/paless-web-deployment.yaml:25-54, k8s/base/paless-worker-deployment.yaml:25-50, k8s/base/paless-scheduler-deployment.yaml:25-50` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | PAPERLESS_AUDIT_LOG_ENABLED is set to 'false', disabling audit logging which is  | `k8s/base/configmap.yaml:70` |
| MEDIUM | A05:2021 - Security Misconfiguration | Database SSL mode is set to 'prefer' rather than 'require', allowing fallback to | `k8s/base/configmap.yaml:16` |
| MEDIUM | A05:2021 - Security Misconfiguration | No resource quotas, limit ranges, or network policies are defined at the namespa | `k8s/base/ (missing files)` |
| MEDIUM | A08:2021 - Software and Data Integrity Failures | Container images use 'latest' tag for rclone and 'v2' tags without digest pinnin | `k8s/base/paless-web-deployment.yaml:26,72, k8s/base/paless-worker-deployment.yaml:26,52, k8s/base/paless-scheduler-deployment.yaml:26,52` |
| LOW | A05:2021 - Security Misconfiguration | PAPERLESS_BIND_ADDR is set to '0.0.0.0' which binds to all interfaces. While sta | `k8s/base/configmap.yaml:44` |
| INFO | A04:2021 - Insecure Design | The deployment uses emptyDir volumes for media storage which are ephemeral. Whil | `k8s/base/paless-web-deployment.yaml:110, k8s/base/paless-worker-deployment.yaml:90, k8s/base/paless-scheduler-deployment.yaml:90` |

