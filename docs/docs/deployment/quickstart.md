---
sidebar_position: 3
title: Quick Start
description: Get Paperless NGX running on Kubernetes with persistent storage
---

# Kubernetes Quick Start

Deploy Paperless NGX on Kubernetes in minutes with proper persistent volume configuration.

## Prerequisites

- Kubernetes cluster (1.20+)
- `kubectl` configured with cluster access
- At least 3Gi available storage
- Kustomize (optional, for simplified deployment)

## Option 1: Manual Deployment

### Step 1: Create Persistent Volumes

Save as `pv.yaml`:

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
    path: /data/paperless-data
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
    path: /data/paperless-media
    type: DirectoryOrCreate
```

Apply:
```bash
kubectl apply -f pv.yaml
```

### Step 2: Create Persistent Volume Claims

Save as `pvc.yaml`:

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

Apply:
```bash
kubectl apply -f pvc.yaml
```

### Step 3: Deploy Application

Save as `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paperless
  labels:
    app: paperless
spec:
  replicas: 1
  selector:
    matchLabels:
      app: paperless
  template:
    metadata:
      labels:
        app: paperless
    spec:
      containers:
        - name: paperless
          image: paperless-ngx:latest
          ports:
            - containerPort: 8000
          volumeMounts:
            - name: data
              mountPath: /usr/src/paperless/data
            - name: media
              mountPath: /usr/src/paperless/media
          env:
            - name: PAPERLESS_TIME_ZONE
              value: "UTC"
            - name: PAPERLESS_ALLOWED_HOSTS
              value: "*"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: paperless-data-pvc
        - name: media
          persistentVolumeClaim:
            claimName: paperless-media-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: paperless
spec:
  selector:
    app: paperless
  ports:
    - port: 8000
      targetPort: 8000
  type: NodePort
```

Apply:
```bash
kubectl apply -f deployment.yaml

# Check status
kubectl get pods
kubectl get pvc
```

## Option 2: Kustomize Deployment with MinIO

### Directory Structure

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── secret.yaml
│   ├── configmap.yaml
│   ├── minio-statefulset.yaml
│   ├── minio-service.yaml
│   ├── minio-init-job.yaml
│   ├── rclone-configmap.yaml
│   ├── pvc.yaml
│   └── deployment.yaml
└── overlays/
    └── dev/
        ├── kustomization.yaml
        └── minio-console-nodeport.yaml
```

### Step 1: Create Secrets and ConfigMaps

Create `base/secret.yaml` with MinIO credentials:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: paless-secret
type: Opaque
stringData:
  minio-root-user: minioadmin
  minio-root-password: minioadmin
```

:::caution Development
The above credentials are for development only. In production, use strong, unique credentials and rotate them regularly.
:::

### Step 2: Deploy MinIO and Bucket

Create `base/minio-statefulset.yaml`:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minio
  labels:
    app: minio
spec:
  serviceName: minio
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
      - name: minio
        image: minio/minio:latest
        ports:
        - containerPort: 9000
          name: s3-api
        - containerPort: 9001
          name: console
        command:
        - minio
        - server
        - /data
        - --console-address
        - ":9001"
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
        volumeMounts:
        - name: minio-data
          mountPath: /data
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
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1"
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

Create `base/minio-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minio
  labels:
    app: minio
spec:
  clusterIP: None
  selector:
    app: minio
  ports:
  - port: 9000
    targetPort: 9000
    name: s3-api
  - port: 9001
    targetPort: 9001
    name: console
```

Create `base/minio-init-job.yaml` to initialize bucket:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-init
spec:
  template:
    spec:
      serviceAccountName: default
      containers:
      - name: init
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
        - /bin/sh
        - -c
        - |
          # Wait for MinIO to be ready
          until mc alias set minio http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD; do
            echo "Waiting for MinIO..."
            sleep 2
          done

          # Create bucket if it doesn't exist
          mc mb minio/paperless-media || true

          echo "MinIO initialization complete"
      restartPolicy: Never
  backoffLimit: 3
```

### Step 3: Configure rclone

Create `base/rclone-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rclone-config
  labels:
    app: paperless
data:
  rclone.conf: |
    [minio]
    type = s3
    provider = Minio
    endpoint = http://minio:9000
    env_auth = true
    acl = private
```

### Step 4: Update Deployment

Update `base/deployment.yaml` to include rclone sidecar:

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
        - name: data
          mountPath: /usr/src/paperless/data
        - name: media
          mountPath: /usr/src/paperless/media
      - name: rclone
        image: rclone/rclone:latest
        securityContext:
          privileged: true
        command:
        - /bin/sh
        - -c
        - |
          rclone mount minio:paperless-media /mnt/media \
            --vfs-cache-mode full \
            --allow-other \
            --daemon
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
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: paperless-data-pvc
      - name: media
        emptyDir: {}
      - name: rclone-config
        configMap:
          name: rclone-config
