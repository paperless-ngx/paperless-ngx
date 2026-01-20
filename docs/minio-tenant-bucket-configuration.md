# MinIO Tenant Bucket Isolation Configuration

## Overview

This document describes the MinIO configuration for per-tenant bucket isolation in the paless multi-tenant document management system.

## MinIO StatefulSet Configuration

### Current Configuration

**Location**: `k8s/base/minio-statefulset.yaml`

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Image** | `minio/minio:latest` | MinIO server image |
| **Replicas** | 1 | Single instance deployment |
| **Storage Capacity** | 20Gi | PersistentVolumeClaim size |
| **Storage Class** | `local-path` | K3s local-path provisioner |
| **Access Mode** | ReadWriteOnce | Single node access |
| **Memory Request** | 512Mi | Minimum memory allocation |
| **Memory Limit** | 1Gi | Maximum memory allocation |
| **CPU Request** | 500m | Minimum CPU allocation |
| **CPU Limit** | 1 | Maximum CPU allocation |

### Service Endpoints

**Location**: `k8s/base/minio-service.yaml`

| Port | Name | Protocol | Purpose |
|------|------|----------|---------|
| 9000 | s3-api | TCP | S3 API endpoint |
| 9001 | console | TCP | MinIO web console |

**Service Type**: ClusterIP (internal cluster access)

**DNS Name**: `minio.<namespace>.svc.cluster.local` or `minio` within namespace

### Credentials

Credentials are stored in Kubernetes Secret: `paless-secret`

| Secret Key | Environment Variable | Purpose |
|------------|---------------------|---------|
| `minio-root-user` | `MINIO_ROOT_USER` | MinIO admin username |
| `minio-root-password` | `MINIO_ROOT_PASSWORD` | MinIO admin password |

**Security Note**: These credentials provide full administrative access to all buckets. For production multi-tenant isolation, implement per-tenant IAM policies.

## Bucket Naming Convention

### Standard Format

```
paperless-<tenant_id>
```

### Examples

- `paperless-tenant-a` - Bucket for tenant A
- `paperless-tenant-b` - Bucket for tenant B
- `paperless-acme-corp` - Bucket for ACME Corporation
- `paperless-demo-user` - Bucket for demo user

### Naming Rules

1. **Prefix**: Always use `paperless-` prefix
2. **Tenant ID Format**: Lowercase alphanumeric characters and hyphens only
3. **Pattern**: `^paperless-[a-z0-9-]+$`
4. **Examples of Valid IDs**: `tenant-a`, `acme-corp`, `user123`, `demo-tenant`
5. **Examples of Invalid IDs**: `Tenant_A` (uppercase/underscore), `tenant.b` (period), `tenant@c` (special char)

### Legacy Bucket

- `paperless-media` - Original single-tenant bucket (for backward compatibility)

## Bucket Provisioning

### Automated Provisioning Script

**Location**: `scripts/provision-tenant-bucket.sh`

**Usage**:
```bash
./scripts/provision-tenant-bucket.sh <tenant_id> [namespace]
```

**Examples**:
```bash
# Create bucket for tenant-a in default namespace
./scripts/provision-tenant-bucket.sh tenant-a

# Create bucket for tenant-b in custom namespace
./scripts/provision-tenant-bucket.sh tenant-b my-namespace
```

**Features**:
- ✓ Validates tenant ID format
- ✓ Creates bucket following naming convention
- ✓ Idempotent (safe to run multiple times)
- ✓ Verifies bucket creation
- ✓ Reports execution time (target: <5 seconds)

**Performance**: Typically completes in 2-4 seconds

### Manual Provisioning

If the script is unavailable, use kubectl exec:

```bash
# Get MinIO pod name
MINIO_POD=$(kubectl get pods -n generic-repo -l app=minio -o jsonpath='{.items[0].metadata.name}')

# Get credentials
MINIO_USER=$(kubectl get secret paless-secret -n generic-repo -o jsonpath='{.data.minio-root-user}' | base64 -d)
MINIO_PASS=$(kubectl get secret paless-secret -n generic-repo -o jsonpath='{.data.minio-root-password}' | base64 -d)

# Create bucket
kubectl exec -n generic-repo "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_USER' '$MINIO_PASS' && \
    mc mb --ignore-existing local/paperless-<tenant_id>
"
```

