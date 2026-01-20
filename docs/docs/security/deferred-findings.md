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
| HIGH | A05:2021 - Security Misconfiguration | All three deployments (web, worker, scheduler) run rclone sidecar containers wit | `k8s/base/paless-web-deployment.yaml:74, k8s/base/paless-worker-deployment.yaml:54, k8s/base/paless-scheduler-deployment.yaml:54` |
| HIGH | A05:2021 - Security Misconfiguration | Main application containers (paless-web, paless-worker, paless-scheduler) lack P | `k8s/base/paless-web-deployment.yaml:25-54, k8s/base/paless-worker-deployment.yaml:25-50, k8s/base/paless-scheduler-deployment.yaml:25-50` |
| HIGH | A01:2021 - Broken Access Control | PAPERLESS_ALLOWED_HOSTS set to '*' disables Django's host header validation, all | `k8s/base/configmap.yaml:40` |
| MEDIUM | A08:2021 - Software and Data Integrity Failures | Container images use mutable tags without digest pinning. Web/worker/scheduler u | `k8s/base/paless-web-deployment.yaml:26,72, k8s/base/paless-worker-deployment.yaml:26,52, k8s/base/paless-scheduler-deployment.yaml:26,52` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | PAPERLESS_AUDIT_LOG_ENABLED is 'false', disabling audit trails for user actions, | `k8s/base/configmap.yaml:70` |
| MEDIUM | A05:2021 - Security Misconfiguration | Database connection uses PAPERLESS_DBSSLMODE: 'prefer' instead of 'require', all | `k8s/base/configmap.yaml:16` |
| MEDIUM | A05:2021 - Security Misconfiguration | No namespace-level security controls: ResourceQuotas (prevent resource exhaustio | `k8s/base/ (missing resources)` |
| LOW | A05:2021 - Security Misconfiguration | PAPERLESS_BIND_ADDR: '0.0.0.0' binds to all interfaces. In container context thi | `k8s/base/configmap.yaml:44` |
| INFO | A04:2021 - Insecure Design | Media storage uses emptyDir volumes (ephemeral) with rclone mounting MinIO. Whil | `k8s/base/paless-web-deployment.yaml:110, k8s/base/paless-worker-deployment.yaml:90, k8s/base/paless-scheduler-deployment.yaml:90` |

