---
sidebar_position: 5
title: Redis and Celery Configuration
description: Configure Redis as Celery broker and task queue for multi-tenant deployments
---

# Redis and Celery Configuration

This guide covers configuring Redis as the Celery message broker and managing task queuing for Paperless-ngx, particularly in multi-tenant deployments.

## Overview

Redis serves two critical roles in Paperless-ngx:

1. **Celery Broker** - Message queue for distributed task processing
2. **Cache Backend** - Caching layer for database queries and WebSocket messaging

Celery enables asynchronous task execution, allowing document processing, OCR, and other long-running operations to run without blocking the web interface.

## Redis URL Configuration

### Environment Variable

Configure Redis connectivity using the `PAPERLESS_REDIS` environment variable:

```env
PAPERLESS_REDIS=redis://localhost:6379
```

### URL Formats

Paperless supports multiple Redis connection formats:

**Standard TCP Connection:**
```env
PAPERLESS_REDIS=redis://localhost:6379
PAPERLESS_REDIS=redis://redis-server:6379
PAPERLESS_REDIS=redis://username:password@redis-server:6379/0
```

**Unix Socket Connection:**
```env
PAPERLESS_REDIS=unix:///var/run/redis/redis.sock
PAPERLESS_REDIS=unix:///var/run/redis/redis.sock?db=0
```

**TLS/SSL Connection:**
```env
PAPERLESS_REDIS=rediss://redis-server:6380
PAPERLESS_REDIS=rediss://username:password@redis-server:6380/0
```

### Database Selection

By default, Redis database 0 is used. To use a different database:

```env
PAPERLESS_REDIS=redis://localhost:6379/1
```

### Redis Key Prefix

Separate multi-tenant deployments or environments using the `PAPERLESS_REDIS_PREFIX`:

```env
PAPERLESS_REDIS=redis://localhost:6379
PAPERLESS_REDIS_PREFIX=tenant-a:
PAPERLESS_REDIS_PREFIX=tenant-b:
```

Key prefixes automatically isolate:
- Celery task queues
- Cache entries
- WebSocket channel layers
- Session data

:::tip Multi-Tenant Isolation
Using unique `PAPERLESS_REDIS_PREFIX` values for each tenant ensures complete isolation of task queues and cache data, even when sharing a single Redis instance.
:::

## Celery Broker Configuration

### Broker Settings

Paperless configures Celery with Redis as the message broker:

| Setting | Default | Purpose |
|---------|---------|---------|
| `CELERY_BROKER_URL` | `redis://localhost:6379` | Broker connection string |
| `CELERY_BROKER_CONNECTION_RETRY` | `True` | Retry on broker connection failures |
| `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP` | `True` | Retry broker connection during startup |
| `CELERY_BROKER_TRANSPORT_OPTIONS` | Global key prefix | Options for broker transport |

### Connection Options

Control broker behavior using environment variables:

**Connection Timeout:**
```env
PAPERLESS_REDIS=redis://localhost:6379?timeout=5
```

**Connection Pool Size:**
```env
PAPERLESS_REDIS=redis://localhost:6379?max_connections=50
```

## Result Backend Configuration

Paperless uses Django database as the Celery result backend:

```python
CELERY_RESULT_BACKEND = "django-db"
```

Task results are stored in the PostgreSQL database, providing:
- Persistent result storage
- Access to task status and results through the web interface
- No additional Redis usage required

### Result Tracking

Task results are tracked with extended information:

```python
CELERY_RESULT_EXTENDED = True
CELERY_TASK_TRACK_STARTED = True
```

Query task status:
```python
from celery.result import AsyncResult

result = AsyncResult(task_id)
print(result.status)      # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'
print(result.result)      # Task result or exception
print(result.traceback)   # Exception traceback if failed
```

## Task Queue Configuration

### Worker Configuration

