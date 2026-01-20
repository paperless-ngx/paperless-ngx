---
sidebar_position: 3
title: Kubernetes Deployment Guide
description: Deploy Paperless NGX on Kubernetes with persistent volume management
---

# Kubernetes Deployment Guide

This guide covers deploying Paperless NGX on Kubernetes with proper persistent volume (PV) and persistent volume claim (PVC) configuration for data persistence.

## Overview

Paperless NGX requires two key volume types:
- **Data volume** (`/usr/src/paperless/data`): Stores database and application state
- **Media volume** (`/usr/src/paperless/media`): Stores scanned document files and processed media

The deployment uses persistent volume claims to ensure data survives pod restarts and enables proper backup and recovery strategies.

## Volume Architecture

### Volume Types

| Volume | Path | Size | Type | Purpose |
|--------|------|------|------|---------|
| data | `/usr/src/paperless/data` | 1Gi | PVC | Database and application state |
| media | `/usr/src/paperless/media` | 2Gi | PVC | Document storage and media files |
| rclone-config | `/config/rclone` | - | ConfigMap | rclone configuration |

## Setup Instructions

### Prerequisites

- Kubernetes 1.20+ cluster
- kubectl configured with cluster access
- At least 3Gi total storage available
- Kustomize (if using kustomization approach)

### Step 1: Create Persistent Volumes (Development)

For development environments using local storage, create persistent volumes with `hostPath`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: paperless-data-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  hostPath:
    path: /tmp/paperless-data
    type: DirectoryOrCreate
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: paperless-media-pv
spec:
  capacity:
    storage: 2Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  hostPath:
    path: /tmp/paperless-media
    type: DirectoryOrCreate
```

:::info Storage Classes
Development uses the `manual` storage class with `hostPath`. For production, use your cloud provider's storage classes (e.g., `ebs-sc` on AWS, `standard` on GKE).
:::

### Step 2: Create Persistent Volume Claims

Define PVCs to bind to the persistent volumes:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: paperless-data-pvc
  labels:
    app: paperless
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: paperless-media-pvc
  labels:
    app: paperless
spec:
  storageClassName: manual
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
```

### Step 3: Mount Volumes in Deployment

Configure the deployment to mount PVCs at the correct paths:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paperless
spec:
  template:
    spec:
      containers:
        - name: paperless
          volumeMounts:
            - name: data
              mountPath: /usr/src/paperless/data
            - name: media
              mountPath: /usr/src/paperless/media
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: paperless-data-pvc
        - name: media
          persistentVolumeClaim:
            claimName: paperless-media-pvc
```

## Data Persistence Strategy

### Before: emptyDir Volumes

Previous deployments used ephemeral `emptyDir` volumes, which created temporary storage that was deleted when the pod terminated:

```yaml
volumes:
  - name: data
    emptyDir: {}
  - name: media
    emptyDir: {}
```

**Problems with emptyDir:**
- Data lost on pod restart
- No backup capability
- No persistent state across redeployments
- Unsuitable for production use

### After: Persistent Volume Claims

Current deployments use PVCs, which provide durable storage independent of pod lifecycle:

```yaml
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: paperless-data-pvc
  - name: media
    persistentVolumeClaim:
      claimName: paperless-media-pvc
```

**Advantages of PVCs:**
- Data survives pod restarts and redeployments
- Enables backup and disaster recovery
- Production-ready storage management
- Works with any storage backend (local, cloud, network)

## MinIO S3 Object Storage Integration

Paperless NGX integrates with MinIO to provide S3-compatible object storage for media files. This architecture separates application data (SQLite database) from document storage (media files).

### Architecture Overview

```
┌─────────────────────────────────────────────┐
│         Paperless NGX Deployment            │
├─────────────────────────────────────────────┤
│  ┌──────────────────┐   ┌───────────────┐  │
│  │   Paperless      │   │    rclone     │  │
│  │   Container      │◄──►  Sidecar      │  │
│  │                  │   │   Container   │  │
│  └──────────────────┘   └───────────────┘  │
│           ▲                      │          │
│           │                      ▼          │
│      /data (1Gi)          /mnt/media       │
│        emptyDir            emptyDir        │
│                                 │          │
│                         [mount propagation]
│                                 │          │
│                            /media         │
│                              PVC          │
└─────────────────────────────────────────────┘
           │
           │ S3 API (HTTP)
           ▼