## Bucket Isolation

### Current Implementation

**Isolation Level**: Bucket-level separation

Each tenant has a dedicated bucket that logically isolates their data from other tenants.

### Isolation Verification

**Test Script**: `scripts/test-bucket-isolation.sh`

**Usage**:
```bash
./scripts/test-bucket-isolation.sh [namespace]
```

**Test Coverage**:
1. ✓ Creates test buckets for three tenants (tenant-a, tenant-b, tenant-c)
2. ✓ Uploads unique test files to each bucket
3. ✓ Verifies each bucket contains only its own files
4. ✓ Confirms files are not leaked between buckets

### Security Considerations

**Current Setup**: Uses shared root credentials
- All pods have access to all buckets via root credentials
- Application-level logic must enforce tenant context

**Production Recommendations**:
1. **IAM Policies**: Create MinIO IAM users per tenant with bucket-specific policies
2. **Bucket Policies**: Restrict access to bucket only to authorized tenant users
3. **Network Policies**: Implement Kubernetes NetworkPolicies if needed
4. **Audit Logging**: Enable MinIO audit logs for compliance
5. **Encryption**: Enable server-side encryption for data at rest

## rclone Integration

### Configuration

**Location**: `k8s/base/rclone-configmap.yaml`

```yaml
[minio]
type = s3
provider = Minio
endpoint = http://minio:9000
env_auth = true
acl = private
```

**Authentication**: Uses environment variables from paless-secret
- `AWS_ACCESS_KEY_ID` → minio-root-user
- `AWS_SECRET_ACCESS_KEY` → minio-root-password

### Sidecar Container

**Location**: `k8s/base/paless-web-deployment.yaml` (lines 71-104)

**Current Mount**:
```bash
rclone mount minio:paperless-media /mnt/media --vfs-cache-mode full --allow-other --daemon
```

### Multi-Bucket Support

rclone supports mounting different buckets by changing the remote path:

```bash
# Mount tenant-a bucket
rclone mount minio:paperless-tenant-a /mnt/media --vfs-cache-mode full --allow-other

# Mount tenant-b bucket
rclone mount minio:paperless-tenant-b /mnt/media --vfs-cache-mode full --allow-other
```

**Testing**: Use `scripts/test-rclone-multibucket.sh` to verify multi-bucket compatibility

### Per-Tenant Deployment Strategy

For true multi-tenant isolation with rclone:

1. **Option A: Environment Variable**
   - Add `TENANT_ID` environment variable to pod
   - Modify rclone command to use: `minio:paperless-${TENANT_ID}`

2. **Option B: Separate Deployments**
   - Deploy separate pod instances per tenant
   - Each pod mounts its specific tenant bucket

3. **Option C: Dynamic Mounting**
   - Application-level logic determines tenant context
   - Mount appropriate bucket based on request/session

## Storage Capacity Planning

### Current Capacity

- **Provisioned**: 20Gi PersistentVolume
- **Storage Class**: local-path (K3s default)
- **Backend**: Host filesystem

### Growth Monitoring

```bash
# Check PVC usage
kubectl get pvc -n generic-repo

# Check MinIO storage usage
kubectl exec -n generic-repo <minio-pod> -- df -h /data

# Check bucket sizes
kubectl exec -n generic-repo <minio-pod> -- mc du local/
```

### Capacity Recommendations

| Tenant Count | Avg. per Tenant | Recommended Total | Notes |
|--------------|-----------------|-------------------|-------|
| 1-5 tenants | 2-5 GB | 20-50 Gi | Current setup sufficient |
| 5-10 tenants | 2-5 GB | 50-100 Gi | Increase PVC size |
| 10-50 tenants | 2-5 GB | 100-500 Gi | Consider distributed MinIO |
| 50+ tenants | 2-5 GB | 500+ Gi | Multi-node MinIO cluster recommended |

### Scaling Storage

To increase storage capacity:

