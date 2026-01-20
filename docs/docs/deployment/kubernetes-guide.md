---
sidebar_position: 3
title: Kubernetes Deployment Guide
description: Deploy Paperless NGX on Kubernetes with persistent volume management
---

# Kubernetes Deployment Guide

This guide covers deploying Paperless NGX on Kubernetes with proper persistent volume (PV) and persistent volume claim (PVC) configuration for data persistence.

## Overview

Paperless NGX uses a separated component architecture with three independent deployments:
- **Web Component** (`paless-web`): Handles HTTP requests and document uploads
- **Worker Component** (`paless-worker`): Processes documents asynchronously (OCR, PDF generation)
- **Scheduler Component** (`paless-scheduler`): Manages periodic tasks and maintenance operations

All components share persistent storage through:
- **Data volume** (`/usr/src/paperless/data`): Stores database and application state
- **Media volume** (`/usr/src/paperless/media`): Stores scanned document files and processed media

This separation provides better scalability, resource isolation, and independent restart capabilities while the deployment uses persistent volume claims to ensure data survives pod restarts and enables proper backup and recovery strategies.

## Volume Architecture

### Volume Types

| Volume | Path | Size | Type | Purpose |
|--------|------|------|------|---------|
| data | `/usr/src/paperless/data` | 1Gi | PVC | Database and application state |
| media | `/usr/src/paperless/media` | 2Gi | PVC | Document storage and media files |
| rclone-config | `/config/rclone` | - | ConfigMap | rclone configuration |

## Separated Component Architecture

Paperless NGX is deployed as three independent components that work together through shared storage and a common message queue (Redis via Celery):

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Paperless NGX Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                  External Access                        │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │  Ingress (paless-web)                           │   │  │
│  │  │  - Host: paless.local                           │   │  │
│  │  │  - Path: /                                      │   │  │
│  │  │  - Routes to: paless-web Service (port 8000)   │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               Web Component (paless-web)               │  │
│  │  ┌────────────────────────────────────────────────┐    │  │
│  │  │ Deployment: paless-web                        │    │  │
│  │  │ Replicas: 3 (scalable via HPA)               │    │  │
│  │  │ CPU: 250m request, 1 limit                   │    │  │
│  │  │ Memory: 512Mi request, 2Gi limit             │    │  │
│  │  │                                              │    │  │
│  │  │ Responsibilities:                            │    │  │
│  │  │ - HTTP API server (port 8000)               │    │  │
│  │  │ - Document upload handling                  │    │  │
│  │  │ - Web UI serving                            │    │  │
│  │  │ - Real-time status updates                  │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  │                                                         │  │
│  │  HPA: Scale 1-10 replicas based on CPU/memory        │  │
│  └─────────────────────────────────────────────────────────┘  │
│           │ Celery Events                                     │
│           ▼ (via Redis)                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │           Worker Component (paless-worker)              │  │
│  │  ┌────────────────────────────────────────────────┐    │  │
│  │  │ Deployment: paless-worker                      │    │  │
│  │  │ Replicas: 2 (scalable via HPA)                │    │  │
│  │  │ CPU: 500m request, 2 limit                    │    │  │
│  │  │ Memory: 1Gi request, 4Gi limit                │    │  │
│  │  │                                               │    │  │
│  │  │ Responsibilities:                             │    │  │
│  │  │ - Asynchronous document processing           │    │  │
│  │  │ - OCR and text extraction                    │    │  │
│  │  │ - PDF generation and manipulation            │    │  │
│  │  │ - File format conversions                    │    │  │
│  │  │ - Heavy computational workloads              │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  │                                                         │  │
│  │  HPA: Scale 1-4 replicas based on CPU/memory         │  │
│  └─────────────────────────────────────────────────────────┘  │
│           │ Celery Beat Schedules                            │
│           ▼ (via Redis)                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         Scheduler Component (paless-scheduler)           │  │
│  │  ┌────────────────────────────────────────────────┐    │  │
│  │  │ Deployment: paless-scheduler                   │    │  │
│  │  │ Replicas: 1 (single instance, no HPA)          │    │  │
│  │  │ CPU: 100m request, 500m limit                  │    │  │
│  │  │ Memory: 256Mi request, 1Gi limit               │    │  │
│  │  │                                                │    │  │
│  │  │ Responsibilities:                              │    │  │
│  │  │ - Celery Beat scheduler                       │    │  │
│  │  │ - Periodic task execution                     │    │  │
│  │  │ - Report generation scheduling                │    │  │
│  │  │ - Maintenance operations                      │    │  │
│  │  │ - Index cleanup and optimization              │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                      │                                        │
│                      ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Shared Resources                           │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │ PVC: paperless-data-pvc (1Gi)                   │   │  │
│  │  │ Mount: /usr/src/paperless/data                  │   │  │
│  │  │ Purpose: SQLite database, application state    │   │  │
│  │  │                                                 │   │  │
│  │  │ PVC: paperless-media-pvc (2Gi)                 │   │  │
│  │  │ Mount: /usr/src/paperless/media (via rclone)   │   │  │
│  │  │ Purpose: Document storage, media files         │   │  │
│  │  │ Backend: MinIO S3 storage                       │   │  │
│  │  │                                                 │   │  │
│  │  │ ConfigMap: paperless-config                     │   │  │
│  │  │ ConfigMap: rclone-config                        │   │  │
│  │  │ Secret: paless-secret (credentials)             │   │  │
│  │  │ Service: redis (broker for Celery)              │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### Web Component (paless-web)

The web component is the user-facing interface:

- **HTTP Server**: Runs the Django application server on port 8000
- **API Endpoints**: Handles all REST API calls for document management
- **File Upload**: Accepts document uploads from users
- **Web UI**: Serves the web interface for users to browse documents
- **Authentication**: Manages user sessions and authentication

**Scaling:**
- Runs with 3 replicas by default (configurable)
- Automatically scales 1-10 replicas based on CPU and memory usage via HPA
- Stateless design allows arbitrary scaling without data loss
- Each replica is independent and can be restarted without affecting others

**Resource Allocation:**
- Request: 250m CPU, 512Mi memory (guaranteed minimum)
- Limit: 1 CPU, 2Gi memory (maximum allowed)
- Adjusted for typical web workloads with moderate concurrency

#### Worker Component (paless-worker)

The worker component processes documents:

- **Document Processing**: Executes Celery worker tasks
- **OCR Operations**: Runs Tesseract for optical character recognition
- **PDF Generation**: Creates optimized PDF versions
- **Format Conversion**: Converts documents between formats
- **Thumbnail Generation**: Creates document previews
- **Asynchronous Processing**: Handles long-running operations without blocking the web interface

**Scaling:**
- Runs with 2 replicas by default (configurable)
- Automatically scales 1-4 replicas based on CPU and memory usage via HPA
- Each replica is a full Celery worker processing tasks from the queue
- Can handle multiple concurrent tasks per replica

**Resource Allocation:**
- Request: 500m CPU, 1Gi memory (guaranteed minimum)
- Limit: 2 CPU, 4Gi memory (maximum allowed)
- Higher allocation due to CPU-intensive OCR and document processing

#### Scheduler Component (paless-scheduler)

The scheduler component manages periodic tasks:

- **Celery Beat Scheduler**: Runs the task scheduler for periodic jobs
- **Scheduled Tasks**: Executes tasks on a defined schedule
- **Report Generation**: Creates periodic reports
- **Maintenance**: Performs database optimization and cleanup
- **Index Management**: Updates search indexes
- **Single Instance**: Only one scheduler should run to avoid duplicate tasks

**Scaling:**
- Fixed at 1 replica (never scaled)
- Critical to have exactly one instance to avoid task duplication
- Lightweight component, minimal resource usage

**Resource Allocation:**
- Request: 100m CPU, 256Mi memory (guaranteed minimum)
- Limit: 500m CPU, 1Gi memory (maximum allowed)
- Minimal allocation due to I/O-bound scheduling operations

### Inter-component Communication

Components communicate through:

1. **Shared Database (SQLite)**
   - All components access the same SQLite database via the data PVC
   - Database file locked by first accessor, preventing conflicts
   - Application-level transaction handling ensures consistency

2. **Celery Task Queue (Redis)**
   - Web component submits tasks to the Redis queue
   - Worker and scheduler components read from the queue
   - Redis manages task routing and deduplication
   - Celery Beat scheduler uses Redis for periodic task scheduling

3. **Shared Media Storage (MinIO + rclone)**
   - All components access media files through rclone mount
   - rclone FUSE mount provides local filesystem interface to S3 storage
   - Bidirectional mount propagation allows all containers to access the mount
   - MinIO provides durable, multi-replica S3 storage

### Component Startup Sequence

For a clean deployment, components should start in this order:

1. **MinIO** - Must be ready first (storage backend)
2. **Redis** - Must be ready second (message broker)
3. **Scheduler** - Should start before workers
4. **Workers** - Can start in any order
5. **Web** - Start last (user-facing, depends on all others)

Kubernetes doesn't enforce this order automatically. Use Kustomize `dependsOn` or Pod Scheduling Gates if strict ordering is needed.

## Horizontal Pod Autoscaling (HPA)

The web and worker components automatically scale based on resource utilization:

### Web Component HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-hpa
  labels:
    app: paless
    component: web
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: paless-web
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

**Scaling Rules:**
- **Scale Up**: Doubles replicas every 30 seconds when CPU > 70% or memory > 80%
- **Scale Down**: Reduces by 50% every 60 seconds after 5 minutes of stable resource usage
- **Min/Max**: Scales between 1 and 10 replicas

**When to Scale:**
- High user traffic increases CPU and memory usage → more replicas
- Idle periods reduce resource usage → fewer replicas
- Each replica handles ~100-200 concurrent requests (depends on document size)

### Worker Component HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
  labels:
    app: paless
    component: worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: paless-worker
  minReplicas: 1
  maxReplicas: 4
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 85
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

**Scaling Rules:**
- **Scale Up**: Doubles replicas every 30 seconds when CPU > 75% or memory > 85%
- **Scale Down**: Reduces by 50% every 60 seconds after 5 minutes of stable resource usage
- **Min/Max**: Scales between 1 and 4 replicas

**When to Scale:**
- Large document batch uploads trigger OCR processing → more workers
- CPU-intensive operations (OCR, PDF generation) increase resource usage
- Idle periods reduce resource usage → scale down
- Each worker handles 1-3 concurrent document processing tasks

### Scheduler Component

The scheduler component is **never scaled** (replicas: 1). Celery Beat requires exactly one scheduler instance to prevent duplicate scheduled tasks.

## Networking and Service Discovery

### Web Service

The web component exposes an internal ClusterIP service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: paless-web
  labels:
    app: paless
    component: web
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
      protocol: TCP
      name: http
  selector:
    app: paless
    component: web
