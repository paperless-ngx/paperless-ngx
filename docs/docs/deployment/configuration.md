---
sidebar_position: 2
title: Configuration Management
description: Central configuration file for all Paless deployment settings
---

# Configuration Management

This guide covers the central `paless.env` configuration file, which defines all settings for Paless deployments across environments.

## Overview

The `paless.env` file is the single source of truth for deployment configuration. It contains all environment variables, database settings, object storage configuration, and application parameters needed for running Paperless NGX on Kubernetes.

**Location:** `/workspace/paless.env` (repository root)

### Why a Central Configuration File?

- **Single Source of Truth**: All deployment settings in one place
- **Environment Consistency**: Same configuration applied across development, staging, and production
- **Version Control**: Track configuration changes through git history
- **Security**: Clear documentation of what needs to be changed for production

## File Structure

The `paless.env` file is organized into logical sections:

### 1. Namespace Configuration

```env
PALESS_NAMESPACE=paless
```

**Purpose:** Specifies the Kubernetes namespace where all resources are deployed.

**Usage:**
- Development: `paless` (development namespace)
- Production: Keep separate from development environment

### 2. Container Registry Configuration

```env
REGISTRY=localhost:5000
```

**Purpose:** Container registry for storing and pulling images.

**Development:**
- `localhost:5000` - Local K3s registry
- Some configurations use `:5001` for alternative setups

**Production:**
- Replace with your production registry
- Examples: `ghcr.io/your-org`, `docker.io/your-org`, `ecr.aws/your-account`

:::warning Production Requirement
This value **MUST be changed** for production deployments.
:::

### 3. PostgreSQL Database Configuration

```env
POSTGRES_DB=paperless
POSTGRES_USER=paperless
POSTGRES_PASSWORD=dev-postgres-password-changeme
```

**Purpose:** Database credentials for the primary Paperless application database.

| Variable | Purpose | Notes |
|----------|---------|-------|
| `POSTGRES_DB` | Database name | Usually `paperless` |
| `POSTGRES_USER` | Database user | Database owner |
| `POSTGRES_PASSWORD` | Database password | **CHANGE IN PRODUCTION** |

**Generating a Secure Password:**
```bash
openssl rand -base64 32
```

:::warning Production Security
Always use a strong, randomly generated password in production. The development default (`dev-postgres-password-changeme`) is insecure and only suitable for local development.
:::

### 4. MinIO Object Storage Configuration

```env
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=dev-minio-password-changeme
MINIO_BUCKET=paperless-documents
```

**Purpose:** S3-compatible object storage for document and media files.

| Variable | Purpose | Notes |
|----------|---------|-------|
| `MINIO_ROOT_USER` | MinIO admin username | For console access |
| `MINIO_ROOT_PASSWORD` | MinIO admin password | **CHANGE IN PRODUCTION** |
| `MINIO_BUCKET` | S3 bucket for documents | Usually `paperless-documents` or `paperless-media` |

**MinIO Console Access:**
- API Endpoint: `http://minio:9000`
- Console UI: `http://minio:9001`
- Login with credentials from configuration

:::warning Minimum Password Length
MinIO passwords must be at least 8 characters. Development defaults are sufficient length but must be changed for production.
:::

### 5. Paperless-ngx Application Configuration

```env
PAPERLESS_SECRET_KEY=dev-secret-key-change-in-production-x7k9m2p5q8w1r4t6
PAPERLESS_TIME_ZONE=UTC
PAPERLESS_OCR_LANGUAGE=eng
```

**Purpose:** Core application settings for Paperless NGX.

| Variable | Purpose | Notes |
|----------|---------|-------|
| `PAPERLESS_SECRET_KEY` | Django cryptographic key | Used for session management and signing |
| `PAPERLESS_TIME_ZONE` | Timezone (TZ database format) | Examples: `UTC`, `America/New_York`, `Europe/London`, `Asia/Tokyo` |
| `PAPERLESS_OCR_LANGUAGE` | OCR language(s) for document processing | Examples: `eng`, `deu`, `fra`, `spa`. Multiple: `eng+deu` |

**Generating a New Secret Key:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Available OCR Languages:**
- `eng` - English
- `deu` - German
- `fra` - French
- `spa` - Spanish
- `ita` - Italian
- `por` - Portuguese

See [Tesseract language codes](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html) for complete list.

## Using paless.env

### Loading Configuration

The configuration is loaded by Kubernetes manifests using:

1. **Secrets** - For sensitive credentials (passwords, keys)
2. **ConfigMaps** - For non-sensitive configuration values

Example in `paless-secret.yaml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: paless-secret
type: Opaque
stringData:
  postgres-password: ${POSTGRES_PASSWORD}
  minio-root-user: ${MINIO_ROOT_USER}
  minio-root-password: ${MINIO_ROOT_PASSWORD}
  paperless-secret-key: ${PAPERLESS_SECRET_KEY}
```

