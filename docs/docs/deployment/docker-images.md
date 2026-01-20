---
sidebar_position: 2
title: Docker Image Architecture
description: Separated Docker images for web, worker, and scheduler components
---

# Docker Image Architecture

Paperless-ngx is deployed as three separate Docker images, each running a single specialized service. This architecture enables independent scaling, improved resource efficiency, and better failure isolation compared to the monolithic approach.

## Overview

Instead of a single container running all services, the architecture now uses:

- **paless-web**: Granian webserver only (HTTP API and web UI)
- **paless-worker**: Celery worker only (document processing tasks)
- **paless-scheduler**: Celery beat only (scheduled background jobs)

Each image is built from the official `ghcr.io/paperless-ngx/paperless-ngx:latest` base image with service removal to disable unnecessary components.

## Architecture Comparison

### Before: Monolithic Container

```
┌─────────────────────────────────────┐
│     Paperless-ngx Container         │
├─────────────────────────────────────┤
│  • Granian webserver (port 8000)    │
│  • Celery worker                    │
│  • Celery beat scheduler            │
│  • Document consumer                │
│  • Flower monitoring UI             │
└─────────────────────────────────────┘
```

**Limitations:**
- All services compete for resources
- Container scaling affects all services
- Single failure affects entire application
- Difficult to allocate different resource profiles

### After: Separated Components

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   paless-web     │  │  paless-worker   │  │ paless-scheduler │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ Granian HTTP     │  │ Celery worker    │  │ Celery beat      │
│ API & Web UI     │  │ (parallelizable) │  │ (single instance)│
│ (port 8000)      │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
        ▲                      ▲                       ▲
        │                      └─────────┬─────────────┘
        │                                │
        └────────────────┬───────────────┘
                         ▼
                  Shared Resources
                  • Redis
                  • PostgreSQL
                  • MinIO Storage
```

**Advantages:**
- Independent scaling for each component
- Resource optimization per service type
- Better failure isolation
- Simplified monitoring and debugging
- Easier horizontal scaling for workers

## Image Specifications

### paless-web

**Purpose:** HTTP webserver and REST API

**Service Enabled:** `svc-webserver` (Granian)

**Port:** 8000

**Services Disabled:**
- `svc-worker` (Celery worker)
- `svc-scheduler` (Celery beat)
- `svc-consumer` (Document consumer)
- `svc-flower` (Monitoring UI)

**Dockerfile:**
```dockerfile
FROM localhost:5001/paless:latest

LABEL org.opencontainers.image.description="Paperless-ngx web component (Granian webserver only)"
LABEL org.opencontainers.image.title="paless-web"

# Remove worker, scheduler, consumer, and flower services
RUN rm -rf /etc/s6-overlay/s6-rc.d/svc-worker \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-scheduler \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-consumer \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-flower \
  && rm -f /etc/s6-overlay/s6-rc.d/svc-webserver/dependencies.d/svc-worker \
  && rm -f /etc/s6-overlay/s6-rc.d/svc-webserver/dependencies.d/svc-scheduler \
  && rm -f /etc/s6-overlay/s6-rc.d/svc-webserver/dependencies.d/svc-consumer \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-worker \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-scheduler \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-consumer \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-flower

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
  CMD curl -fs -S -L --max-time 2 http://localhost:8000
```

**Typical Resource Allocation:**
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

**Scaling:** Can be scaled to multiple replicas (e.g., behind a load balancer)

### paless-worker

**Purpose:** Celery worker for document processing tasks

**Service Enabled:** `svc-worker` (Celery)

**Services Disabled:**
- `svc-webserver` (Granian)
- `svc-scheduler` (Celery beat)
- `svc-consumer` (Document consumer)
- `svc-flower` (Monitoring UI)

**Dockerfile:**
```dockerfile
FROM localhost:5001/paless:latest

LABEL org.opencontainers.image.description="Paperless-ngx worker component (Celery worker only)"
LABEL org.opencontainers.image.title="paless-worker"

# Remove webserver, scheduler, consumer, and flower services
RUN rm -rf /etc/s6-overlay/s6-rc.d/svc-webserver \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-scheduler \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-consumer \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-flower \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-webserver \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-scheduler \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-consumer \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-flower

# No HEALTHCHECK for background worker
```

**Typical Resource Allocation:**
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

**Scaling:** Should scale based on document volume and task queue depth

**Concurrency Configuration:**
```yaml
env:
  - name: PAPERLESS_WORKER_THREADS
    value: "4"  # Adjust based on CPU cores available
