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
- At least 23Gi total storage available (3Gi for Paperless + 20Gi for MinIO)
- Kustomize (if using kustomization approach)
- MinIO credentials configured in secrets (see [Credentials Configuration](#credentials-configuration))

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

### Step 4: Deploy MinIO and Initialize Buckets

When deploying with MinIO S3 object storage, follow the correct deployment order:

1. **Create Secrets** - MinIO requires credentials
   ```bash
   kubectl apply -f secrets.yaml
   ```

2. **Deploy MinIO StatefulSet** - Object storage backend
   ```bash
   kubectl apply -f minio-statefulset.yaml
   ```

3. **Deploy MinIO Service** - Network access to MinIO
   ```bash
   kubectl apply -f minio-service.yaml
   ```

4. **Deploy Bucket Initialization Job** - Creates paperless-media bucket
   ```bash
   kubectl apply -f minio-init-job.yaml
   ```

5. **Deploy Paperless Application** - After MinIO and bucket are ready
   ```bash
   kubectl apply -f paperless-deployment.yaml
   ```

:::tip Deployment Automation
Use Kustomization or Helm to automate this deployment order. These tools handle dependencies and resource ordering automatically.
:::

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

**Bucket Initialization Job:**
- Automated Kubernetes Job creates `paperless-media` bucket
- Runs after MinIO is healthy (uses init container for health checks)
- Idempotent operation (safe to re-run)
- Uses MinIO client (mc) container image
- Implements backoff retry logic for failure handling
- Properly configured tolerations for disk-pressure node conditions

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

### Bucket Initialization Job Configuration

The bucket initialization is handled by a dedicated Kubernetes Job that automatically creates the required `paperless-media` bucket in MinIO. This job runs once per deployment and is idempotent, making it safe to re-run.

#### Job Workflow

1. **Init Container**: Waits for MinIO to become ready
   - Uses health check endpoint: `http://minio:9000/minio/health/ready`
   - Retries every 5 seconds until MinIO is available
   - Ensures bucket creation only happens when MinIO is stable

2. **Main Container**: Creates the bucket
   - Configures MinIO client alias with provided credentials
   - Creates `paperless-media` bucket (idempotent - skips if exists)
   - Verifies bucket creation with listing

#### Job Configuration Example

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-init
  labels:
    app: minio-init
    app.kubernetes.io/component: init
    app.kubernetes.io/part-of: paless
spec:
  backoffLimit: 3  # Retry up to 3 times on failure
  template:
    metadata:
      labels:
        app: minio-init
    spec:
      restartPolicy: OnFailure
      tolerations:
      - key: node.kubernetes.io/disk-pressure
        operator: Exists
        effect: NoSchedule
      initContainers:
      - name: wait-for-minio
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "Waiting for MinIO to be ready..."
          until wget --spider -q http://minio:9000/minio/health/ready; do
            echo "MinIO is not ready. Retrying in 5 seconds..."
            sleep 5
          done
          echo "MinIO is ready!"
      containers:
      - name: minio-client
        image: minio/mc:latest
        env:
        - name: MINIO_ROOT_USER
          valueFrom:
            secretKeyRef:
              name: paless-secret
              key: minio-root-user
        - name: MINIO_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: paless-secret
              key: minio-root-password
        command:
        - sh
        - -c
        - |
          set -e
          echo "Configuring MinIO client alias..."
          mc alias set minio http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

          echo "Creating bucket 'paperless-media' if it doesn't exist..."
          mc mb --ignore-existing minio/paperless-media

          echo "Bucket initialization complete!"
          mc ls minio/ | grep paperless-media
          echo "Verified: paperless-media bucket exists"
```

:::info Idempotent Operation
The `--ignore-existing` flag in the `mc mb` command makes bucket creation idempotent. The job can be re-run without error if the bucket already exists. This is essential for Kubernetes' at-least-once delivery semantics.
:::

#### Job Failure Handling

- **backoffLimit: 3**: Job will retry up to 3 times before marking as failed
- **restartPolicy: OnFailure**: Failed pods are restarted within the job
- **tolerations**: Job can run on nodes with disk pressure conditions
- **Init container health check**: Ensures MinIO is ready before bucket creation

#### Monitoring Job Status

```bash
# Check job status
kubectl get job minio-init

# View job logs
kubectl logs job/minio-init

# Describe job for detailed information
kubectl describe job minio-init

# View completed job pods
kubectl get pods --selector=job-name=minio-init
```

:::warning Job Dependencies
The minio-init Job should be deployed after the MinIO StatefulSet. Use proper ordering in your Kustomization or Helm chart to ensure correct deployment sequence.
:::

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