Example in `configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: paless-config
data:
  PALESS_NAMESPACE: "paless"
  REGISTRY: "localhost:5000"
  POSTGRES_DB: "paperless"
  POSTGRES_USER: "paperless"
  PAPERLESS_TIME_ZONE: "UTC"
  PAPERLESS_OCR_LANGUAGE: "eng"
  MINIO_BUCKET: "paperless-documents"
```

### Environment-Specific Overrides

The Kubernetes structure supports environment-specific overrides using Kustomize:

```
k8s/
├── base/              # Base configuration (uses paless.env defaults)
│   ├── configmap.yaml
│   ├── paless-secret.yaml.example
│   └── ...
└── overlays/
    ├── dev/           # Development overrides
    ├── staging/       # Staging overrides
    └── prod/          # Production overrides (NEVER commit secrets)
```

**Development** (`overlays/dev/`)
```yaml
# paless-secret-patch.yaml
apiVersion: v1
kind: Secret
metadata:
  name: paless-secret
stringData:
  postgres-password: dev-postgres-password
  minio-root-password: dev-minio-password
```

**Production** (`overlays/prod/`)
```yaml
# .gitignore entry:
k8s/overlays/prod/paless-secret-patch.yaml

# paless-secret-patch.yaml (NOT in version control)
apiVersion: v1
kind: Secret
metadata:
  name: paless-secret
stringData:
  postgres-password: ${PROD_PASSWORD}  # From secure store
  minio-root-password: ${PROD_MINIO_PASSWORD}
  paperless-secret-key: ${PROD_SECRET_KEY}
```

## Security Checklist

Before deploying to production, verify all items:

- [ ] Changed `POSTGRES_PASSWORD` to a strong password
- [ ] Changed `MINIO_ROOT_USER` to a secure username
- [ ] Changed `MINIO_ROOT_PASSWORD` to a strong password
- [ ] Generated new `PAPERLESS_SECRET_KEY`
- [ ] Updated `REGISTRY` to your production registry
- [ ] Set appropriate `PAPERLESS_TIME_ZONE`
- [ ] Configured `PAPERLESS_OCR_LANGUAGE` for your documents
- [ ] Stored secrets securely (use secrets management tool)
- [ ] Did NOT commit production secrets to version control
- [ ] Reviewed all configuration values for your environment

:::danger Never Commit Production Secrets
Production values should NEVER be committed to version control. Use:
- Sealed Secrets
- External Secrets Operator
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Similar secrets management solutions
:::

## Configuration Best Practices

### 1. Secret Management

**Development:**
```env
# Safe to commit - development values
POSTGRES_PASSWORD=dev-postgres-password-changeme
MINIO_ROOT_PASSWORD=dev-minio-password-changeme
PAPERLESS_SECRET_KEY=dev-secret-key-change-in-production
```

**Production:**
- Generate secrets offline
- Store in secrets management system
- Use sealed secrets or operator for deployment
- Rotate regularly (at least quarterly)
- Never share or log credentials

### 2. Environment-Specific Values

**Development:**
```env
REGISTRY=localhost:5000
PAPERLESS_TIME_ZONE=UTC
```

**Production:**
```env
REGISTRY=gcr.io/my-project/paperless-ngx
PAPERLESS_TIME_ZONE=America/New_York  # Your actual timezone
```

### 3. Capacity Planning

Configure `POSTGRES_PASSWORD` and `MINIO_ROOT_PASSWORD` based on expected load:

**Small Deployment (< 1000 documents)**
- PostgreSQL: 1Gi disk
- MinIO: 5Gi disk
- Memory: 512Mi each

**Medium Deployment (1000-10000 documents)**
- PostgreSQL: 2Gi disk
- MinIO: 10Gi disk
- Memory: 1Gi each

**Large Deployment (> 10000 documents)**
- PostgreSQL: 5Gi+ disk
- MinIO: 20Gi+ disk
- Memory: 2Gi each

### 4. Timezone Configuration

Choose the timezone matching your deployment location:

```env
# Common examples:
PAPERLESS_TIME_ZONE=UTC                    # Coordinated Universal Time
PAPERLESS_TIME_ZONE=America/New_York       # Eastern Time
PAPERLESS_TIME_ZONE=America/Chicago        # Central Time
PAPERLESS_TIME_ZONE=America/Denver         # Mountain Time
PAPERLESS_TIME_ZONE=America/Los_Angeles    # Pacific Time
PAPERLESS_TIME_ZONE=Europe/London          # GMT/BST
PAPERLESS_TIME_ZONE=Europe/Paris           # CET/CEST
PAPERLESS_TIME_ZONE=Asia/Tokyo             # JST
PAPERLESS_TIME_ZONE=Australia/Sydney       # AEDT/AEST
```

