---
sidebar_position: 1
title: Deployment Documentation
description: Complete guides for deploying Paperless NGX
---

# Deployment Documentation

Welcome to the Paperless NGX deployment guides. This section covers all aspects of deploying and managing Paperless NGX in Kubernetes environments.

## Available Guides

### [Docker Image Architecture](./docker-images.md)
Separated Docker images for web, worker, and scheduler components with independent scaling and deployment.

- Architecture comparison (monolithic vs. separated)
- Image specifications (paless-web, paless-worker, paless-scheduler)
- Service removal mechanism using s6-overlay
- Building and pushing images
- Kubernetes deployment of separated components
- Scaling strategies for each component
- Monitoring and debugging by component

### [Configuration Management](./configuration.md)
Central configuration file documentation for all deployment settings.

- `paless.env` file structure and sections
- Environment variables and their purposes
- Development vs. production configuration
- Security checklist and best practices
- Secrets management and environment-specific overrides

### [Quick Start](./quickstart.md)
Get Paperless NGX running on Kubernetes in minutes with persistent storage. Perfect for developers and operators new to the system.

- Manual manifest deployment
- Kustomize-based deployment
- Verification and troubleshooting
- Common configurations

### [Kubernetes Deployment Guide](./kubernetes-guide.md)
Comprehensive guide to Kubernetes deployment architecture and best practices.

- Volume architecture overview
- Setup instructions for development and production
- Data persistence strategy
- Backup and recovery procedures
- Production considerations

### [Volume Configuration](./volume-configuration.md)
Detailed reference for persistent volume and persistent volume claim configuration.

- Volume structure and definitions
- Configuration file examples
- Deployment scenarios (dev, test, production)
- Capacity planning and monitoring
- Troubleshooting guide

## Key Changes: PVC Migration

### What Changed

Previous versions of Paperless NGX used ephemeral `emptyDir` volumes, which created temporary storage deleted when pods terminated. The current deployment uses persistent volume claims (PVCs) for durable storage.

**Before (emptyDir):**
```yaml
volumes:
  - name: data
    emptyDir: {}
  - name: media
    emptyDir: {}
```

**After (PVC):**
```yaml
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: paperless-data-pvc
  - name: media
    persistentVolumeClaim:
      claimName: paperless-media-pvc
```

### Benefits

- **Data Persistence**: Data survives pod restarts and redeployments
- **Backup Capability**: Enable snapshots and disaster recovery
- **Production Ready**: Suitable for enterprise deployments
- **Flexible Storage**: Works with any Kubernetes storage backend

## Quick Navigation

### I want to...

**Understand the separated Docker architecture**
→ Read [Docker Image Architecture](./docker-images.md)

**Build and push separate Docker images**
→ See [Building Images](./docker-images.md#building-images) section in Docker Image Architecture

**Deploy separated web, worker, and scheduler components**
→ Follow examples in [Kubernetes Deployment](./docker-images.md#kubernetes-deployment) section

**Scale workers based on task volume**
→ Check [Scaling Strategy](./docker-images.md#scaling-strategy) in Docker Image Architecture

**Configure environment settings**
→ Read [Configuration Management](./configuration.md)

**Deploy Paperless NGX quickly**
→ Start with [Quick Start](./quickstart.md)

**Understand the deployment architecture**
→ Read [Kubernetes Deployment Guide](./kubernetes-guide.md)

**Configure volumes for specific scenarios**
→ Refer to [Volume Configuration](./volume-configuration.md)

**Set up secrets and configuration**
→ See [Configuration Management](./configuration.md#secret-management) and [Quick Start](./quickstart.md#step-1-create-secrets-and-configmaps)

**Migrate from emptyDir to PVC**
→ See the "Data Persistence Strategy" section in [Kubernetes Deployment Guide](./kubernetes-guide.md#data-persistence-strategy)

**Plan storage capacity**
→ Check "Capacity Planning" in [Kubernetes Deployment Guide](./kubernetes-guide.md#capacity-planning) and [Configuration Management](./configuration.md#capacity-planning)

**Troubleshoot volume issues**
→ Use troubleshooting guides in [Volume Configuration](./volume-configuration.md#troubleshooting)

**Monitor separated components**
→ See [Monitoring and Debugging](./docker-images.md#monitoring-and-debugging) in Docker Image Architecture

## Architecture Overview

```
Kubernetes Cluster
├── Persistent Volumes (PVs)
│   ├── paperless-data-pv (1Gi)
│   └── paperless-media-pv (2Gi)
├── Persistent Volume Claims (PVCs)
│   ├── paperless-data-pvc
│   └── paperless-media-pvc
├── Deployments
│   ├── paless-web (2+ replicas)
│   │   └── Container: paless-web (port 8000)
│   ├── paless-worker (2+ replicas, scalable)
│   │   └── Container: paless-worker (Celery)
│   └── paless-scheduler (1 replica, single instance)
│       └── Container: paless-scheduler (Celery beat)
├── Services
│   ├── paperless (LoadBalancer → web tier)
│   ├── redis
│   └── postgres
└── Optional: MinIO storage with rclone sidecars
```

:::info Separated Components
Paperless-ngx is deployed as three separate Docker images (paless-web, paless-worker, paless-scheduler) for independent scaling and better resource efficiency. See [Docker Image Architecture](./docker-images.md) for details.
:::

## Deployment Checklist

Before deploying to production:

### Architecture & Planning
- [ ] Review [Docker Image Architecture](./docker-images.md) to understand separated components
- [ ] Review [Configuration Management](./configuration.md) and complete security checklist
- [ ] Review [Kubernetes Deployment Guide](./kubernetes-guide.md) for architecture understanding

### Building & Deployment
- [ ] Build Docker images (web, worker, scheduler) - see [Building Images](./docker-images.md#building-images)
- [ ] Push images to container registry
- [ ] Follow [Quick Start](./quickstart.md) guide for initial setup
- [ ] Deploy web, worker, and scheduler deployments separately

### Configuration
- [ ] Configure all values in `paless.env` for your environment
- [ ] Set up secrets management (Sealed Secrets, External Secrets, etc.)
- [ ] Configure appropriate storage class for your environment

### Storage & Backup
- [ ] Set reclaim policy to `Retain` for production
- [ ] Plan and allocate sufficient storage capacity
- [ ] Implement backup strategy
- [ ] Test restore procedures

### Monitoring & Operations
- [ ] Configure monitoring and alerting for all three components
- [ ] Set up worker scaling based on task queue depth
- [ ] Verify scheduler runs as single instance only
- [ ] Document your deployment for team reference

## Integration with Other Services

Paperless NGX in Kubernetes typically integrates with:

- **Storage Backend**: Local hostPath (dev), NFS (test), Cloud storage (production)
- **Message Queue**: Redis (included in standard deployment)
- **Optional Services**: Apache Tika, Gotenberg (for document processing)
- **Object Storage**: MinIO (via rclone sidecar)

## Support and Resources

### Official Kubernetes Documentation
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

### Paperless NGX Resources
- [Official Paperless NGX Repository](https://github.com/paperless-ngx/paperless-ngx)
- [Paperless NGX Documentation](https://docs.paperless-ngx.com/)

---

**Last Updated**: 2026-01-20

For questions or issues with the deployment guides, please refer to the [troubleshooting sections](./volume-configuration.md#troubleshooting) or consult the [Kubernetes documentation](https://kubernetes.io/docs/).