```

### paless-scheduler

**Purpose:** Celery beat scheduler for periodic background jobs

**Service Enabled:** `svc-scheduler` (Celery beat)

**Services Disabled:**
- `svc-webserver` (Granian)
- `svc-worker` (Celery worker)
- `svc-consumer` (Document consumer)
- `svc-flower` (Monitoring UI)

**Dockerfile:**
```dockerfile
FROM localhost:5001/paless:latest

LABEL org.opencontainers.image.description="Paperless-ngx scheduler component (Celery beat only)"
LABEL org.opencontainers.image.title="paless-scheduler"

# Remove webserver, worker, consumer, and flower services
RUN rm -rf /etc/s6-overlay/s6-rc.d/svc-webserver \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-worker \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-consumer \
  && rm -rf /etc/s6-overlay/s6-rc.d/svc-flower \
  && rm -f /etc/s6-overlay/s6-rc.d/svc-scheduler/dependencies.d/svc-worker \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-webserver \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-worker \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-consumer \
  && rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-flower

# No HEALTHCHECK for background scheduler
```

**Typical Resource Allocation:**
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "250m"
```

**Scaling:** Must be single replica (scheduler must not run concurrently)

:::warning Single Replica
The scheduler must be deployed with exactly one replica. Multiple scheduler instances will cause duplicate task execution. Use pod disruption budgets and affinity rules to ensure high availability without duplication.
:::

## Service Removal Mechanism

All images use s6-overlay's service management system for clean service removal:

### s6-overlay Directory Structure

```
/etc/s6-overlay/s6-rc.d/
├── svc-webserver/          # Granian HTTP server
├── svc-worker/             # Celery worker
├── svc-scheduler/          # Celery beat
├── svc-consumer/           # Document consumer
├── svc-flower/             # Monitoring UI
└── user/
    └── contents.d/         # User bundle service list
```

### Service Removal Steps

Each image performs three removal operations:

1. **Remove Service Directory**
   ```bash
   rm -rf /etc/s6-overlay/s6-rc.d/svc-{service}
   ```
   Deletes the entire service definition directory

2. **Remove Service Dependencies** (if applicable)
   ```bash
   rm -f /etc/s6-overlay/s6-rc.d/svc-{dependent}/dependencies.d/svc-{service}
   ```
   Removes references to the disabled service from dependent services

3. **Remove from User Bundle**
   ```bash
   rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/svc-{service}
   ```
   Removes the service from the startup bundle

This clean removal ensures s6-overlay won't attempt to manage disabled services.

## Building Images

### Using Docker Build

Build all three images:

```bash
# Build web image
docker build -f Dockerfile.web -t paless-web:v2 .

# Build worker image
docker build -f Dockerfile.worker -t paless-worker:v2 .

# Build scheduler image
docker build -f Dockerfile.scheduler -t paless-scheduler:v2 .
```

### Using Build Script

The project includes an automated build script:

```bash
./scripts/build-split-containers.sh
```

This script:
- Detects all `Dockerfile.*` files
- Builds each image with proper naming
- Tags images with version information
- Pushes to configured registry

### Registry Configuration

Update registry in build commands or environment:

```bash
export REGISTRY=localhost:5000

docker build -f Dockerfile.web -t ${REGISTRY}/paless-web:v2 .
docker push ${REGISTRY}/paless-web:v2
```

## Kubernetes Deployment

### Separate Deployments

Deploy each image as a separate Kubernetes Deployment:

**web-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paperless-web
  labels:
    app: paperless
    component: web
spec:
  replicas: 2  # Scale web tier
  selector:
    matchLabels:
      app: paperless
      component: web
  template:
    metadata:
      labels:
        app: paperless
        component: web
    spec:
      containers:
      - name: web
        image: paless-web:v2
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: PAPERLESS_REDIS
          value: "redis://redis:6379"
        - name: PAPERLESS_DBHOST
          value: "postgres"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: paperless-data-pvc
      - name: media
        persistentVolumeClaim:
          claimName: paperless-media-pvc
```

**worker-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paperless-worker
  labels:
    app: paperless
    component: worker
spec:
  replicas: 2  # Scale workers based on volume
  selector:
    matchLabels:
      app: paperless
      component: worker
  template:
    metadata:
      labels:
        app: paperless
        component: worker
    spec:
      containers:
      - name: worker
        image: paless-worker:v2
        env:
        - name: PAPERLESS_REDIS
          value: "redis://redis:6379"
        - name: PAPERLESS_DBHOST
          value: "postgres"
        - name: PAPERLESS_WORKER_THREADS
          value: "4"
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: paperless-data-pvc
      - name: media
        persistentVolumeClaim:
          claimName: paperless-media-pvc
```

**scheduler-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paperless-scheduler
  labels:
    app: paperless
    component: scheduler
