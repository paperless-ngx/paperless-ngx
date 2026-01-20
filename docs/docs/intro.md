---
sidebar_position: 0
---

# Paperless NGX Documentation

Welcome to the comprehensive documentation for Paperless NGX. This site contains guides for deploying, configuring, and developing Paperless NGX.

## Documentation Sections

### [Deployment Guides](./deployment/index.md)
Learn how to deploy and manage Paperless NGX on Kubernetes with persistent storage, including:
- Docker image architecture (web, worker, scheduler components)
- Kubernetes deployment strategies
- PostgreSQL and MinIO configuration
- Volume management and data persistence

### [Development Guides](./development/index.md)
Documentation for development and contribution, including:
- Code coverage tracking with Codecov
- Testing requirements and practices
- CI/CD integration

## Quick Start

**New to Paperless NGX?**
→ Start with [Kubernetes Deployment Guide](./deployment/kubernetes-guide.md) or [Quick Start](./deployment/quickstart.md)

**Contributing code?**
→ See [Development Documentation](./development/index.md) and the Contributing Guide in the repository root

**Troubleshooting deployment issues?**
→ Check the troubleshooting sections in relevant deployment guides

## Architecture Overview

```
Paperless NGX (Kubernetes Deployment)
├── Web Component (paless-web)
│   └── Granian HTTP server + API
├── Worker Component (paless-worker)
│   └── Celery task processing
├── Scheduler Component (paless-scheduler)
│   └── Celery beat periodic jobs
├── PostgreSQL Database
├── Redis Message Queue
└── Optional: MinIO Object Storage
```

## Key Features

- **Separated Components**: Web, worker, and scheduler run as independent Kubernetes deployments
- **Persistent Storage**: Reliable data persistence with Kubernetes PVCs
- **Multi-Tenancy**: Database support for multiple tenants via PostgreSQL extensions
- **S3-Compatible Storage**: Optional MinIO integration for document storage
- **Code Coverage Tracking**: Comprehensive coverage monitoring across backend and frontend

## Technology Stack

- **Backend**: Python 3.10+, Django, Celery
- **Frontend**: TypeScript, React
- **Container Platform**: Kubernetes (k8s)
- **Databases**: PostgreSQL
- **Message Queue**: Redis
- **Optional Storage**: MinIO (S3-compatible)

---

Last Updated: 2026-01-20

For the latest information, visit the [Paperless NGX GitHub Repository](https://github.com/paperless-ngx/paperless-ngx).
