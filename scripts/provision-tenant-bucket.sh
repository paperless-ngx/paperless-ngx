#!/bin/bash

# Script: provision-tenant-bucket.sh
# Purpose: Provision a MinIO bucket for a tenant with proper isolation
# Usage: ./provision-tenant-bucket.sh <tenant_id> [namespace]

set -e

# Configuration
TENANT_ID="${1}"
NAMESPACE="${2:-generic-repo}"
BUCKET_PREFIX="paperless"

# Validation
if [ -z "$TENANT_ID" ]; then
    echo "ERROR: Tenant ID is required"
    echo "Usage: $0 <tenant_id> [namespace]"
    exit 1
fi

# Validate tenant ID format (alphanumeric and hyphens only)
if ! [[ "$TENANT_ID" =~ ^[a-z0-9-]+$ ]]; then
    echo "ERROR: Tenant ID must contain only lowercase letters, numbers, and hyphens"
    exit 1
fi

# Construct bucket name following convention: paperless-<tenant_id>
BUCKET_NAME="${BUCKET_PREFIX}-${TENANT_ID}"

echo "=========================================="
echo "MinIO Tenant Bucket Provisioning"
echo "=========================================="
echo "Tenant ID: $TENANT_ID"
echo "Bucket Name: $BUCKET_NAME"
echo "Namespace: $NAMESPACE"
echo "=========================================="

# Get MinIO pod name
echo "Finding MinIO pod..."
MINIO_POD=$(kubectl get pods -n "$NAMESPACE" -l app=minio -o jsonpath='{.items[0].metadata.name}')

if [ -z "$MINIO_POD" ]; then
    echo "ERROR: MinIO pod not found in namespace $NAMESPACE"
    exit 1
fi

echo "Found MinIO pod: $MINIO_POD"

# Get MinIO credentials from secret
echo "Retrieving MinIO credentials..."
MINIO_ROOT_USER=$(kubectl get secret paless-secret -n "$NAMESPACE" -o jsonpath='{.data.minio-root-user}' | base64 -d)
MINIO_ROOT_PASSWORD=$(kubectl get secret paless-secret -n "$NAMESPACE" -o jsonpath='{.data.minio-root-password}' | base64 -d)

if [ -z "$MINIO_ROOT_USER" ] || [ -z "$MINIO_ROOT_PASSWORD" ]; then
    echo "ERROR: Failed to retrieve MinIO credentials from secret"
    exit 1
fi

echo "Credentials retrieved successfully"

# Create bucket using kubectl exec
echo "Creating bucket '$BUCKET_NAME'..."
START_TIME=$(date +%s)

kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && \
    mc mb --ignore-existing local/$BUCKET_NAME && \
    echo 'Bucket created successfully'
"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=========================================="
echo "Bucket provisioned successfully!"
echo "Bucket: $BUCKET_NAME"
echo "Time taken: ${DURATION} seconds"
echo "=========================================="

# Verify bucket exists
echo "Verifying bucket exists..."
kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' && \
    mc ls local/ | grep $BUCKET_NAME
"

if [ $? -eq 0 ]; then
    echo "✓ Bucket verification successful"
else
    echo "✗ Bucket verification failed"
    exit 1
fi

echo ""
echo "Bucket '$BUCKET_NAME' is ready for tenant '$TENANT_ID'"