spec:
  replicas: 1  # MUST be 1 - single scheduler
  selector:
    matchLabels:
      app: paperless
      component: scheduler
  template:
    metadata:
      labels:
        app: paperless
        component: scheduler
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: component
                  operator: In
                  values:
                  - scheduler
              topologyKey: kubernetes.io/hostname
      containers:
      - name: scheduler
        image: paless-scheduler:v2
        env:
        - name: PAPERLESS_REDIS
          value: "redis://redis:6379"
        - name: PAPERLESS_DBHOST
          value: "postgres"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: paperless-data-pvc
      - name: media
        persistentVolumeClaim:
          claimName: paperless-media-pvc
```

### Service Exposure

Create a single Service for the web tier:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: paperless
  labels:
    app: paperless
spec:
  type: LoadBalancer
  selector:
    app: paperless
    component: web
  ports:
  - port: 8000
    targetPort: 8000
    name: http
```

## Scaling Strategy

### Web Tier Scaling

Scale based on HTTP request volume:

```bash
# Scale web deployment to 3 replicas
kubectl scale deployment paperless-web --replicas=3

# Or use Horizontal Pod Autoscaler (HPA)
kubectl autoscale deployment paperless-web --min=2 --max=5 --cpu-percent=70
```

### Worker Tier Scaling

Scale based on task queue depth:

```bash
# Monitor queue depth
kubectl exec -it deployment/paperless-web -- \
  python manage.py shell -c "from celery_app.tasks import app; print(app.control.inspect().active_queues())"

# Scale workers
kubectl scale deployment paperless-worker --replicas=4
```

:::info Auto-Scaling Workers
For automatic scaling based on queue depth, consider using:
- KEDA (Kubernetes Event Driven Autoscaling) with Redis queue monitoring
- Custom HPA with queue-depth metrics
:::

### Scheduler Tier Scaling

**Do not scale.** The scheduler must run exactly one instance:

```bash
# Verify single instance
kubectl get deployment paperless-scheduler
# Should show: replicas: 1/1
```

## Monitoring and Debugging

### View Logs by Component

```bash
# Web tier logs
kubectl logs -l app=paperless,component=web -f

# Worker tier logs
kubectl logs -l app=paperless,component=worker -f

# Scheduler logs
kubectl logs -l app=paperless,component=scheduler -f
```

### Check Component Status

```bash
# All components
kubectl get pods -l app=paperless

# Specific component
kubectl get pods -l app=paperless,component=web
```

### Access Pod Shell

```bash
# Web container
kubectl exec -it deployment/paperless-web -- /bin/bash

# Worker container
kubectl exec -it deployment/paperless-worker -- /bin/bash

# Scheduler container
kubectl exec -it deployment/paperless-scheduler -- /bin/bash
```

## Migration from Monolithic

If upgrading from a monolithic deployment:

1. **Back up data:**
   ```bash
   kubectl exec deployment/paperless -- tar czf /tmp/backup.tar.gz /usr/src/paperless/data
   ```

2. **Deploy new components** alongside old deployment

3. **Point web tier** to existing data/media volumes

4. **Verify workers** process queued tasks

5. **Monitor for 24-48 hours** before removing old deployment

6. **Remove old deployment:**
   ```bash
   kubectl delete deployment paperless
   ```

## Troubleshooting

### Worker Tasks Not Processing

**Check worker connection to queue:**
```bash
kubectl logs -l component=worker
# Look for: "Connected to redis://redis:6379"
```

**Verify Redis is accessible:**
```bash
kubectl exec deployment/paperless-worker -- \
  redis-cli -h redis ping
# Should respond: PONG
```

### Scheduler Not Running Jobs

**Verify single instance:**
```bash
kubectl get deployment paperless-scheduler
# Should show replicas: 1/1
```

**Check scheduler logs:**
```bash
kubectl logs -l component=scheduler

# Look for task scheduling messages
# Example: "[2026-01-20 12:00:00] Scheduler: Starting..."
```

### Web Service Not Responding

**Check pod health:**
```bash
kubectl describe pod -l component=web

# Look for: "Ready 1/1", "Running"
```

**Test directly:**
```bash
kubectl port-forward svc/paperless 8000:8000
curl http://localhost:8000
```

## Best Practices

1. **Always deploy scheduler with 1 replica**
2. **Use pod disruption budgets** for web and worker tiers
3. **Configure resource requests** based on actual workload
4. **Monitor queue depth** to drive worker scaling decisions
5. **Use persistent volumes** for shared storage across all components
6. **Implement health checks** for all components
7. **Log centralization** for debugging across components
8. **Gradual rollout** when updating images

## References

- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [s6-overlay Documentation](https://skarnet.org/software/s6-overlay/)
- [Paperless-ngx Worker Configuration](https://docs.paperless-ngx.com/)
