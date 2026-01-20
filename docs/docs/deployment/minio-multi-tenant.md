# MinIO Multi-Tenant Storage Configuration

This document describes the MinIO configuration for per-tenant bucket isolation in Paless.

## Overview

Paless uses MinIO for object storage with a bucket-per-tenant isolation strategy. Each tenant gets a dedicated bucket to ensure data isolation and security.

## Bucket Naming Convention

**Convention**: `paperless-<tenant_id>`

### Examples
- Tenant ID: `tenant-a` → Bucket: `paperless-tenant-a`
- Tenant ID: `customer-123` → Bucket: `paperless-customer-123`
- Tenant ID: `org-acme` → Bucket: `paperless-org-acme`

### Tenant ID Requirements
- Must contain only lowercase letters, numbers, and hyphens
- Pattern: `^[a-z0-9-]+$`
- Example valid IDs: `tenant-a`, `customer-123`, `org-acme-corp`
- Example invalid IDs: `Tenant_A`, `customer.123`, `org@acme`

## MinIO Configuration

### StatefulSet Configuration
- **Storage Capacity**: 20Gi (configurable via PVC)
- **Endpoint**: `http://minio:9000` (internal cluster)
- **Console**: `http://minio:9001`
- **Credentials**: Stored in `paless-secret` Kubernetes secret
  - `minio-root-user`: MinIO root username
  - `minio-root-password`: MinIO root password

### Current Configuration Summary
```yaml
Storage: 20Gi (local-path StorageClass)
Replicas: 1 (StatefulSet)
Memory: 512Mi request, 1Gi limit
CPU: 500m request, 1 core limit
Health checks: Enabled (liveness & readiness probes)
```

## Bucket Provisioning

### Automated Provisioning Script
Use the provided script to create tenant buckets:

```bash
# Create a new tenant bucket
./scripts/provision-tenant-bucket.sh <tenant_id> [namespace]

# Examples
./scripts/provision-tenant-bucket.sh tenant-a
./scripts/provision-tenant-bucket.sh customer-123 paless
```

### Performance
- Bucket creation time: **< 5 seconds**
- Script includes automatic verification

### Manual Provisioning (kubectl)
If needed, you can manually create buckets:

```bash
# Get MinIO pod name
MINIO_POD=$(kubectl get pods -n paless -l app=minio -o jsonpath='{.items[0].metadata.name}')

# Create bucket
kubectl exec -n paless $MINIO_POD -- sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD
    mc mb local/paperless-<tenant_id>
    mc ls local/
"
```

## Bucket Isolation

### Access Control
MinIO supports bucket-level IAM policies for strict tenant isolation:

1. **Default Configuration**: Root user has access to all buckets
2. **Production Setup**: Create per-tenant IAM users with restricted policies

### Example Tenant Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": ["arn:aws:s3:::paperless-tenant-a/*"]
    }
  ]
}
```

### Creating Tenant-Specific Users
```bash
# Create user for tenant-a
kubectl exec -n paless $MINIO_POD -- sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD
    mc admin user add local tenant-a-user tenant-a-password
    mc admin policy attach local tenant-a-policy --user tenant-a-user
"
```

## rclone Sidecar Compatibility

The rclone sidecars in `paless-web` and `paless-worker` deployments can work with multiple tenant buckets:

### Current Configuration
```yaml
# rclone mounts single bucket (legacy)
command: rclone mount minio:paperless-media /mnt/media ...
```

### Multi-Tenant Configuration
For multi-tenant support, the rclone mount can be configured per-tenant:

```yaml
# Example: Mount specific tenant bucket
command: rclone mount minio:paperless-${TENANT_ID} /mnt/media ...
```

### Dynamic Tenant Routing
In a true multi-tenant deployment:
1. Each pod instance is assigned to a specific tenant
2. The `TENANT_ID` environment variable determines which bucket to mount
3. rclone mounts the appropriate `paperless-${TENANT_ID}` bucket

## Storage Management

### Check Storage Capacity
```bash
# Using test script
./scripts/test-tenant-isolation.sh

# Manual check
kubectl exec -n paless $MINIO_POD -- df -h /data
```

### List All Tenant Buckets
```bash
kubectl exec -n paless $MINIO_POD -- sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD
    mc ls local/ | grep 'paperless-'
"
```

### Monitor MinIO Logs
```bash
# Check for errors
kubectl logs -n paless $MINIO_POD --tail=100 | grep -i error

# Follow logs in real-time
kubectl logs -n paless $MINIO_POD -f
```

## Testing

### Automated Test Suite
Run the comprehensive test suite:

```bash
./scripts/test-tenant-isolation.sh
```

This test suite verifies:
- ✓ Creation of multiple tenant buckets
- ✓ File uploads to each bucket
- ✓ Bucket isolation (cross-tenant access control)
- ✓ Storage capacity sufficiency
- ✓ No errors in MinIO logs
- ✓ Bucket provisioning performance (< 5s)

### Manual Testing
```bash
# Create test buckets
./scripts/provision-tenant-bucket.sh tenant-a
./scripts/provision-tenant-bucket.sh tenant-b
./scripts/provision-tenant-bucket.sh tenant-c

# Verify buckets exist
kubectl exec -n paless $MINIO_POD -- sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD
    mc ls local/
"

# Upload test file
kubectl exec -n paless $MINIO_POD -- sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD
    echo 'test data' > /tmp/test.txt
    mc cp /tmp/test.txt local/paperless-tenant-a/test.txt
    mc ls local/paperless-tenant-a/
"
```

## Troubleshooting

### Bucket Creation Fails
```bash
# Check MinIO pod status
kubectl get pods -n paless -l app=minio

# Check MinIO logs
kubectl logs -n paless -l app=minio --tail=50

# Verify credentials
kubectl get secret paless-secret -n paless -o yaml
```

### Storage Full
```bash
# Check storage usage
kubectl exec -n paless $MINIO_POD -- df -h /data

# If needed, increase PVC size (requires storage class support)
kubectl patch pvc minio-data-minio-0 -n paless -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
```

### Access Denied Errors
1. Verify credentials in `paless-secret`
2. Check IAM policies if using tenant-specific users
3. Ensure bucket names follow the convention

## Production Recommendations

1. **Increase Storage**: Scale from 20Gi based on tenant count and usage
2. **Enable IAM Policies**: Create per-tenant users instead of using root credentials
3. **Add Monitoring**: Track bucket size, request rates, and error rates
4. **Backup Strategy**: Implement regular backups of MinIO data volume
5. **Consider Replication**: For HA, deploy MinIO in distributed mode

## References

- [MinIO Documentation](https://min.io/docs/)
- [MinIO Client (mc) Guide](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [rclone MinIO Configuration](https://rclone.org/s3/#minio)