```

### Step 5: Deploy with Kustomize

Create `base/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - secret.yaml
  - configmap.yaml
  - rclone-configmap.yaml
  - minio-statefulset.yaml
  - minio-service.yaml
  - minio-init-job.yaml
  - pvc.yaml
  - deployment.yaml

labels:
  - includeSelectors: true
    pairs:
      app: paperless
```

Deploy everything:

```bash
kubectl apply -k k8s/base/
```

For development, also add MinIO console access by creating `overlays/dev/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

resources:
  - minio-console-nodeport.yaml
```

And `overlays/dev/minio-console-nodeport.yaml`:

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

Deploy dev environment:

```bash
kubectl apply -k k8s/overlays/dev/
```

## Verification

### Check Persistent Volumes

```bash
# List volumes and claims
kubectl get pv,pvc

# Example output:
# NAME                            CAPACITY   ...
# pv/paperless-data-pv            1Gi        ...
# pv/paperless-media-pv           2Gi        ...
#
# NAME                                    STATUS   VOLUME              CAPACITY
# pvc/paperless-data-pvc                  Bound    paperless-data-pv   1Gi
# pvc/paperless-media-pvc                 Bound    paperless-media-pv  2Gi
```

### Check Pod Status

```bash
# Watch pod creation
kubectl get pods -w

# Once running, verify mounts
kubectl exec deployment/paperless -- df -h
```

### Verify MinIO Deployment

```bash
# Check MinIO StatefulSet
kubectl get statefulset minio

# Check MinIO Pod
kubectl get pods -l app=minio

# Verify MinIO is ready
kubectl wait --for=condition=ready pod -l app=minio --timeout=300s

# Check MinIO service
kubectl get svc minio

# Verify bucket initialization job
kubectl get jobs minio-init
kubectl logs job/minio-init
```

### Access MinIO Console

```bash
# Port forward to MinIO console
kubectl port-forward svc/minio 9001:9001

# Access at: http://localhost:9001
# Credentials: minioadmin/minioadmin (from secret)
```

### Verify rclone Sidecar

```bash
# Check paperless pod has rclone sidecar
kubectl get pod -l app=paperless -o jsonpath='{.items[0].spec.containers[*].name}'

# Verify media mount is working
kubectl exec deployment/paperless -c rclone -- mount | grep minio

# Check mounted filesystem from paperless container
kubectl exec deployment/paperless -c paperless -- ls -la /usr/src/paperless/media
```

### Access Application

```bash
# Get service port
kubectl get svc paperless

# Access via port forwarding
kubectl port-forward svc/paperless 8000:8000

# Then open: http://localhost:8000
```

## Common Configurations

### Environment Variables

```yaml
env:
  - name: PAPERLESS_TIME_ZONE
    value: "America/New_York"
  - name: PAPERLESS_ALLOWED_HOSTS
    value: "paperless.example.com"
  - name: PAPERLESS_SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: paperless-secret
        key: secret-key
```

### Resource Limits

For different workloads:

**Small Document Volume (< 1000 docs):**
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

**Medium Document Volume (1000-10000 docs):**
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

**Large Document Volume (> 10000 docs):**
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### Readiness and Liveness Probes

Add health checks to your deployment:

```yaml
containers:
  - name: paperless
    livenessProbe:
      httpGet:
        path: /
        port: 8000
      initialDelaySeconds: 60
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 3
```

## Troubleshooting

### PVC Not Binding

Check if persistent volumes are available:

```bash
# Check PV status
kubectl get pv

# Check PVC details
kubectl describe pvc paperless-data-pvc

# Verify storage class matches
kubectl get storageclass
```

### Pod Fails to Start

```bash
# Check pod events
kubectl describe pod deployment/paperless

# Check logs
kubectl logs deployment/paperless

# Check volume mounts
kubectl get pod -o jsonpath='{.items[0].spec.volumes}' | jq
```

### Connection Refused

```bash
# Verify service is created
kubectl get svc paperless

# Check service endpoints
kubectl get endpoints paperless

# Test connectivity from pod
kubectl run -it debug --image=curlimages/curl --restart=Never -- \
  curl http://paperless:8000
```

## Next Steps

1. **Configure Secrets**: Store sensitive data (secret key, passwords)
2. **Set Up Backup**: Implement regular volume snapshots
3. **Configure Ingress**: Expose application via ingress controller
4. **Monitor Storage**: Set up alerts for volume usage
5. **Enable Auto-Scaling**: Configure based on your workload

See [Kubernetes Deployment Guide](./kubernetes-guide.md) for detailed configuration options.

## Additional Resources

- [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kustomize Documentation](https://kustomize.io/)
