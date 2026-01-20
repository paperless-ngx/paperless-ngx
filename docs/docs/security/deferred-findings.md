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
| Medium   | 3 |
| Low      | 3 |
| Info     | 2 |

---

## Deferred Findings by Task

### Task: 0a156b7f...

**Date**: 2026-01-20
**Stage**: dev
**Description**: Deploy separated web, worker, and scheduler components to K3s and verify they work together correctl

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| HIGH | A05:2021 - Security Misconfiguration | Ingress allows access without host header validation (fallback rule at lines 24- | `k8s/base/web-ingress.yaml:24-32` |
| HIGH | A05:2021 - Security Misconfiguration | Ingress lacks TLS configuration, exposing all traffic including authentication c | `k8s/base/web-ingress.yaml:1-33` |
| MEDIUM | A05:2021 - Security Misconfiguration | Ingress missing security-related annotations: rate limiting to prevent brute for | `k8s/base/web-ingress.yaml:8-10` |
| MEDIUM | A09:2021 - Security Logging and Monitoring Failures | No Ingress access logging configuration or monitoring alerts. Unable to detect o | `k8s/base/web-ingress.yaml:1-33` |
| MEDIUM | A05:2021 - Security Misconfiguration | All three deployments (web, worker, scheduler) use privileged: true for rclone s | `k8s/base/paless-web-deployment.yaml:74, k8s/base/paless-worker-deployment.yaml:54, k8s/base/paless-scheduler-deployment.yaml:54` |
| LOW | A05:2021 - Security Misconfiguration | Ingress proxy-body-size set to 100m allows large upload sizes which could be use | `k8s/base/web-ingress.yaml:10` |
| LOW | A05:2021 - Security Misconfiguration | Deployments lack pod-level security contexts (runAsNonRoot, runAsUser, fsGroup). | `k8s/base/paless-web-deployment.yaml:19-24, k8s/base/paless-worker-deployment.yaml:19-24, k8s/base/paless-scheduler-deployment.yaml:19-24` |
| LOW | A05:2021 - Security Misconfiguration | HPA configurations lack resource limits validation. If CPU/memory metrics fail o | `k8s/base/web-hpa.yaml:14, k8s/base/worker-hpa.yaml:14` |
| INFO | A04:2021 - Insecure Design | Ingress uses local domain (paless.local) suitable for DEV but will need proper D | `k8s/base/web-ingress.yaml:14` |
| INFO | A05:2021 - Security Misconfiguration | All three deployments use imagePullPolicy: Always with localhost:5000 registry.  | `k8s/base/paless-web-deployment.yaml:27, k8s/base/paless-worker-deployment.yaml:27, k8s/base/paless-scheduler-deployment.yaml:27` |