┌─────────────────────────────────────────────┐
│        MinIO StatefulSet (1 Replica)        │
├─────────────────────────────────────────────┤
│  • S3 API Endpoint: minio:9000              │
│  • Console UI: minio:9001                   │
│  • Storage: 20Gi PersistentVolume           │
│  • Bucket: paperless-media                  │
└─────────────────────────────────────────────┘
```

### Component Details

**MinIO StatefulSet:**
- Single-replica MinIO server providing S3 API
- Stores document media in persistent storage
- Exposes S3 API on port 9000
- Includes web console on port 9001
- Health checks (liveness/readiness probes)
- Resource limits: 512Mi-1Gi memory, 500m-1 CPU

**rclone Sidecar:**
- Mounts MinIO bucket as a filesystem
- Uses FUSE to present S3 storage as directory
- Handles authentication via environment variables
- Enables seamless file access from Paperless container

**Bucket Initialization:**
- Automated job creates `paperless-media` bucket
- Runs after MinIO is healthy
- Idempotent operation (safe to re-run)
- Uses MinIO client (mc) container image

### Credentials Configuration

MinIO requires root credentials stored in secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: paless-secret
type: Opaque
stringData:
  minio-root-user: minioadmin      # Change in production
  minio-root-password: minioadmin  # Change in production
```

:::warning Credentials
Never commit credentials to version control. Use a secrets management tool (e.g., Sealed Secrets, External Secrets Operator) in production.
:::

### Development Console Access

In development environments, access MinIO console via NodePort:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minio-console
spec:
  type: NodePort
  selector:
    app: minio
  ports:
    - port: 9001
      targetPort: 9001
      nodePort: 30090
```

Access at: `http://localhost:30090` with credentials from secret.

### Storage Class

MinIO uses the `local-path` storage class for its data:

```yaml
volumeClaimTemplates:
  - metadata:
      name: minio-data
    spec:
      accessModes:
        - ReadWriteOnce
      storageClassName: local-path
      resources:
        requests:
          storage: 20Gi
```

For production, replace with your cloud provider's storage class (e.g., `ebs-sc`, `standard`).

## Production Considerations

### Storage Classes

For production deployments, use your cloud provider's managed storage:

**AWS EBS:**
```yaml
storageClassName: ebs-sc
```

**Google Cloud:**
```yaml
storageClassName: standard
```

**Azure:**
```yaml
storageClassName: default
```

### Capacity Planning

Allocate storage based on document volume:

| Use Case | Data | Media | Total |
|----------|------|-------|-------|
| Small (< 1000 docs) | 1Gi | 2Gi | 3Gi |
| Medium (1000-10000 docs) | 2Gi | 10Gi | 12Gi |
| Large (> 10000 docs) | 5Gi+ | 20Gi+ | 25Gi+ |

### Reclaim Policies

Configure appropriate reclaim behavior:

- **Retain**: Keep data after PVC deletion (recommended for production)
- **Delete**: Remove data when PVC is deleted (use with caution)
- **Recycle**: Scrub data and reclaim volume (deprecated, avoid)

:::warning Production
Always use `persistentVolumeReclaimPolicy: Retain` in production to prevent accidental data loss.
:::

## Backup and Recovery

### Backup Strategy

Implement regular snapshots of PVs:

```bash
# Example: Backup using Kubernetes API
kubectl exec -it pod/paperless -- tar czf - /usr/src/paperless/data | \
  aws s3 cp - s3://my-bucket/paperless-data-backup.tar.gz
```

### Volume Expansion

To expand a PVC, edit the claim and increase the requested storage:

```bash
kubectl patch pvc paperless-data-pvc -p '{"spec":{"resources":{"requests":{"storage":"5Gi"}}}}'
```

## Troubleshooting

### PVC Stuck in Pending State

```bash
# Check PV availability
kubectl get pv

# Check PVC events
kubectl describe pvc paperless-data-pvc

# Verify storage class exists
kubectl get storageclass
```

### Pod Fails to Mount Volume

```bash
# Check pod events for mount errors
kubectl describe pod/paperless

# Verify PVC is bound
kubectl get pvc -o wide

# Check node disk space
kubectl top nodes
```

### Data Loss After Restart

If data is lost after pod restart, verify:

1. PVC is using persistent volumes (not emptyDir)
2. `volumeMounts` paths match container paths
3. PV is not accidentally deleted
4. Storage backend is functioning

## References

- [Kubernetes Persistent Volumes Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Persistent Volume Claims Guide](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
