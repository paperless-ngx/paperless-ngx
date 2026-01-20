---
sidebar_position: 4
title: PostgreSQL StatefulSet
description: Deploy and configure PostgreSQL as a StatefulSet for Paperless NGX multi-tenancy
---

# PostgreSQL StatefulSet Configuration

This guide covers deploying PostgreSQL as a Kubernetes StatefulSet for Paperless NGX, with configuration optimized for multi-tenant architecture support.

## Overview

PostgreSQL serves as the primary data store for Paperless NGX. The StatefulSet deployment ensures:

- **Data Persistence**: PersistentVolume backing preserves database across pod restarts
- **Stable Network Identity**: StatefulSet provides predictable pod naming (`postgres-0`)
- **Initialization**: Automatic schema setup and multi-tenant preparation on first deployment
- **Health Monitoring**: Liveness and readiness probes ensure cluster health

## Architecture

### StatefulSet Design

```yaml
# Key StatefulSet properties
serviceName: postgres              # Headless service for stable DNS
replicas: 1                        # Single replica (HA requires additional setup)
volumeClaimTemplate:
  - name: postgres-data
    size: 10Gi                     # Configurable based on data retention
    storageClass: local-path       # Change for cloud deployments
```

### Network Configuration

| Component | Type | Endpoint | Purpose |
|-----------|------|----------|---------|
| Service | ClusterIP | `postgres:5432` | Internal cluster access |
| DNS | Headless | `postgres-0.postgres:5432` | Direct pod access |
| Port | TCP | 5432 | PostgreSQL protocol |

## Deployment

### Prerequisites

- Kubernetes 1.20+ cluster
- kubectl configured with cluster access
- 10Gi+ available storage
- `local-path` StorageClass (or configure alternative)

### Step 1: Create StorageClass (Development)

For local development clusters (K3s), use the pre-configured `local-path` StorageClass:

```bash
# Verify storage class exists
kubectl get storageclass local-path
```

For production, specify your cloud provider's StorageClass:

```yaml
# AWS EBS example
storageClassName: ebs-sc

# Google Cloud Persistent Disk example
storageClassName: standard-rwo

# Azure Disk example
storageClassName: managed-premium
```

### Step 2: Deploy PostgreSQL StatefulSet

Deploy the PostgreSQL StatefulSet using Kustomize:

```bash
# From repository root
kubectl apply -k k8s/base

# Or specific overlay
kubectl apply -k k8s/overlays/dev
```

### Step 3: Verify Deployment

Monitor the StatefulSet rollout:

```bash
# Watch pod creation
kubectl get pods -n paless -l app=postgres -w

# Check StatefulSet status
kubectl get statefulset -n paless postgres

# View pod details
kubectl describe pod postgres-0 -n paless
```

Wait for the pod to reach `Running` status and both probes to show as ready.

## Configuration

### Resource Allocation

```yaml
# Requests (guaranteed minimum)
resources:
  requests:
    memory: 256Mi
    cpu: 250m

# Limits (maximum allowed)
  limits:
    memory: 1Gi
    cpu: 1000m
```

**Tuning Guidance:**
- **Small deployments** (< 100K documents): Keep current requests
- **Medium deployments** (100K-1M documents): Increase memory to 512Mi request / 2Gi limit
- **Large deployments** (> 1M documents): Increase to 1Gi request / 4Gi limit, consider separate read replicas

### Connection Pool Configuration

PostgreSQL supports `max_connections=100` by default. For multi-tenant deployments:

```yaml
# Connection pool sizing
web_pods: 3
worker_pods: 3
connections_per_pod: 5
total_connections_needed: 30
safety_margin: 50%
total_with_margin: 45
```

With 100 max connections available, this allows headroom for 2-3x scaling.

:::info Connection Pooling Best Practice
For production deployments with 5+ pods, implement **PgBouncer** or **Pgpool-II** as a connection pool proxy to prevent connection exhaustion.
:::