### 5. OCR Language Support

Configure languages based on document types:

**Single language:**
```env
PAPERLESS_OCR_LANGUAGE=eng
```

**Multiple languages:**
```env
PAPERLESS_OCR_LANGUAGE=eng+deu+fra
```

**Language-specific considerations:**
- English (`eng`) - Universal, best support
- German (`deu`) - Common in European documents
- French (`fra`) - European and African documents
- Spanish (`spa`) - Iberian and Latin American
- Adding more languages increases OCR time

## Troubleshooting Configuration Issues

### Invalid Timezone

```bash
# Test timezone validity
python -c "import pytz; pytz.timezone('America/New_York')"

# See all available timezones
python -c "import pytz; print(len(pytz.all_timezones))" # 593 zones
```

### Secret Not Loaded

```bash
# Check if secret exists
kubectl get secret paless-secret

# Verify secret contents (redacted)
kubectl describe secret paless-secret

# Check pod environment variables
kubectl exec pod/paperless -- env | grep PAPERLESS
```

### Registry Connection Failed

```bash
# Verify registry is accessible
docker pull ${REGISTRY}/paperless-ngx:latest

# Check registry configuration in deployment
kubectl get deployment paperless -o yaml | grep image:
```

### OCR Language Not Available

```bash
# Check available OCR languages in running pod
kubectl exec pod/paperless -- tesseract --list-langs

# Install additional language if needed (requires image rebuild)
```

## Migration and Updates

### Updating Configuration

1. **Edit paless.env** in repository
2. **Regenerate secrets** if values changed:
   ```bash
   kubectl delete secret paless-secret
   # Update k8s/overlays/[env]/paless-secret-patch.yaml
   kubectl apply -k k8s/overlays/[env]/
   ```
3. **Restart pods** to apply new configuration:
   ```bash
   kubectl rollout restart deployment/paperless
   ```

### Changing Sensitive Values

For production changes:

1. Update secrets in your secrets management system
2. Sync to Kubernetes:
   ```bash
   # Using External Secrets Operator, Sealed Secrets, etc.
   kubectl annotate secret paless-secret refresh-secret=true
   ```
3. Restart affected deployments
4. Verify in application logs

## Deployment Script Integration

The `scripts/deploy-to-k3s.sh` helper script automatically sources the `paless.env` file and exports all configuration variables for use with Kustomize overlays.

### How the Script Uses paless.env

1. **Script sources paless.env** during initialization
2. **Variables are exported** for Kustomize `envsubst` replacements
3. **Defaults are applied** for unspecified variables
4. **Configuration is passed to Kustomize** during deployment

### Exported Variables

The following variables from `paless.env` are exported for Kustomize use:

```bash
export PALESS_NAMESPACE
export REGISTRY
export POSTGRES_DB
export POSTGRES_USER
export POSTGRES_PASSWORD
export MINIO_ROOT_USER
export MINIO_ROOT_PASSWORD
export MINIO_BUCKET
export PAPERLESS_SECRET_KEY
export PAPERLESS_TIME_ZONE
export PAPERLESS_OCR_LANGUAGE
```

### Script Workflow

```
1. Load paless.env (if exists)
2. Load .context-management/.env (if exists)
3. Apply defaults for missing variables
4. Export all variables
5. Auto-detect Dockerfiles
6. Build and push images
7. Apply Kustomize overlays
8. Wait for pods to be ready
9. Display status and helpful commands
```

### Example: Using paless.env with the Script

```bash
# Create paless.env
cat > paless.env << 'EOF'
PALESS_NAMESPACE=production
REGISTRY=registry.example.com:5000
POSTGRES_PASSWORD=$(openssl rand -base64 32)
MINIO_ROOT_PASSWORD=$(openssl rand -base64 32)
PAPERLESS_TIME_ZONE=America/New_York
OVERLAY=prod
EOF

# Run deployment script
./scripts/deploy-to-k3s.sh all

# The script automatically uses paless.env configuration
# for all build and deployment operations
```

### Backwards Compatibility

If `paless.env` doesn't exist, the script:
- Uses hardcoded defaults from the script itself
- Allows deployment to proceed without external configuration
- Enables scripting and CI/CD pipelines without file creation

**Recommended:** Always create `paless.env` for consistency across deployments.

## Related Documentation

- [Kubernetes Deployment Guide](./kubernetes-guide.md) - Architecture and volume configuration
- [Quick Start](./quickstart.md) - Getting started with deployment, including deploy-to-k3s.sh usage
- [Volume Configuration](./volume-configuration.md) - Persistent storage setup

## References

- [Django Secret Key Generation](https://docs.djangoproject.com/en/stable/ref/settings/#secret-key)
- [Python Timezone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
- [Tesseract OCR Languages](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html)
- [MinIO Documentation](https://docs.min.io/)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
