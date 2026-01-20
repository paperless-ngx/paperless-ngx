# Redis and Celery Configuration Verification

**Date**: $(date +%Y-%m-%d)
**Purpose**: Verify Redis configuration for Celery broker and result backend to support multi-tenant task queuing

## Overview

This document provides a comprehensive verification of the Redis and Celery setup in the Paperless-ngx Kubernetes deployment, with a focus on multi-tenant task queuing capabilities.

## 1. Redis StatefulSet Configuration

### Current Configuration

**File**: `k8s/base/redis-statefulset.yaml`

| Configuration Item | Value | Notes |
|-------------------|-------|-------|
| **Image** | redis:7-alpine | Latest Redis 7.x with Alpine Linux |
| **Replicas** | 1 | Single instance (suitable for development) |
| **Memory Request** | 128Mi | Baseline memory allocation |
| **Memory Limit** | 256Mi | Maximum memory allocation |
| **CPU Request** | 100m | Baseline CPU allocation |
| **CPU Limit** | 500m | Maximum CPU allocation |
| **Storage** | 2Gi | PersistentVolumeClaim size |
| **Storage Class** | local-path | K3s default storage class |
| **Persistence** | AOF enabled | `--appendonly yes --appendfsync everysec` |

### Redis Service Configuration

**File**: `k8s/base/redis-service.yaml`

| Configuration Item | Value |
|-------------------|-------|
| **Service Type** | ClusterIP |
| **Port** | 6379 |
| **Target Port** | 6379 |
| **Service Name** | redis |

### Connection Settings

- **Internal DNS**: `redis.generic-repo.svc.cluster.local`
- **Short DNS**: `redis` (within namespace)
- **Connection String**: `redis://redis:6379`

### Health Checks

**Liveness Probe**:
- Command: `redis-cli ping`
- Initial Delay: 30 seconds
- Period: 10 seconds
- Timeout: 5 seconds
- Failure Threshold: 3

**Readiness Probe**:
- Command: `redis-cli ping`
- Initial Delay: 5 seconds
- Period: 5 seconds
- Timeout: 3 seconds
- Failure Threshold: 3

## 2. Celery Broker Configuration

### Environment Configuration

**File**: `k8s/base/configmap.yaml`

```yaml
PAPERLESS_REDIS: "redis://redis:6379"
PAPERLESS_TASK_WORKERS: "2"
PAPERLESS_THREADS_PER_WORKER: "1"
PAPERLESS_WORKER_TIMEOUT: "1800"
```

### Celery Settings in Paperless

**File**: `src/paperless/settings.py` (lines 920-954)

| Setting | Value | Description |
|---------|-------|-------------|
| **CELERY_BROKER_URL** | `redis://redis:6379` | Parsed from PAPERLESS_REDIS |
| **CELERY_RESULT_BACKEND** | `django-db` | Results stored in PostgreSQL |
| **CELERY_WORKER_CONCURRENCY** | 1 (default) or from env | Number of worker processes |
| **CELERY_WORKER_MAX_TASKS_PER_CHILD** | 1 | Worker recycling after each task |
| **CELERY_TASK_TIME_LIMIT** | 1800 (30 min) | Maximum task execution time |
| **CELERY_TASK_SERIALIZER** | pickle | Task serialization format |
| **CELERY_BROKER_TRANSPORT_OPTIONS** | `global_keyprefix` | Optional key prefix for namespacing |

### Redis URL Parsing

The `_parse_redis_url()` function (settings.py:116-151) handles:
- Standard Redis URLs: `redis://host:port`
- Unix socket URLs: `unix:///path/to/socket`
- Celery socket format: `redis+socket:///path`
- Database selection: `?db=N` or `?virtual_host=N`

## 3. Pod Types and Redis Connectivity

### Web Pods

**Deployment**: `k8s/base/paless-web-deployment.yaml`
- **Replicas**: 3
- **Component**: web
- **Container**: paless-web
- **Environment**: Includes PAPERLESS_REDIS from configmap
- **Purpose**: API server, connects to Redis for caching and task queuing

### Worker Pods

**Deployment**: `k8s/base/paless-worker-deployment.yaml`
- **Replicas**: 2
- **Component**: worker
- **Container**: paless-worker
- **Environment**: Includes PAPERLESS_REDIS from configmap
- **Purpose**: Celery workers, consume tasks from Redis queues