### Storage Configuration

```yaml
# Volume mount point
volumeMounts:
  - name: postgres-data
    mountPath: /var/lib/postgresql/data
    subPath: postgres

# Persistence template
volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: local-path
      resources:
        requests:
          storage: 10Gi
```

**Storage Sizing Factors:**
- Current database size: ~13MB (baseline)
- Average document size: ~1-10MB
- Historical data retention: Scale based on retention policy
- Growth buffer: Plan 1.5x current size for 12 months

### Health Checks

PostgreSQL includes probe configurations for automatic failure detection:

```yaml
livenessProbe:
  exec:
    command: ["pg_isready", "-U", "postgres"]
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  exec:
    command: ["pg_isready", "-U", "postgres"]
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Multi-Tenancy Support

### Prepared Database Extensions

The PostgreSQL deployment includes pre-installed extensions for multi-tenant support:

#### uuid-ossp (v1.1)

Generates universally unique identifiers for tenant IDs:

```sql
SELECT uuid_generate_v4() AS tenant_id;
-- Output: d296f28d-5546-4424-bc82-a9c7a3989da9
```

**Use Case**: Creating unique tenant identifiers during onboarding

#### pgcrypto (v1.4)

Provides cryptographic functions for sensitive data:

```sql
SELECT encode(digest('sensitive_data', 'sha256'), 'hex') AS hash;
-- Output: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Use Cases**:
- Hashing tenant credentials
- Encrypting sensitive configuration
- Generating secure tokens

### Tables Ready for Multi-Tenancy

The following 11 tables have been identified with `ModelWithOwner` base class, requiring `tenant_id` column addition:

1. `documents_correspondent` - Contact information (senders/recipients)
2. `documents_document` - Core document metadata
3. `documents_documenttype` - Document classification types
4. `documents_storagepath` - File storage paths
5. `documents_tag` - Document categorization tags
6. `documents_paperlesstask` - Background tasks
7. `documents_savedview` - User-defined document views
8. `documents_sharelink` - Public sharing links
9. `paperless_mail_mailaccount` - Email account configurations
10. `paperless_mail_mailrule` - Email processing rules
11. `paperless_mail_processedmail` - Email processing history

:::tip Schema Migration
See the complete schema export in `/workspace/docs/database/schema-before-multi-tenant.sql` (209KB) for detailed column definitions and constraints to plan migrations.
:::

## Administration

### Connect to Database

Direct connection from your local machine:

```bash
# Port-forward PostgreSQL service
kubectl port-forward -n paless svc/postgres 5432:5432

# Connect with psql
psql -h localhost -U postgres -d paperless
```

### Backup and Restore

#### Full Database Backup

```bash
# Backup to file
kubectl exec -n paless postgres-0 -- \
  pg_dump -U postgres paperless | \
  gzip > paperless-backup-$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip < paperless-backup-20260120.sql.gz | \
  kubectl exec -i -n paless postgres-0 -- \
  psql -U postgres paperless
```

#### Table-Level Backup

```bash
# Backup specific table
kubectl exec -n paless postgres-0 -- \
  pg_dump -U postgres -t documents_document paperless | \
  gzip > documents-backup.sql.gz
```

### Monitoring

#### View Database Size

```bash
kubectl exec -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "SELECT pg_size_pretty(pg_database_size('paperless'));"
```

#### Check Table Sizes

```bash
kubectl exec -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

#### Monitor Connection Usage

```bash
kubectl exec -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "SELECT count(*) FROM pg_stat_activity;"

# View active connections
kubectl exec -n paless postgres-0 -- \
  psql -U postgres postgres -c \
  "SELECT usename, application_name, state, query_start
   FROM pg_stat_activity
   WHERE state != 'idle';"
```

### Performance Tuning

#### Enable Slow Query Logging

```bash
# Set log duration threshold (adjust value as needed)
kubectl exec -n paless postgres-0 -- \
  psql -U postgres postgres -c \
  "ALTER SYSTEM SET log_min_duration_statement = 1000;
   SELECT pg_reload_conf();"

