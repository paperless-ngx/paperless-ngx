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

## Option 2: Kustomize Deployment

### Directory Structure

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── pv-manual.yaml
│   ├── pvc.yaml
│   └── deployment.yaml
└── overlays/
    └── dev/
        └── kustomization.yaml
```

### base/kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: default

resources:
  - pv-manual.yaml
  - pvc.yaml
  - deployment.yaml

labels:
  - includeSelectors: true
    pairs:
      app: paperless
```

### Deploy with Kustomize

```bash
kubectl apply -k k8s/base/
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