```

**Service Details:**
- **Type**: ClusterIP (internal only, not accessible from outside)
- **Port**: 8000 (HTTP)
- **Selector**: Routes to all `paless-web` pods
- **Use**: Referenced by Ingress for external access

**Service Discovery:**
- DNS name: `paless-web.default.svc.cluster.local` (full FQDN)
- DNS name: `paless-web.default` (namespace-qualified)
- DNS name: `paless-web` (within same namespace)

### Ingress for External Access

The Ingress resource provides external HTTP access to the web component:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: paless-web
  labels:
    app: paless
    component: web
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  ingressClassName: nginx
  rules:
    - host: paless.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: paless-web
                port:
                  number: 8000
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: paless-web
                port:
                  number: 8000
```

**Configuration Details:**

| Setting | Value | Purpose |
|---------|-------|---------|
| IngressClass | `nginx` | Uses NGINX ingress controller |
| Host Rule | `paless.local` | Domain-based routing |
| Path | `/` | Route all requests to web service |
| PathType | `Prefix` | Match all paths starting with `/` |
| rewrite-target | `/` | Rewrite URL path before forwarding |
| proxy-body-size | `100m` | Allow large file uploads (up to 100MB) |

**Access Methods:**

1. **By Hostname** (requires DNS configuration)
   ```bash
   curl http://paless.local
   ```

2. **By Ingress IP** (direct IP access)
   ```bash
   # Get Ingress IP
   kubectl get ingress paless-web

   # Add to /etc/hosts
   echo "10.0.0.5 paless.local" >> /etc/hosts

   # Access
   curl http://paless.local
   ```

3. **Via Port Forwarding** (development)
   ```bash
   kubectl port-forward service/paless-web 8000:8000
   curl http://localhost:8000
   ```

**Ingress Rules:**

The ingress includes two rule blocks:

1. **Host-based rule** (`paless.local`)
   - Matches requests to the specific hostname
   - Used for DNS-based access

2. **Default rule** (no host specified)
   - Matches all requests (fallback)
   - Used for IP-based or unknown hostname access

Both rules route to the same service, allowing flexible access methods.

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
- Mounts MinIO bucket as a filesystem using rclone
- Uses FUSE to present S3 storage as a local directory
- Handles authentication via AWS credentials from secrets
- Enables seamless file access from Paperless container
- Configured with VFS cache for performance
- Uses bidirectional mount propagation for secure volume sharing

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

In development environments, access MinIO console via NodePort. The NodePort service is defined in the dev overlay and exposes the MinIO console on port 30090:

**File**: `k8s/overlays/dev/minio-console-nodeport.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minio-console-nodeport
  labels:
    app: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/component: storage
    app.kubernetes.io/part-of: paless
spec:
  type: NodePort
  ports:
  - port: 9001
    targetPort: 9001
    nodePort: 30090
    protocol: TCP
    name: console
  selector:
    app: minio
```

#### Accessing the Console

**URL**: `http://localhost:30090`

**Credentials**: Use the MinIO root credentials from the secret:
- **Username**: `MINIO_ROOT_USER` from `paless-secret`
- **Password**: `MINIO_ROOT_PASSWORD` from `paless-secret`

**For K3s/Local Development**:
```bash
# Get the node IP (for remote access)
kubectl get nodes -o wide

# Then access: http://<node-ip>:30090
```

:::info NodePort vs ClusterIP
The MinIO service includes two ports:
- **ClusterIP (9000, 9001)**: Internal cluster access for Paperless and initialization jobs
- **NodePort (30090)**: External access for development console UI

Both ports are available simultaneously, allowing pod-to-pod communication and developer console access.
:::

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

### rclone Sidecar Configuration

The rclone sidecar container handles mounting the MinIO S3 bucket as a filesystem that Paperless can access directly. This eliminates the need for Paperless to implement S3 API calls for file operations.

#### rclone Configuration

Create a ConfigMap with rclone's S3 remote configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rclone-config
  labels:
    app: paperless
    app.kubernetes.io/name: paperless
    app.kubernetes.io/component: storage
data:
  rclone.conf: |
    [minio]
    type = s3
    provider = Minio
    endpoint = http://minio:9000
    env_auth = true
    acl = private
```

**Configuration Options:**
- `type = s3`: Specifies S3-compatible storage backend
- `provider = Minio`: Sets provider to MinIO for optimized behavior
- `endpoint = http://minio:9000`: Internal cluster endpoint to MinIO S3 API
- `env_auth = true`: Uses `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables for authentication
- `acl = private`: Sets default ACL for uploaded objects

#### Sidecar Container Definition

The rclone sidecar is deployed as a second container in the Paperless pod:

```yaml
containers:
  - name: rclone
    image: rclone/rclone:latest
    securityContext:
      privileged: true
    command:
      - /bin/sh
      - -c
      - |
        rclone mount minio:paperless-media /mnt/media --vfs-cache-mode full --allow-other --daemon
        sleep infinity
    env:
      - name: AWS_ACCESS_KEY_ID
        valueFrom:
          secretKeyRef:
            name: paless-secret
            key: minio-root-user
      - name: AWS_SECRET_ACCESS_KEY
        valueFrom:
          secretKeyRef:
            name: paless-secret
            key: minio-root-password
    volumeMounts:
      - name: rclone-config
        mountPath: /config/rclone
      - name: media
        mountPath: /mnt/media
        mountPropagation: Bidirectional
    resources:
      limits:
        cpu: "500m"
        memory: "512Mi"
      requests:
        cpu: "100m"
        memory: "128Mi"