# View slow queries
kubectl logs -n paless postgres-0 | grep duration
```

#### Analyze Query Plans

```bash
# Connect and run EXPLAIN
kubectl exec -i -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "EXPLAIN ANALYZE
   SELECT * FROM documents_document
   WHERE created > NOW() - INTERVAL '7 days';"
```

## Troubleshooting

### Pod Not Starting

**Check pod status:**

```bash
kubectl describe pod postgres-0 -n paless
kubectl logs postgres-0 -n paless
```

**Common issues:**
- PersistentVolumeClaim not bound: Verify StorageClass and available storage
- Image pull errors: Check image registry access
- Port conflicts: Verify port 5432 is available

### Connection Refused

```bash
# Verify service is running
kubectl get svc -n paless postgres

# Test connectivity from pod
kubectl run -it --rm debug --image=postgres:18 --restart=Never -- \
  psql -h postgres -U postgres -d postgres -c "SELECT version();"
```

### High Memory Usage

```bash
# Check current memory usage
kubectl top pod postgres-0 -n paless

# Check cache hit ratio
kubectl exec -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "SELECT
     sum(heap_blks_read) as heap_read, sum(heap_blks_hit) as heap_hit,
     sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
   FROM pg_statio_user_tables;"
```

### Slow Queries

**Identify problematic queries:**

```bash
# Top tables by sequential scans
kubectl exec -n paless postgres-0 -- \
  psql -U postgres paperless -c \
  "SELECT relname, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
   FROM pg_stat_user_tables
   WHERE seq_scan > 100
   ORDER BY seq_scan DESC LIMIT 10;"

# Create missing indexes as needed
```

## Production Deployment

### High Availability Setup

For production, consider multi-replica StatefulSet:

```yaml
replicas: 3              # Primary + standby replicas
volumeClaimTemplate:
  storage: 50Gi          # Larger storage for HA setup

# Requires:
# - Streaming replication configuration
# - pg_basebackup for replica setup
# - WAL archiving to remote storage
```

### Backup Strategy

:::warning Critical for Production
Implement automated backups before production deployment.
:::

```bash
# Example: Daily backup to S3
# (Configure as CronJob in Kubernetes)
kubectl exec postgres-0 -- \
  pg_basebackup -D - | \
  aws s3 cp - s3://backup-bucket/postgres/$(date +%Y%m%d).tar.gz
```

### Monitoring Stack

Add Prometheus/Grafana monitoring:

```yaml
# Install postgres_exporter
helm install prometheus-postgres-exporter \
  prometheus-community/prometheus-postgres-exporter \
  --set postgresql.host=postgres \
  --namespace paless
```

### Security Hardening

1. **Network Policies**: Restrict PostgreSQL access to application pods only
2. **RBAC**: Create service account with minimal permissions
3. **Secrets Management**: Store credentials in encrypted etcd
4. **SSL/TLS**: Enable client certificate verification for remote connections
5. **Audit Logging**: Enable PostgreSQL logs for compliance

## Scaling Considerations

### Vertical Scaling (Larger Instance)

Increase resource limits and storage:

```bash
# Edit StatefulSet
kubectl edit statefulset postgres -n paless

# Update limits and volumeClaimTemplate size
# Requires pod restart for limits to take effect
```

### Horizontal Scaling (Read Replicas)

```yaml
# Requires custom streaming replication setup
# See PostgreSQL HA documentation for detailed configuration
```

## Related Documentation

- [Volume Configuration Guide](./volume-configuration.md) - PersistentVolume and PersistentVolumeClaim setup
- [Kubernetes Deployment Guide](./kubernetes-guide.md) - Complete multi-service deployment
- [Configuration Management](./configuration.md) - Environment variables and secrets
- [Multi-Tenant Preparation Report](../database/multi-tenant-preparation-report.md) - Database readiness assessment