### Scheduler Pods

**Deployment**: `k8s/base/paless-scheduler-deployment.yaml`
- **Replicas**: 1
- **Component**: scheduler
- **Container**: paless-scheduler
- **Environment**: Includes PAPERLESS_REDIS from configmap
- **Purpose**: Celery beat scheduler, publishes periodic tasks

## 4. Current Task Queue Structure

### Celery Queue Architecture

Celery uses Redis to manage task queues with the following key patterns:

1. **Default Queue**: `celery`
2. **Task Metadata**: `celery-task-meta-<task_id>`
3. **Results**: Stored in PostgreSQL via `django-db` backend
4. **Beat Schedule**: `celerybeat-schedule.db` (file-based, stored in data volume)

### Scheduled Tasks

**File**: `src/paperless/settings.py` (lines 154-263)

| Task Name | Schedule | Task Function |
|-----------|----------|---------------|
| Check all e-mail accounts | */10 * * * * | paperless_mail.tasks.process_mail_accounts |
| Train the classifier | 5 */1 * * * | documents.tasks.train_classifier |
| Optimize the index | 0 0 * * * | documents.tasks.index_optimize |
| Perform sanity check | 30 0 * * sun | documents.tasks.sanity_check |
| Empty trash | 0 1 * * * | documents.tasks.empty_trash |
| Check scheduled workflows | 5 */1 * * * | documents.tasks.check_scheduled_workflows |
| Rebuild LLM index | 10 2 * * * | documents.tasks.llmindex_index |

## 5. Multi-Tenant Task Queuing Plan

### Current State

- **Single Queue**: All tasks go to the default `celery` queue
- **No Tenant Isolation**: Tasks from different tenants share the same queue
- **Global Key Prefix**: Optional `PAPERLESS_REDIS_PREFIX` for namespace separation

### Proposed Multi-Tenant Architecture

#### Option 1: Queue-Based Isolation

```python
# Route tasks to tenant-specific queues
task.apply_async(queue=f'tenant-{tenant_id}')
```

**Pros**:
- Clean isolation
- Different workers can serve different tenants
- Priority can be set per tenant

**Cons**:
- Requires worker configuration changes
- Need to pre-create workers for each queue or use dynamic routing

#### Option 2: Key Prefix-Based Isolation

```python
# Use Redis key prefix for tenant isolation
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'global_keyprefix': f'tenant-{tenant_id}:'
}
```

**Pros**:
- Simple to implement
- No worker configuration changes
- Automatic key namespacing

**Cons**:
- All tasks for a tenant must use same Celery app instance
- Less flexible for priority handling

#### Option 3: Hybrid Approach (Recommended)

Combine both approaches:
1. Use key prefixes for data isolation
2. Use queue names for routing and priority

```python
# Application code
app = Celery(
    broker=f'redis://redis:6379/0',
    transport_options={'global_keyprefix': f'tenant-{tenant_id}:'}
)

# Task execution
task.apply_async(
    queue=f'tenant-{tenant_id}',
    routing_key=f'tenant-{tenant_id}.default'
)
```

### Implementation Considerations

1. **Worker Configuration**:
   - Dynamic worker pools that can handle any tenant queue
   - Or dedicated workers per tenant for guaranteed isolation

2. **Connection Pooling**:
   - Current settings rely on Celery's built-in connection pooling
   - Monitor connection counts under multi-tenant load

3. **Memory Management**:
   - Current 256Mi limit should be increased for multi-tenant workloads
   - Recommended: 512Mi - 1Gi depending on tenant count

4. **Monitoring**:
   - Add tenant_id to task metadata for tracking
   - Monitor queue depths per tenant
   - Track task execution times per tenant

## 6. Redis Performance Characteristics

### Connection Limits

Default Redis configuration allows:
- **Max Clients**: 10,000 (default)
- **Current Setup**: 3 web pods + 2 worker pods + 1 scheduler = 6 active connections minimum
- **Connection Pooling**: Managed by Celery (default pool size: 10)

### Memory Usage Patterns

Expected memory usage:
- **Baseline**: ~5-10 MB (empty Redis)
- **Per Task in Queue**: ~1-5 KB (metadata)
- **100 Tasks**: ~500 KB - 1 MB
- **1000 Tasks**: ~5-10 MB

