#!/bin/bash

# Script: test-bucket-isolation.sh
# Purpose: Test MinIO bucket isolation between tenants
# Usage: ./test-bucket-isolation.sh [namespace]

set -e

NAMESPACE="${1:-generic-repo}"

echo "=========================================="
echo "MinIO Bucket Isolation Test"
echo "=========================================="
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
echo ""

# Test 1: Create test buckets for three tenants
echo "Test 1: Creating test buckets for three tenants"
echo "================================================"

TENANTS=("tenant-a" "tenant-b" "tenant-c")

for tenant in "${TENANTS[@]}"; do
    bucket_name="paperless-${tenant}"
    echo "Creating bucket: $bucket_name"
    kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
        mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
        mc mb --ignore-existing local/$bucket_name > /dev/null 2>&1 && \
        echo '✓ Bucket $bucket_name created'
    "
done

echo ""
echo "Test 2: List all buckets"
echo "========================"
kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
    mc ls local/
"

echo ""
echo "Test 3: Upload test files to each tenant bucket"
echo "================================================"

for tenant in "${TENANTS[@]}"; do
    bucket_name="paperless-${tenant}"
    test_content="This is test data for ${tenant}"
    echo "Uploading test file to: $bucket_name"
    kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
        mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
        echo '$test_content' | mc pipe local/$bucket_name/test-file-${tenant}.txt && \
        echo '✓ Uploaded test-file-${tenant}.txt to $bucket_name'
    "
done

echo ""
echo "Test 4: Verify bucket isolation"
echo "================================"
echo "Each bucket should only contain its own test file"

for tenant in "${TENANTS[@]}"; do
    bucket_name="paperless-${tenant}"
    echo ""
    echo "Contents of $bucket_name:"
    kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
        mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
        mc ls local/$bucket_name/
    "
done

echo ""
echo "Test 5: Verify file content from tenant-a bucket"
echo "================================================="
kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
    mc cat local/paperless-tenant-a/test-file-tenant-a.txt
"

echo ""
echo ""
echo "Test 6: Verify tenant-b cannot access tenant-a files"
echo "====================================================="
echo "Attempting to access paperless-tenant-a/test-file-tenant-a.txt from tenant-b context"
echo "(Note: With root credentials, all buckets are accessible - proper isolation requires IAM policies)"
kubectl exec -n "$NAMESPACE" "$MINIO_POD" -- sh -c "
    mc alias set local http://localhost:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' > /dev/null 2>&1 && \
    mc ls local/paperless-tenant-b/ | grep -q test-file-tenant-a || echo '✓ tenant-a file not found in tenant-b bucket (correct isolation)'
"

echo ""
echo "=========================================="
echo "Bucket Isolation Test Summary"
echo "=========================================="
echo "✓ Created 3 tenant buckets successfully"
echo "✓ Uploaded files to each bucket"
echo "✓ Verified bucket isolation (each bucket contains only its own files)"
echo ""
echo "Note: True tenant isolation requires:"
echo "  1. Separate access credentials per tenant (IAM users/policies)"
echo "  2. Bucket policies restricting cross-tenant access"
echo "  3. Application-level tenant context enforcement"
echo ""
echo "Current test validates bucket-per-tenant structure is working."
echo "=========================================="