```bash
# Edit StatefulSet PVC template
kubectl edit statefulset minio -n generic-repo

# Update storage request
# spec.volumeClaimTemplates[0].spec.resources.requests.storage: 50Gi

# Delete pod to trigger recreation with new PVC (if supported by storage class)
kubectl delete pod minio-0 -n generic-repo
```

**Warning**: Not all storage classes support volume expansion. Check with `kubectl get storageclass`.

## Monitoring and Operations

### Health Checks

MinIO StatefulSet includes liveness and readiness probes:

```yaml
livenessProbe:
  httpGet:
    path: /minio/health/live
    port: 9000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /minio/health/ready
    port: 9000
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Accessing MinIO Console

For development environments:

```bash
# Forward console port
kubectl port-forward -n generic-repo svc/minio 9001:9001

# Access console at: http://localhost:9001
```

Or use the NodePort service (dev overlay): `http://<node-ip>:30900`

### Logging

```bash
# View MinIO logs
kubectl logs -n generic-repo -l app=minio --tail=100 -f

# View rclone sidecar logs
kubectl logs -n generic-repo <pod-name> -c rclone --tail=100 -f
```

### Common Operations

```bash
# List all buckets
kubectl exec -n generic-repo <minio-pod> -- mc ls local/

# Check bucket contents
kubectl exec -n generic-repo <minio-pod> -- mc ls local/paperless-tenant-a/

# Copy data between buckets (if needed)
kubectl exec -n generic-repo <minio-pod> -- mc cp --recursive local/source-bucket/ local/dest-bucket/

# Remove bucket (DANGER!)
kubectl exec -n generic-repo <minio-pod> -- mc rb --force local/paperless-tenant-a/
```

## Testing and Verification

### Available Test Scripts

1. **scripts/provision-tenant-bucket.sh** - Create new tenant buckets
2. **scripts/test-bucket-isolation.sh** - Verify bucket isolation
3. **scripts/test-rclone-multibucket.sh** - Test rclone multi-bucket support

### Verification Checklist

- [ ] MinIO pod is running
- [ ] MinIO service is accessible (9000, 9001)
- [ ] Credentials are properly configured in paless-secret
- [ ] Test buckets created successfully (tenant-a, tenant-b, tenant-c)
- [ ] Files uploaded to each bucket without errors
- [ ] Bucket isolation verified (no cross-bucket file access)
- [ ] rclone sidecar can access multiple buckets
- [ ] Bucket provisioning completes in <5 seconds
- [ ] No errors in MinIO logs
- [ ] Storage capacity is sufficient for workload

## Troubleshooting

### Issue: MinIO pod not starting

```bash
# Check pod status
kubectl describe pod -n generic-repo -l app=minio

# Check logs
kubectl logs -n generic-repo -l app=minio

# Common causes:
# - Storage class not available
# - Insufficient resources
# - Secret not found
```

### Issue: Cannot create buckets

```bash
# Verify credentials
kubectl get secret paless-secret -n generic-repo -o yaml

# Test MinIO connectivity
kubectl exec -n generic-repo <minio-pod> -- mc alias ls

# Check MinIO health
kubectl exec -n generic-repo <minio-pod> -- curl http://localhost:9000/minio/health/live
```

### Issue: rclone mount failing

```bash
# Check rclone logs
kubectl logs -n generic-repo <pod-name> -c rclone

# Common causes:
# - Bucket doesn't exist
# - Incorrect credentials in env vars
# - Insufficient permissions (privileged mode required)
```

## Future Enhancements

1. **Multi-node MinIO**: Distributed setup for high availability
2. **IAM Policies**: Per-tenant access credentials
3. **Bucket Lifecycle Policies**: Automated cleanup and archival
4. **Object Versioning**: Enable versioning for document recovery
5. **Cross-region Replication**: Disaster recovery setup
6. **Prometheus Metrics**: Monitoring integration
7. **Automated Backup**: Regular bucket backups to external storage

## References

- MinIO Documentation: https://min.io/docs/minio/kubernetes/
- rclone Documentation: https://rclone.org/docs/
- K3s Storage: https://docs.k3s.io/storage
- Kubernetes StatefulSets: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