Configure Celery workers using environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PAPERLESS_TASK_WORKERS` | `1` | Number of concurrent worker processes |
| `PAPERLESS_WORKER_TIMEOUT` | `1800` | Task timeout in seconds (30 minutes) |

**Example - Multiple Workers:**
```env
PAPERLESS_TASK_WORKERS=4
PAPERLESS_WORKER_TIMEOUT=3600
```

:::warning Task Timeout
Set `PAPERLESS_WORKER_TIMEOUT` appropriately for your document sizes:
- Small documents (< 10 pages): 1800 seconds (30 minutes)
- Medium documents (10-100 pages): 3600 seconds (1 hour)
- Large documents (> 100 pages): 7200 seconds (2 hours)
:::

### Task Serialization

Paperless uses pickle serialization for task arguments:

```python
CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["application/json", "application/x-python-serialize"]
```

This enables passing complex Python objects (file handles, models) directly to tasks.

### Beat Schedule

Periodic tasks are managed by Celery Beat:

```env
PAPERLESS_BEAT_SCHEDULE_FILENAME=/data/celerybeat-schedule.db
```

The schedule database stores periodic task timing information. Use a persistent volume to maintain scheduling across restarts.

## Multi-Tenant Task Queuing

### Isolated Task Queues

For multi-tenant deployments, create separate task queues per tenant:

**Configuration:**
```env
# Tenant A
PAPERLESS_NAMESPACE=tenant-a
PAPERLESS_REDIS=redis://redis:6379/0
PAPERLESS_REDIS_PREFIX=tenant-a:

# Tenant B
PAPERLESS_NAMESPACE=tenant-b
PAPERLESS_REDIS=redis://redis:6379/1
PAPERLESS_REDIS_PREFIX=tenant-b:
```

**Kubernetes Example:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: paperless-tenant-a-config
data:
  PAPERLESS_REDIS: "redis://redis-service:6379/0"
  PAPERLESS_REDIS_PREFIX: "tenant-a:"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: paperless-tenant-b-config
data:
  PAPERLESS_REDIS: "redis://redis-service:6379/1"
  PAPERLESS_REDIS_PREFIX: "tenant-b:"
```

### Queue Isolation Benefits

- **Data Isolation**: Tasks for tenant A don't access tenant B's cache
- **Performance**: Each tenant's queue is independent
- **Debugging**: Easy to filter logs by tenant prefix
- **Scaling**: Can scale workers per tenant

### Monitoring Task Queues

View queue status per tenant:

```bash
# View all keys for tenant-a
redis-cli --scan --pattern "tenant-a:*"

# Count tasks in queue
redis-cli LLEN "tenant-a:celery"

# Inspect task details
redis-cli LRANGE "tenant-a:celery" 0 -1
```

## Redis Instance Requirements

### Persistence Configuration

For production, enable Redis persistence:

**RDB Snapshots:**
```conf
save 900 1      # Save if 1+ keys changed in 900 seconds
save 300 10     # Save if 10+ keys changed in 300 seconds
save 60 10000   # Save if 10000+ keys changed in 60 seconds
```

**AOF (Append-Only File):**
```conf
appendonly yes
appendfsync everysec
```

### Memory Management

Redis memory usage depends on:
- Number of pending tasks
- Size of cached data
- Number of concurrent connections
- Document metadata cache

**Sizing Guidelines:**

| Deployment | Expected Memory | Recommended Redis Memory |
|------------|-----------------|--------------------------|
| Small (< 10k docs) | 500MB | 1GB |
| Medium (10k-100k docs) | 5GB | 8GB |
| Large (> 100k docs) | 20GB+ | 32GB+ |

**Memory Limits:**
```env
# Docker
REDIS_MEMORY_LIMIT=2g

# Kubernetes
limits:
  memory: "2Gi"
```

### Eviction Policy

Set appropriate key eviction when memory is full:

```conf
maxmemory-policy allkeys-lru
```

Options:
- `noeviction` - Return error when full (default)
- `allkeys-lru` - Evict least recently used keys
- `volatile-lru` - Evict expiring keys (least recently used)
- `allkeys-random` - Evict random keys
- `volatile-ttl` - Evict keys with shortest TTL

:::warning Critical Tasks
Using `allkeys-lru` may evict pending Celery tasks. For production, either:
1. Provision sufficient Redis memory
2. Use `volatile-lru` with task TTLs
3. Use dedicated Redis instance for Celery
:::

## Health Monitoring

### Health Check Commands

Monitor Redis connectivity:

```bash
# Test connection
redis-cli ping

# Check memory usage
redis-cli INFO memory

# Check connected clients
redis-cli CLIENT LIST

# Monitor broker activity
redis-cli SUBSCRIBE celery
```