```

**Sidecar Configuration Details:**

| Setting | Value | Purpose |
|---------|-------|---------|
| Image | `rclone/rclone:latest` | Official rclone container image |
| `securityContext.privileged` | `true` | Required for FUSE mount operations |
| Mount command | `rclone mount minio:paperless-media /mnt/media` | Mounts `paperless-media` bucket at `/mnt/media` |
| `--vfs-cache-mode full` | Full caching | Improves performance, especially for reads |
| `--allow-other` | Enabled | Allows other containers to access the mount |
| `--daemon` | Enabled | Runs rclone in background daemon mode |

#### Mount Propagation

The rclone sidecar uses **bidirectional mount propagation** to safely share the mounted filesystem:

```yaml
volumeMounts:
  - name: media
    mountPath: /mnt/media
    mountPropagation: Bidirectional
```

**Why Bidirectional Propagation?**
- Rclone mounts the S3 bucket at `/mnt/media` inside the sidecar container
- `Bidirectional` propagation allows the Paperless container to see this mount
- This enables transparent file access as if the bucket were a local filesystem

**Mount Propagation Modes:**
- `None`: No propagation between containers (default)
- `HostToContainer`: Host mounts visible in container
- `Bidirectional`: Mounts propagate both directions (required for sidecars)

#### Volume Configuration

The media volume is configured as an `emptyDir` shared between containers:

```yaml
volumes:
  - name: media
    emptyDir: {}
  - name: rclone-config
    configMap:
      name: rclone-config