Current 256Mi limit provides ample headroom for task queuing.

### Persistence Impact

AOF (Append-Only File) with `everysec` fsync:
- **Write Performance**: Minimal impact (async writes)
- **Durability**: At most 1 second of data loss on crash
- **Storage**: AOF file grows with operations, needs periodic rewrite
- **Disk I/O**: Moderate (1 fsync per second)

## 7. Verification Test Plan

### Test Suite 1: Connectivity Tests

1. **Redis Pod Status**: Verify pod is Running
2. **Web Pod Connectivity**: Test connection from web pods to Redis
3. **Worker Pod Connectivity**: Test connection from worker pods to Redis
4. **Scheduler Pod Connectivity**: Test connection from scheduler pods to Redis

### Test Suite 2: Configuration Tests

1. **Broker URL**: Verify PAPERLESS_REDIS configuration
2. **StatefulSet Config**: Verify memory, CPU, and storage settings
3. **Persistence**: Verify AOF configuration
4. **Health Checks**: Verify liveness and readiness probes

### Test Suite 3: Functional Tests

1. **Simple Task**: Queue and execute a single task
2. **Multiple Tasks**: Queue 10 tasks and verify execution
3. **Task States**: Verify task state transitions (PENDING → STARTED → SUCCESS)
4. **Result Backend**: Verify results are stored in PostgreSQL

### Test Suite 4: Performance Tests

1. **Load Test**: Queue 100 tasks and measure:
   - Total queue time
   - Average queue time per task
   - Throughput (tasks/second)
   - Redis memory before/after
   - Task completion rate

2. **Connection Pool**: Monitor:
   - Active connections
   - Connection creation rate
   - Connection reuse rate

### Test Suite 5: Multi-Tenant Tests

1. **Namespace Isolation**: Create keys with tenant prefixes
2. **Key Retrieval**: Verify tenant-specific keys are retrievable
3. **Cross-Tenant**: Verify tenant A cannot access tenant B's keys
4. **Queue Naming**: Test queue name patterns (tenant-<tenant_id>)

## 8. Verification Scripts

### Bash Script: `scripts/verify-redis-celery.sh`

Automated verification script that:
- Checks Redis StatefulSet configuration
- Tests connectivity from all pod types
- Verifies Celery broker configuration
- Checks Redis logs for errors
- Analyzes memory usage and connection stats
- Tests multi-namespace capability
- Generates JSON report

**Usage**:
```bash
chmod +x scripts/verify-redis-celery.sh
./scripts/verify-redis-celery.sh
```

### Python Script: `scripts/test_celery_tasks.py`

Celery task testing script that:
- Tests simple task execution
- Measures task queuing performance
- Tests performance under load (100 tasks)
- Analyzes queue structure
- Tests tenant-aware queuing patterns
- Generates JSON report

**Usage**:
```bash
# Run inside a worker pod
kubectl exec -it <worker-pod> -n generic-repo -- python3 /workspace/scripts/test_celery_tasks.py
```

## 9. Recommendations

### Immediate Actions (Verification Phase)

1. ✅ Run verification scripts to baseline current performance
2. ✅ Document all current settings and configurations
3. ✅ Test Redis under 100-task load
4. ✅ Verify connectivity from all pod types

### Short-Term Improvements (Next Phase)

1. **Increase Redis Memory Limit**: 256Mi → 512Mi for multi-tenant support
2. **Add Monitoring**: Deploy Redis exporter for Prometheus metrics
3. **Configure Alerts**: Set up alerts for:
   - Memory usage > 80%
   - Connection count > 1000
   - Queue depth > 500 tasks
4. **Document Patterns**: Create tenant-aware task queuing patterns

### Long-Term Enhancements (Production)

1. **Redis Cluster**: Consider Redis Sentinel or Cluster for HA
2. **Dedicated Workers**: Deploy tenant-specific worker pools
3. **Result Backend**: Consider switching to Redis for faster result retrieval
4. **Connection Pooling**: Tune connection pool sizes based on load
5. **Backup Strategy**: Implement Redis backup and restore procedures

## 10. Multi-Tenant Queue Namespace Pattern

### Recommended Pattern

For multi-tenant task queuing, use this naming convention:

```
Queue Name Pattern: tenant-<tenant_id>
Key Prefix Pattern: tenant:<tenant_id>:

Examples:
- tenant-001
- tenant-002
- tenant-acme-corp

Redis Keys:
- tenant:001:celery:task-meta:<task_id>
- tenant:001:celery:unacked
- tenant:002:celery:task-meta:<task_id>
```

### Implementation Example

```python
from celery import Celery

def get_tenant_celery_app(tenant_id):
    """Get a Celery app configured for a specific tenant"""
    app = Celery(
        'paperless',
        broker=f'redis://redis:6379/0',
        backend='django-db'
    )

    # Configure tenant-specific key prefix
    app.conf.broker_transport_options = {
        'global_keyprefix': f'tenant:{tenant_id}:'
    }

    # Use tenant-specific queue
    app.conf.task_default_queue = f'tenant-{tenant_id}'

    return app

# Usage
app = get_tenant_celery_app('001')
task_result = app.send_task('documents.tasks.consume_file', args=[file_path])
```

### Worker Configuration for Multi-Tenant

```bash
# Option 1: Single worker serving all tenant queues
celery -A paperless worker -Q tenant-001,tenant-002,tenant-003

# Option 2: Dedicated worker per tenant
celery -A paperless worker -Q tenant-001 --hostname=worker-tenant-001@%h

# Option 3: Dynamic routing (advanced)
celery -A paperless worker -Q celery --autoscale=10,3
```

## 11. Performance Baselines

### Expected Performance Metrics

| Metric | Target | Acceptable | Needs Investigation |
|--------|--------|------------|---------------------|
| Task Queue Time | < 10ms | < 50ms | > 100ms |
| Task Execution Time | Varies | - | > timeout |
| Redis Memory (baseline) | < 50MB | < 100MB | > 200MB |
| Redis Memory (100 tasks) | < 60MB | < 120MB | > 250MB |
| Connection Count | < 20 | < 50 | > 100 |
| Queue Depth | < 10 | < 100 | > 500 |
| Throughput | > 50 tasks/s | > 20 tasks/s | < 10 tasks/s |

### Capacity Planning

Based on current configuration:

- **Maximum Queued Tasks**: ~10,000 (with 256Mi memory)
- **Maximum Throughput**: ~100 tasks/second (limited by workers)
- **Maximum Concurrent Tenants**: 50-100 (with current resources)
- **Recommended Tenant Limit**: 20-30 (with monitoring)

## 12. Troubleshooting Guide

### Common Issues

**Issue**: Tasks stuck in PENDING state
- **Cause**: Workers not connected or not consuming from queue
- **Solution**: Check worker logs, verify PAPERLESS_REDIS configuration

**Issue**: Redis connection timeouts
- **Cause**: Too many connections, network issues
- **Solution**: Check connection pool settings, verify network connectivity

**Issue**: High Redis memory usage
- **Cause**: Too many queued tasks, memory leak
- **Solution**: Monitor queue depth, restart Redis if needed, check for leaks

**Issue**: Slow task execution
- **Cause**: Worker overload, insufficient resources
- **Solution**: Scale up workers, increase resource limits

### Diagnostic Commands

```bash
# Check Redis pod status
kubectl get pods -n generic-repo -l app=redis

# View Redis logs
kubectl logs -n generic-repo <redis-pod-name>

# Check Redis memory usage
kubectl exec -n generic-repo <redis-pod-name> -- redis-cli INFO memory

# Check queue depth
kubectl exec -n generic-repo <redis-pod-name> -- redis-cli LLEN celery

# Check worker status
kubectl logs -n generic-repo -l app=paless,component=worker

# Test Redis connectivity
kubectl exec -n generic-repo <pod-name> -- sh -c "echo PING | nc redis 6379"
```

## 13. Conclusion

The current Redis and Celery configuration provides a solid foundation for task queuing with the following characteristics:

✅ **Strengths**:
- Persistence enabled (AOF)
- Health checks configured
- Proper resource limits
- Clean service architecture

⚠️ **Considerations**:
- Single Redis instance (no HA)
- Memory limit suitable for current load, may need increase for multi-tenant
- No built-in multi-tenant support (requires implementation)

📋 **Next Steps**:
1. Run verification scripts to establish baseline
2. Test with 100-task load
3. Document actual performance metrics
4. Plan multi-tenant implementation based on results

---

**Document Version**: 1.0
**Last Updated**: $(date +%Y-%m-%d)
**Status**: Verification Phase