### Kubernetes Health Checks

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: paperless
spec:
  containers:
  - name: paperless
    livenessProbe:
      exec:
        command:
        - /bin/sh
        - -c
        - "python -c 'from redis import Redis; Redis.from_url(\"${PAPERLESS_REDIS}\").ping()'"
      initialDelaySeconds: 30
      periodSeconds: 10
```

### Monitoring Celery Workers

Check worker status:

```bash
celery -A paperless.celery inspect active
celery -A paperless.celery inspect stats
celery -A paperless.celery inspect reserved
```

## Troubleshooting

### Connection Issues

**Error: Connection refused**
```
Error: Error -1 connecting to localhost:6379. Connection refused.
```

**Solution:**
1. Verify Redis is running: `redis-cli ping`
2. Check `PAPERLESS_REDIS` environment variable
3. Verify network connectivity to Redis host
4. Check firewall rules

### Task Queue Stalls

**Symptom:** Tasks remain in queue, not being processed

**Diagnostic:**
```bash
# Check Redis queue
redis-cli LLEN celery

# Check worker status
celery -A paperless.celery inspect active

# Check for stuck tasks
redis-cli KEYS "celery-task-meta-*"
```

**Solution:**
1. Restart Celery workers: `supervisorctl restart paperless-celery`
2. Flush old task results: `redis-cli DEL "celery-task-meta-*"`
3. Check worker logs for errors

### Memory Issues

**Error: OOM command not allowed when used memory > 'maxmemory'**

**Solution:**
1. Increase Redis memory limit
2. Enable key eviction policy
3. Clear expired keys: `redis-cli MEMORY PURGE`
4. Monitor growth: `redis-cli INFO memory`

### Multi-Tenant Isolation Issues

**Symptom:** Tasks from one tenant appear in another's queue

**Diagnostic:**
```bash
# Check key prefixes
redis-cli --scan --pattern "tenant-a:*" | wc -l
redis-cli --scan --pattern "tenant-b:*" | wc -l
```

**Solution:**
1. Verify `PAPERLESS_REDIS_PREFIX` is set for each deployment
2. Verify separate Redis databases or instances are used
3. Check for any hardcoded queue names in application code
4. Restart all affected workers

## Security Best Practices

### Authentication

Require authentication for Redis:

```env
PAPERLESS_REDIS=redis://:password@redis-server:6379
```

**Kubernetes Secret:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: redis-credentials
type: Opaque
stringData:
  connection-string: "redis://:secure-password@redis-service:6379"
```

### Network Security

Restrict Redis access:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: redis-access
spec:
  podSelector:
    matchLabels:
      app: redis
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: paperless
    ports:
    - protocol: TCP
      port: 6379
```

### SSL/TLS Encryption

Use TLS for remote Redis connections:

```env
PAPERLESS_REDIS=rediss://redis-server:6380
```

Configure Redis with TLS certificates:
```conf
port 0
tls-port 6380
tls-cert-file /etc/redis/certs/redis.crt
tls-key-file /etc/redis/certs/redis.key
tls-ca-cert-file /etc/redis/certs/ca.crt
```

## Performance Tuning

### Connection Pool

Optimize Redis connection pool:

```env
PAPERLESS_REDIS=redis://localhost:6379?max_connections=50&socket_connect_timeout=5&socket_timeout=5
```

### Command Pipelining

Reduce network round-trips:

```python
pipe = redis_client.pipeline()
pipe.incr('counter')
pipe.lpush('queue', 'task')
pipe.execute()
```

### Cluster Configuration

For high availability, use Redis Cluster:

```env
PAPERLESS_REDIS=redis://redis-node-1:6379,redis-node-2:6379,redis-node-3:6379
```

:::info Cluster Notes
- Requires Redis Cluster mode enabled
- Automatic failover and resharding
- Horizontal scaling of reads and writes
- More complex to operate and monitor
:::

## Summary

| Topic | Configuration |
|-------|---------------|
| Basic Connection | `PAPERLESS_REDIS=redis://localhost:6379` |
| Multi-Tenant Isolation | Use `PAPERLESS_REDIS_PREFIX=tenant-name:` |
| Task Workers | `PAPERLESS_TASK_WORKERS=4` |
| Worker Timeout | `PAPERLESS_WORKER_TIMEOUT=1800` |
| Persistence | Enable RDB + AOF in Redis config |
| Monitoring | Use `celery inspect` and `redis-cli INFO` |
| Security | Enable authentication and TLS |