```

**Why emptyDir for media?**
- Acts as a mount point for the rclone FUSE mount
- Persistent media is stored in MinIO (backend), not local storage
- Each pod restart remounts the bucket without data loss
- Simplifies cleanup when pods terminate

#### Authentication Flow

The rclone sidecar authenticates with MinIO using AWS credentials:

```
1. Pod starts with rclone and paperless containers
2. rclone reads AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from secrets
3. rclone.conf configures MinIO endpoint (http://minio:9000)
4. rclone authenticates to MinIO using provided credentials
5. rclone mounts paperless-media bucket at /mnt/media with FUSE
6. Paperless container accesses files through mounted filesystem
```

#### VFS Cache Configuration

The `--vfs-cache-mode full` option enables comprehensive caching:

```
Read Flow:
  Paperless reads /mnt/media/document.pdf
  → rclone checks local cache
  → If miss: downloads from MinIO S3
  → Caches locally for future access
  → Returns to Paperless

Write Flow:
  Paperless writes to /mnt/media/output.pdf
  → Written to cache first
  → Cached file uploaded to MinIO asynchronously
  → Returns success to Paperless
```

This caching strategy improves performance while maintaining data consistency.

:::info Resource Allocation
The rclone sidecar has modest resource requirements:
- **Requests**: 100m CPU, 128Mi memory (minimum guaranteed)
- **Limits**: 500m CPU, 512Mi memory (maximum allowed)

Adjust limits based on document volume and concurrent access patterns.
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

### rclone Sidecar Issues

#### rclone Fails to Mount

**Symptoms:** Pod stuck in `NotReady` state, rclone container crashes repeatedly

**Check rclone logs:**
```bash
kubectl logs pod/paperless -c rclone

# Typical errors:
# "FUSE mount failed: permission denied" → pod needs privileged: true
# "Unable to connect to minio:9000" → MinIO not ready, check MinIO pod
# "Invalid credentials" → Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
```

**Diagnosis steps:**
1. Verify rclone container has `privileged: true` in securityContext
2. Check MinIO pod is running: `kubectl get pods -l app=minio`
3. Verify MinIO service endpoint: `kubectl get svc minio`
4. Confirm bucket exists: `kubectl logs job/minio-init`
5. Test connectivity from Paperless pod: `kubectl exec pod/paperless -c rclone -- ping minio`

**Resolution:**
```bash
# Recreate pod to force rclone remount
kubectl delete pod/paperless

# Monitor startup logs
kubectl logs -f pod/paperless -c rclone
```

#### rclone Mount Point Empty or Inaccessible

**Symptoms:** Files appear to be missing, permission denied when accessing /mnt/media

**Diagnosis:**
```bash
# Check mount status inside paperless container
kubectl exec pod/paperless -c paperless -- mount | grep /mnt/media

# Should output something like:
# minio:paperless-media on /mnt/media type fuse.rclone (rw,nosuid,nodev,relatime,...)

# If not present, rclone mount failed
# If present, check file visibility
kubectl exec pod/paperless -c paperless -- ls -la /mnt/media/
```

**Common Issues:**
- Mount propagation not set to `Bidirectional` → update deployment
- FUSE permissions issue → ensure `--allow-other` flag is present
- rclone cache corrupted → delete pod to clear cache

#### Slow File Operations

**Symptoms:** File reads/writes are unusually slow, timeouts

**Optimization:**
```yaml
# In rclone mount command, adjust VFS cache settings:
rclone mount minio:paperless-media /mnt/media \
  --vfs-cache-mode full \
  --vfs-cache-max-size 2G \      # Increase cache size
  --vfs-cache-poll-interval 5s \  # Adjust poll frequency
  --allow-other \
  --daemon
```

**Tuning parameters:**
- `--vfs-cache-max-size`: Increase if documents are large (adjust container memory limit)
- `--vfs-cache-poll-interval`: Lower for more responsive updates, higher for less overhead
- `--transfers N`: Increase parallel transfers (default 4)

#### rclone Configuration Not Loading

**Symptoms:** "Config file not found" errors, authentication failures

**Check ConfigMap:**
```bash
# Verify ConfigMap exists
kubectl get cm rclone-config

# View its contents
kubectl describe cm rclone-config

# Expected output should show rclone.conf with [minio] section
```

**Verify mount in pod:**
```bash
# Check if /config/rclone/rclone.conf is readable
kubectl exec pod/paperless -c rclone -- cat /config/rclone/rclone.conf

# Should output the rclone configuration with MinIO settings
```

**Redeploy ConfigMap:**
```bash
# Update ConfigMap
kubectl apply -f rclone-configmap.yaml

# Recreate pod to pick up new config
kubectl delete pod/paperless
```

### Separated Component Issues

#### Components Not Starting

**Symptoms:** One or more component deployments showing 0/N replicas, pods pending or crashing

**Diagnosis:**
```bash
# Check deployment status
kubectl get deployments -l app=paless

# Check for pod creation issues
kubectl describe deployment paless-web
kubectl describe deployment paless-worker
kubectl describe deployment paless-scheduler

# Check recent pod events
kubectl get events --sort-by='.lastTimestamp'

# Check component-specific pod logs
kubectl logs -l app=paless,component=web --all-containers=true --tail=50
kubectl logs -l app=paless,component=worker --all-containers=true --tail=50
kubectl logs -l app=paless,component=scheduler --all-containers=true --tail=50
```

**Common Issues:**

1. **Missing Dependencies (MinIO or Redis not ready)**
   - Web, worker, and scheduler all depend on MinIO and Redis
   - Solution: Verify MinIO and Redis are running before components
   ```bash
   kubectl get pods -l app=minio,app=redis
   ```

2. **Insufficient Resources**
   - Not enough CPU/memory for requested replicas
   - Solution: Check node resource availability
   ```bash
   kubectl describe nodes
   kubectl top nodes
   ```

3. **PVC Not Bound**
   - Components can't mount data PVC
   - Solution: Verify PVCs are bound
   ```bash
   kubectl get pvc
   ```

4. **Image Pull Failures**
   - Container image not found in registry
   - Solution: Check image name and registry
   ```bash
   kubectl describe pod -l app=paless,component=web | grep -A 5 "Image:"
   ```

#### Component-to-Component Communication Issues

**Symptoms:** Web component can't connect to worker queue, scheduler tasks not executing

**Diagnosis:**
```bash
# Verify Redis (message broker) is running
kubectl get pods -l app=redis

# Test connectivity from components
kubectl exec -it deployment/paless-web -- redis-cli -h redis ping

# Check Celery configuration in all components
kubectl exec -it deployment/paless-web -- printenv | grep CELERY
```

**Resolution:**
- Ensure Redis service is running and accessible
- Verify all components can reach Redis by DNS name (`redis.default.svc.cluster.local`)
- Check network policies don't block pod-to-pod communication

#### Worker Not Processing Documents

**Symptoms:** Documents uploaded but no processing occurs, worker pod not doing work

**Diagnosis:**
```bash
# Check worker pod is running
kubectl get pods -l app=paless,component=worker

# Monitor worker logs for activity
kubectl logs -f -l app=paless,component=worker -c paless-worker

# Check if tasks are queued in Redis
kubectl exec -it deployment/paless-web -- python manage.py shell
# In Django shell:
# from django_celery_beat.models import PeriodicTask
# PeriodicTask.objects.all()
```

**Common Causes:**
1. **Worker not connected to Redis** → Check Redis configuration
2. **No worker replicas running** → Check worker deployment status
3. **Tasks failing** → Check worker logs for error messages
4. **Resource limits** → Worker might be getting OOMKilled or CPU throttled

#### Scheduler Not Executing Periodic Tasks

**Symptoms:** Scheduled reports not generated, maintenance tasks not running

**Diagnosis:**
```bash
# Verify scheduler pod is running (must be exactly 1)
kubectl get pods -l app=paless,component=scheduler

# Check Celery Beat logs
kubectl logs -f -l app=paless,component=scheduler -c paless-scheduler

# Verify scheduler is working
kubectl exec -it deployment/paless-scheduler -c paless-scheduler -- \
  celery -A config inspect active_queues
```

**Issues:**
1. **Multiple scheduler replicas** → Causes duplicate tasks
   - Solution: Ensure scheduler deployment has exactly 1 replica
   ```bash
   kubectl scale deployment paless-scheduler --replicas=1
   ```

2. **Scheduler not connected to Redis** → No tasks execute
   - Solution: Verify Redis connectivity

3. **Tasks not defined** → Check Django settings and Celery Beat configuration

#### HPA Not Scaling Components

**Symptoms:** HPA created but replicas not increasing under load, stuck at minimum replicas

**Diagnosis:**
```bash
# Check HPA status
kubectl get hpa

# Check HPA detailed info
kubectl describe hpa web-hpa
kubectl describe hpa worker-hpa

# Check if metrics are being collected
kubectl top pods -l app=paless

# Check HPA events
kubectl get events --field-selector involvedObject.kind=HorizontalPodAutoscaler
```

**Common Issues:**

1. **Metrics Server Not Running**
   - HPA requires metrics server to collect CPU/memory data
   ```bash
   kubectl get deployment -n kube-system metrics-server
   ```
   - Solution: Install metrics server if missing

2. **No Resource Requests Defined**
   - HPA can't calculate utilization without requests
   - Solution: Verify deployments have `resources.requests`

3. **Requests Too High**
   - Utilization calculation: `used / requested`
   - High requests → low utilization percentage → no scaling
   - Solution: Adjust resource requests to realistic values

4. **CPU/Memory Target Too High**
   - Default thresholds (70% CPU, 80% memory) might be too high
   - Solution: Lower thresholds in HPA spec for more responsive scaling

#### Service and Ingress Not Accessible

**Symptoms:** Web UI not reachable, unable to connect to service

**Diagnosis:**
```bash
# Verify service is created
kubectl get service paless-web

# Verify service endpoints (should match pod IPs)
kubectl get endpoints paless-web

# Test service connectivity from within cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  wget -O- http://paless-web:8000

# Check ingress status
kubectl get ingress paless-web

# Check ingress controller is running
kubectl get pods -n ingress-nginx
```

**Issues:**
1. **Ingress IP not assigned** → Ingress controller not running
2. **No endpoints** → Web pods not running or have wrong labels
3. **Service unreachable** → Network policy blocking traffic

**Solutions:**
```bash
# Recreate ingress if stuck
kubectl delete ingress paless-web
kubectl apply -f web-ingress.yaml

# Force web pod recreation
kubectl rollout restart deployment paless-web

# Check network policies
kubectl get networkpolicies
```

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

## Complete Deployment Checklist

Use this checklist when deploying Paperless NGX with MinIO and rclone on Kubernetes:

### Pre-Deployment

- [ ] Kubernetes cluster is running and accessible via `kubectl`
- [ ] Sufficient storage capacity available (minimum 23Gi)
- [ ] MinIO root user credentials prepared
- [ ] Docker registry configured (if using custom image)
- [ ] Network policies allow pod-to-pod communication

### Deployment Order

**Step 1: Create Namespace**
```bash
kubectl apply -f namespace.yaml
```

**Step 2: Create Secrets**
```bash
kubectl apply -f paless-secret.yaml
# Verify: kubectl get secret paless-secret
```

**Step 3: Create Persistent Volumes (Development Only)**
```bash
kubectl apply -f pv-manual.yaml
# Verify: kubectl get pv
```

**Step 4: Create Persistent Volume Claims**
```bash
kubectl apply -f pvc.yaml
# Verify: kubectl get pvc
# Wait for all PVCs to be Bound
```

**Step 5: Create rclone Configuration**
```bash
kubectl apply -f rclone-configmap.yaml
# Verify: kubectl describe cm rclone-config
```

**Step 6: Deploy MinIO**
```bash
# Deploy StatefulSet
kubectl apply -f minio-statefulset.yaml

# Deploy Service (ClusterIP for internal access)
kubectl apply -f minio-service.yaml

# Deploy NodePort service for console access (development only)
kubectl apply -f overlays/dev/minio-console-nodeport.yaml

# Wait for MinIO pod to be Ready
kubectl wait --for=condition=ready pod -l app=minio --timeout=5m
```

**Step 7: Initialize MinIO Bucket**
```bash
kubectl apply -f minio-init-job.yaml

# Wait for job completion
kubectl wait --for=condition=complete job/minio-init --timeout=5m

# Verify bucket creation
kubectl logs job/minio-init
```

**Step 8: Deploy Separated Components**

The separated component architecture includes three independent deployments (web, worker, scheduler) plus networking resources:

```bash
# Deploy web component and networking
kubectl apply -f paless-web-deployment.yaml
kubectl apply -f web-service.yaml
kubectl apply -f web-ingress.yaml
kubectl apply -f web-hpa.yaml

# Wait for web component to be Ready
kubectl wait --for=condition=ready pod -l app=paless,component=web --timeout=5m

# Deploy worker component and autoscaler
kubectl apply -f paless-worker-deployment.yaml
kubectl apply -f worker-hpa.yaml

# Wait for worker component to be Ready
kubectl wait --for=condition=ready pod -l app=paless,component=worker --timeout=5m

# Deploy scheduler component
kubectl apply -f paless-scheduler-deployment.yaml

# Wait for scheduler component to be Ready
kubectl wait --for=condition=ready pod -l app=paless,component=scheduler --timeout=5m
```

**Component Verification:**

```bash
# Check all Paperless components are running
kubectl get pods -l app=paless -L component

# Expected output:
# NAME                                   READY   STATUS    RESTARTS   COMPONENT
# paless-web-xxxxxxxx-xxxxx             2/2     Running   0          web
# paless-web-xxxxxxxx-xxxxx             2/2     Running   0          web
# paless-web-xxxxxxxx-xxxxx             2/2     Running   0          web
# paless-worker-xxxxxxxx-xxxxx          2/2     Running   0          worker
# paless-worker-xxxxxxxx-xxxxx          2/2     Running   0          worker
# paless-scheduler-xxxxxxxx-xxxxx       2/2     Running   0          scheduler

# Check HPA status
kubectl get hpa

# Expected output:
# NAME        REFERENCE                    TARGETS          MINPODS  MAXPODS  REPLICAS
# web-hpa     Deployment/paless-web        23%/70%, 45%/80% 1        10       3
# worker-hpa  Deployment/paless-worker     45%/75%, 60%/85% 1        4        2

# Check services and ingress
kubectl get service,ingress

# Expected output:
# NAME                  TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)
# service/paless-web    ClusterIP   10.43.100.200   <none>        8000/TCP
#
# NAME                     CLASS   HOSTS        ADDRESS       PORTS
# ingress/paless-web       nginx   paless.local 10.0.0.1      80
```

**Understanding the Output:**
- **Web pods**: 3 replicas, each with 2 containers (paless-web + rclone)
- **Worker pods**: 2 replicas, each with 2 containers (paless-worker + rclone)
- **Scheduler pod**: 1 replica with 2 containers (paless-scheduler + rclone)
- **Total containers**: 12 containers running (3 × 2 web + 2 × 2 workers + 1 × 2 scheduler)

### Post-Deployment Verification

Verify the separated components are working correctly:

**Component Status:**
- [ ] Web component: 3 pods in `Running` state, each with 2 containers (web + rclone)
- [ ] Worker component: 2 pods in `Running` state, each with 2 containers (worker + rclone)
- [ ] Scheduler component: 1 pod in `Running` state with 2 containers (scheduler + rclone)
- [ ] HPA controllers created for web and worker components
- [ ] All pods show `READY` status (2/2 containers running)

**Networking:**
- [ ] Web service created (ClusterIP: paless-web)
- [ ] Ingress resource created and assigned IP address
- [ ] Ingress points to web service on port 8000
- [ ] Web UI accessible via ingress hostname or IP

**Storage and rclone:**
- [ ] All components can access `/usr/src/paperless/data` (data PVC)
- [ ] All components can access `/usr/src/paperless/media` (rclone mount)
- [ ] rclone containers show successful mounts in logs
- [ ] MinIO bucket accessible from all components

**Functionality:**
- [ ] Web UI loads and responds to HTTP requests
- [ ] Can upload documents through web interface
- [ ] Worker processes documents (check logs for processing activity)
- [ ] Scheduler executes periodic tasks (check beat logs)

### Verification Commands

**Component Status:**

```bash
# List all Paperless components with their component labels
kubectl get pods -l app=paless -L component,ready

# Check component-specific pod status
kubectl get pods -l app=paless,component=web
kubectl get pods -l app=paless,component=worker
kubectl get pods -l app=paless,component=scheduler

# Watch components start (shows real-time status)
kubectl get pods -l app=paless --watch

# Detailed pod information
kubectl describe pod -l app=paless,component=web
kubectl describe pod -l app=paless,component=worker
kubectl describe pod -l app=paless,component=scheduler
```

**Networking:**

```bash
# Verify service creation
kubectl get service paless-web

# Verify ingress creation and IP assignment
kubectl get ingress paless-web
kubectl describe ingress paless-web

# Test internal service connectivity (from within cluster)
kubectl run -it --rm debug --image=busybox --restart=Never -- wget -O- http://paless-web:8000

# Get the Ingress IP for external access
kubectl get ingress paless-web -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Test external access (if Ingress IP is assigned)
curl http://<ingress-ip>
```

**Component Logs:**

```bash
# Web component logs (all replicas)
kubectl logs -l app=paless,component=web --all-containers=true

# Monitor web logs in real-time
kubectl logs -f -l app=paless,component=web -c paless-web

# Worker component logs (all replicas)
kubectl logs -l app=paless,component=worker --all-containers=true

# Monitor worker processing activity
kubectl logs -f -l app=paless,component=worker -c paless-worker

# Scheduler component logs
kubectl logs -f -l app=paless,component=scheduler -c paless-scheduler
```

**rclone Mount Verification (All Components):**

```bash
# Check rclone mount in web component
kubectl exec -it deployment/paless-web -c paless-web -- mount | grep /mnt/media

# Check rclone mount in worker component
kubectl exec -it deployment/paless-worker -c paless-worker -- mount | grep /mnt/media

# Check rclone mount in scheduler component
kubectl exec -it deployment/paless-scheduler -c paless-scheduler -- mount | grep /mnt/media

# Test file access from web component
kubectl exec -it deployment/paless-web -c paless-web -- ls -la /usr/src/paperless/media/

# Test file access from worker component
kubectl exec -it deployment/paless-worker -c paless-worker -- ls -la /usr/src/paperless/media/

# Monitor rclone activity in real-time (pick any web pod as an example)
kubectl logs -f deployment/paless-web -c rclone
```

**Storage Access:**

```bash
# Verify data PVC is bound to all components
kubectl get pvc paperless-data-pvc
kubectl describe pvc paperless-data-pvc

# Verify media PVC is bound
kubectl get pvc paperless-media-pvc
kubectl describe pvc paperless-media-pvc

# Check that all components see the same data directory
kubectl exec deployment/paless-web -c paless-web -- ls -la /usr/src/paperless/data/
kubectl exec deployment/paless-worker -c paless-worker -- ls -la /usr/src/paperless/data/
kubectl exec deployment/paless-scheduler -c paless-scheduler -- ls -la /usr/src/paperless/data/
```

**HPA Status:**

```bash
# Check HPA controllers
kubectl get hpa

# Detailed HPA information
kubectl describe hpa web-hpa
kubectl describe hpa worker-hpa

# Monitor HPA behavior (scales replicas based on metrics)
kubectl get hpa --watch

# Check current resource metrics
kubectl top pods -l app=paless
```

**Resource Usage:**

```bash
# Check CPU and memory usage per component
kubectl top pods -l app=paless,component=web
kubectl top pods -l app=paless,component=worker
kubectl top pods -l app=paless,component=scheduler

# Monitor node resource availability
kubectl top nodes

# Check resource requests vs usage
kubectl describe nodes
```

**End-to-End Functionality Test:**

```bash
# 1. Upload a test document via web API
curl -X POST -F "document=@test.pdf" http://<ingress-ip>/api/documents/post_document/

# 2. Check if worker picked up the task
kubectl logs -f -l app=paless,component=worker -c paless-worker | grep "processing"

# 3. Verify document appears in media storage
kubectl exec -it deployment/paless-web -c paless-web -- ls -la /usr/src/paperless/media/

# 4. Check MinIO bucket content
kubectl exec -it deployment/minio -- mc ls minio/paperless-media
```

## Automated Deployment with deploy-to-k3s.sh

For a streamlined deployment experience, the `scripts/deploy-to-k3s.sh` script automates many of the manual steps described above. This script is particularly useful for development and rapid iteration.

### What the Script Automates

1. **Configuration Loading**: Reads `paless.env` for environment settings
2. **Application Detection**: Auto-discovers Dockerfiles in subdirectories
3. **Image Building**: Builds Docker images with consistent naming
4. **Registry Push**: Pushes images to configured registry
5. **Kustomize Deployment**: Applies environment-specific overlays
6. **Health Verification**: Waits for pods to reach Ready state
7. **Status Display**: Shows helpful debugging information and next steps

### Script Features

- **paless.env Integration**: Sources configuration for Kubernetes deployment
- **Multi-overlay Support**: Deploy to different environments (dev, staging, prod)
- **Auto-detection**: Finds all applications without manual configuration
- **Error Handling**: Provides clear error messages and troubleshooting commands
- **Namespace Management**: Configurable Kubernetes namespace per deployment

### Quick Reference

```bash
# Show usage and available applications
./scripts/deploy-to-k3s.sh help

# Deploy all detected applications
./scripts/deploy-to-k3s.sh all

# Deploy specific application
./scripts/deploy-to-k3s.sh paperless

# Show deployment status
./scripts/deploy-to-k3s.sh status
```

### Configuration with paless.env

Create `paless.env` in the repository root to customize deployment:

```env
PALESS_NAMESPACE=production
REGISTRY=registry.example.com:5000
POSTGRES_PASSWORD=your-secure-password
MINIO_ROOT_PASSWORD=your-secure-password
PAPERLESS_TIME_ZONE=America/New_York
OVERLAY=prod
```

See [Configuration Management](./configuration.md#deployment-script-integration) for complete details.

### Kustomize Integration

The script applies Kustomize overlays from:

```
k8s/overlays/{OVERLAY}/
```

Where `{OVERLAY}` is specified by the `OVERLAY` variable in `paless.env` (default: `dev`).

Each overlay can customize:
- Resource names and labels
- Image tags and registries
- Replica counts
- Resource limits
- Storage configurations
- Environment-specific patches

### Environment Variables for Kustomize

The script exports these variables for use in Kustomize templates:

```bash
PALESS_NAMESPACE     # Kubernetes namespace
REGISTRY             # Container image registry
POSTGRES_DB          # Database name
POSTGRES_USER        # Database user
POSTGRES_PASSWORD    # Database password
MINIO_ROOT_USER      # MinIO admin user
MINIO_ROOT_PASSWORD  # MinIO admin password
MINIO_BUCKET         # S3 bucket name
PAPERLESS_SECRET_KEY # Django secret key
PAPERLESS_TIME_ZONE  # Application timezone
PAPERLESS_OCR_LANGUAGE  # OCR languages
```

Use these in your Kustomize base files with `envsubst`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: paless-config
data:
  PALESS_NAMESPACE: ${PALESS_NAMESPACE}
  REGISTRY: ${REGISTRY}
  POSTGRES_DB: ${POSTGRES_DB}
```

### Workflow Example

```bash
# 1. Create configuration
cat > paless.env << 'EOF'
PALESS_NAMESPACE=paperless-prod
REGISTRY=ghcr.io/myorg
POSTGRES_PASSWORD=$(openssl rand -base64 32)
MINIO_ROOT_PASSWORD=$(openssl rand -base64 32)
OVERLAY=prod
EOF

# 2. Deploy applications
./scripts/deploy-to-k3s.sh all

# 3. Verify deployment
./scripts/deploy-to-k3s.sh status

# 4. Check application logs
kubectl logs -n paperless-prod deployment/paperless -f
```

### Troubleshooting

If deployment fails, the script provides:
1. **Detailed error messages** with the specific problem
2. **Suggested commands** to investigate further
3. **Event logs** from recent Kubernetes activity
4. **Pod status** to understand what went wrong

See [Quick Start](./quickstart.md#troubleshooting-deploy-script-issues) for common issues and solutions.

### Manual vs. Automated Deployment

| Aspect | Manual | Script |
|--------|--------|--------|
| Configuration | Environment variables | paless.env file |
| Image Build | Manual docker build | Automatic detection |
| Registry Push | Manual docker push | Automatic push |
| Deployment | Manual kubectl apply | Kustomize overlay |
| Verification | Manual kubectl checks | Automatic health checks |
| Learning Curve | Higher (understand all steps) | Lower (script handles details) |
| Customization | Full control | Through paless.env |

**Recommendation**: Use the script for development and CI/CD pipelines. Use manual steps for understanding and debugging complex deployments.

## Related Documentation

- [PostgreSQL StatefulSet Guide](./postgres-statefulset.md) - Complete PostgreSQL deployment and multi-tenancy configuration
- [MinIO Multi-Tenant Storage](./minio-multi-tenant.md) - Per-tenant bucket isolation strategy
- [Volume Configuration](./volume-configuration.md) - PersistentVolume and PersistentVolumeClaim reference

## External References

- [Kubernetes Persistent Volumes Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Persistent Volume Claims Guide](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaims)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [rclone Documentation](https://rclone.org/docs/)
- [rclone S3 Configuration](https://rclone.org/s3/)
- [MinIO Kubernetes Deployment](https://min.io/docs/minio/kubernetes/upstream/)
