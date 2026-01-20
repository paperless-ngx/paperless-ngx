---
sidebar_position: 2
title: Volume Configuration
description: Detailed guide for configuring persistent volumes in Paperless NGX deployments
---

# Volume Configuration Guide

This guide provides detailed instructions for configuring volumes in your Paperless NGX Kubernetes deployment, with examples for different deployment scenarios.

## Volume Structure

Paperless NGX uses two distinct volumes:

```
/usr/src/paperless/
├── data/              ← 1Gi PVC (Database + Application State)
└── media/             ← 2Gi PVC (Document Files)
```

## Configuration Files

### PersistentVolume Definition (pv-manual.yaml)

For development environments, define manual persistent volumes:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: paperless-data-pv
  namespace: default
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
  namespace: default
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

**Key Fields Explained:**

| Field | Value | Purpose |
|-------|-------|---------|
| `capacity.storage` | `1Gi` / `2Gi` | Maximum volume size |
| `accessModes` | `ReadWriteOnce` | Single pod read/write access |
| `reclaimPolicy` | `Retain` | Keep data after deletion |
| `storageClassName` | `manual` | Binding to manual storage class |
| `hostPath.path` | `/tmp/paperless-*` | Local filesystem path |
| `hostPath.type` | `DirectoryOrCreate` | Create directory if missing |

### PersistentVolumeClaim Definition (pvc.yaml)

Claims request storage from available persistent volumes:

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

## Deployment Integration

### Mounting Volumes in Pods

In your deployment manifest, reference the claims:

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
          image: paperless-ngx:latest
          volumeMounts:
            # Mount data volume
            - name: data
              mountPath: /usr/src/paperless/data
            # Mount media volume
            - name: media
              mountPath: /usr/src/paperless/media

      # Define volumes referenced above
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: paperless-data-pvc
        - name: media
          persistentVolumeClaim:
            claimName: paperless-media-pvc
```

## Kustomization Integration

If using Kustomize for deployment management:

**kustomization.yaml:**
```yaml
resources:
  - configmap.yaml
  - paless-secret.yaml
  - pv-manual.yaml          # Persistent volumes (dev only)
  - pvc.yaml                # Persistent volume claims
  - deployment.yaml         # Deployment with volume mounts
  - service.yaml
```

## Deployment Scenarios

### Development Environment

Use local hostPath storage for rapid iteration:

```yaml
hostPath:
  path: /tmp/paperless-data
  type: DirectoryOrCreate
storageClassName: manual
```

**Trade-offs:**
- ✅ No external dependencies
- ✅ Easy to inspect and debug
- ❌ Only works on single node
- ❌ Not production-ready

### Testing Environment

Use network storage (NFS) for multi-node testing:

```yaml
nfs:
  server: nfs.example.com
  path: "/export/paperless-data"
storageClassName: nfs
```

**Configuration:**
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: paperless-data-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteMany
  storageClassName: nfs
  nfs:
    server: nfs.example.com
    path: "/export/paperless-data"
```

### Production Environment

Use cloud provider managed storage:

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

Example production PVC:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: paperless-data-pvc
spec:
  storageClassName: ebs-sc
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

## Access Modes

Paperless NGX requires `ReadWriteOnce` (RWO) access:

| Mode | Symbol | Meaning | Use Case |
|------|--------|---------|----------|
| ReadWriteOnce | RWO | Single pod read/write | Paperless NGX (default) |
| ReadOnlyMany | ROX | Multiple pods read-only | Backup systems |
| ReadWriteMany | RWX | Multiple pods read/write | Distributed systems |

:::note Access Modes
Paperless NGX pods cannot share storage simultaneously. Use external backup solutions (e.g., rclone) to share media across systems.
:::

## Capacity Management

### Initial Sizing

Base allocation for fresh installations:

```yaml
data:
  requests:
    storage: 1Gi    # SQLite database + metadata

media:
  requests:
    storage: 2Gi    # Scanned documents
```

### Growth Estimation

For active scanning systems:

- **Consumption Rate:** ~2-5MB per scanned document (depends on document type)
- **OCR Data:** Additional space for OCR processing caches

Example for 1000 documents:
```yaml
data:
  requests:
    storage: 2Gi      # Database growth

media:
  requests:
    storage: 5-10Gi   # 1000 docs × 5-10MB average
```

### Dynamic Expansion

Expand PVCs without downtime:

```bash
# Update PVC storage request
kubectl patch pvc paperless-data-pvc -p \
  '{"spec":{"resources":{"requests":{"storage":"5Gi"}}}}'

# Verify new size (may require storage backend expansion)
kubectl get pvc
```

## Storage Class Selection

### Manual Storage Class (Development)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: manual
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
```

### Cloud Provisioned Storage (Production)

Most clouds provide default storage classes:

```bash
# List available storage classes
kubectl get storageclass

# Check details
kubectl describe sc ebs-sc
```

## Volume Verification

### Check Volume Status

```bash
# List persistent volumes
kubectl get pv -o wide

# List persistent volume claims
kubectl get pvc -o wide

# Detailed PVC information
kubectl describe pvc paperless-data-pvc
```

### Verify Mount Points

```bash
# Access pod and verify mounts
kubectl exec -it deployment/paperless -- df -h

# Example output:
# /dev/xxx    1.0G  100M  900M  10% /usr/src/paperless/data
# /dev/yyy    2.0G  500M  1.5G  25% /usr/src/paperless/media
```

### Monitor Volume Usage

```bash
# Check current usage
kubectl exec -it deployment/paperless -- \
  du -sh /usr/src/paperless/data /usr/src/paperless/media
```

## Troubleshooting

### PVC Stuck in "Pending"

```bash
# Check available PVs
kubectl get pv

# Check PVC events
kubectl describe pvc paperless-data-pvc

# Common causes:
# - Storage class doesn't exist
# - No available PVs of matching size
# - StorageClassName mismatch between PV and PVC
```

### Pod CrashLoopBackOff with Volume Issues

```bash
# Check pod events
kubectl describe pod <pod-name>

# Check volume mounts in container
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].volumeMounts}'

# Verify PVC is bound
kubectl get pvc -o wide
```

### Insufficient Disk Space

```bash
# Monitor node disk usage
kubectl top nodes
df -h /tmp/paperless-*

# Clean up old data if using hostPath
# For production, increase volume size instead
```

## Best Practices

1. **Always use Retain reclaim policy** in production
2. **Over-allocate by 20%** to handle growth spikes
3. **Implement regular backups** independent of volumes
4. **Monitor volume usage** proactively
5. **Test restore procedures** regularly
6. **Use meaningful PV/PVC names** for clarity
7. **Label resources** for easy filtering: `app: paperless`

## References

- [Kubernetes PV/PVC Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Managing Resources in Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
