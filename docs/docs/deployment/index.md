---
sidebar_position: 1
title: Deployment Documentation
description: Complete guides for deploying Paperless NGX
---

# Deployment Documentation

Welcome to the Paperless NGX deployment guides. This section covers all aspects of deploying and managing Paperless NGX in Kubernetes environments.

## Available Guides

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

## Architecture Overview

```
Kubernetes Cluster
├── Persistent Volumes (PVs)
│   ├── paperless-data-pv (1Gi)
│   └── paperless-media-pv (2Gi)
├── Persistent Volume Claims (PVCs)
│   ├── paperless-data-pvc
│   └── paperless-media-pvc
└── Deployment (paperless)
    ├── Container: paperless
    │   ├── /usr/src/paperless/data (mounted from paperless-data-pvc)
    │   └── /usr/src/paperless/media (mounted from paperless-media-pvc)
    └── Container: rclone (optional, for MinIO integration)
```

## Deployment Checklist

Before deploying to production:

- [ ] Review [Configuration Management](./configuration.md) and complete security checklist
- [ ] Review [Kubernetes Deployment Guide](./kubernetes-guide.md) for architecture understanding
- [ ] Follow [Quick Start](./quickstart.md) guide for initial setup
- [ ] Configure all values in `paless.env` for your environment
- [ ] Set up secrets management (Sealed Secrets, External Secrets, etc.)
- [ ] Configure appropriate storage class for your environment
- [ ] Set reclaim policy to `Retain` for production
- [ ] Plan and allocate sufficient storage capacity
- [ ] Implement backup strategy
- [ ] Configure monitoring and alerting
- [ ] Test restore procedures
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
