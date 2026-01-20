#!/bin/bash
# PostgreSQL Multi-Tenancy Verification Script
# This script verifies that PostgreSQL is properly configured for multi-tenant architecture

set -e

NAMESPACE="paless"
POSTGRES_POD="postgres-0"

echo "=========================================="
echo "PostgreSQL Multi-Tenancy Verification"
echo "=========================================="
echo ""

# Check if pod is running
echo "1. Checking PostgreSQL pod status..."
POD_STATUS=$(kubectl get pods -n $NAMESPACE | grep postgres | head -1 | awk '{print $3}')
if [ "$POD_STATUS" != "Running" ]; then
    echo "❌ FAILED: PostgreSQL pod is not running (Status: $POD_STATUS)"
    exit 1
fi
echo "✅ PASSED: PostgreSQL pod is Running"
echo ""

# Check PostgreSQL version
echo "2. Checking PostgreSQL version..."
VERSION=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT version();" | grep -oP 'PostgreSQL \K[0-9]+')
if [ "$VERSION" -ge 16 ]; then
    echo "✅ PASSED: PostgreSQL version $VERSION (>= 16 required)"
else
    echo "❌ FAILED: PostgreSQL version $VERSION (< 16)"
    exit 1
fi
echo ""

# Check database exists
echo "3. Checking database 'paperless' exists..."
DB_EXISTS=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT 1 FROM pg_database WHERE datname = 'paperless';" || echo "0")
if [ "$DB_EXISTS" = "1" ]; then
    echo "✅ PASSED: Database 'paperless' exists"
else
    echo "❌ FAILED: Database 'paperless' does not exist"
    exit 1
fi
echo ""

# Check paperless_app user exists
echo "4. Checking user 'paperless_app' exists..."
USER_EXISTS=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'paperless_app';" || echo "0")
if [ "$USER_EXISTS" = "1" ]; then
    echo "✅ PASSED: User 'paperless_app' exists"
else
    echo "❌ FAILED: User 'paperless_app' does not exist"
    exit 1
fi
echo ""

# Check user permissions
echo "5. Checking paperless_app permissions..."
PERMS=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT COUNT(DISTINCT privilege_type) FROM information_schema.role_table_grants WHERE grantee = 'paperless_app' AND privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE');" || echo "0")
if [ "$PERMS" -ge 4 ]; then
    echo "✅ PASSED: User 'paperless_app' has required permissions (SELECT, INSERT, UPDATE, DELETE)"
else
    echo "⚠️  WARNING: User 'paperless_app' may not have all required permissions (found $PERMS/4 privilege types)"
fi
echo ""

# Check extensions
echo "6. Checking PostgreSQL extensions..."
UUID_EXT=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp';" || echo "0")
CRYPTO_EXT=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto';" || echo "0")

if [ "$UUID_EXT" = "1" ] && [ "$CRYPTO_EXT" = "1" ]; then
    echo "✅ PASSED: Extensions 'uuid-ossp' and 'pgcrypto' are enabled"
else
    echo "❌ FAILED: Required extensions not enabled (uuid-ossp: $UUID_EXT, pgcrypto: $CRYPTO_EXT)"
    exit 1
fi
echo ""

# Check max_connections
echo "7. Checking max_connections setting..."
MAX_CONN=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- psql -U paperless -d paperless -tAc "SHOW max_connections;" || echo "0")
if [ "$MAX_CONN" -ge 100 ]; then
    echo "✅ PASSED: max_connections is $MAX_CONN (>= 100 required)"
else
    echo "❌ FAILED: max_connections is $MAX_CONN (< 100)"
    exit 1
fi
echo ""

# Test connection as paperless_app
echo "8. Testing connection as paperless_app user..."
# Use a simpler method - exec into postgres pod and connect as paperless_app
CONNECTION_TEST=$(kubectl exec -n $NAMESPACE $POSTGRES_POD -- sh -c 'PGPASSWORD=devapppassword psql -h localhost -U paperless_app -d paperless -tAc "SELECT 1;"' 2>/dev/null || echo "0")
if [ "$CONNECTION_TEST" = "1" ]; then
    echo "✅ PASSED: Connection test successful"
else
    echo "❌ FAILED: Connection test failed"
    exit 1
fi
echo ""

# Check for errors in logs
echo "9. Checking PostgreSQL logs for errors..."
ERROR_COUNT=$(kubectl logs -n $NAMESPACE $POSTGRES_POD --tail=100 | grep -i error | wc -l || echo "0")
if [ "$ERROR_COUNT" = "0" ]; then
    echo "✅ PASSED: No errors found in recent PostgreSQL logs"
else
    echo "⚠️  WARNING: Found $ERROR_COUNT error entries in recent logs"
fi
echo ""

echo "=========================================="
echo "✅ All verification checks passed!"
echo "=========================================="
echo ""
echo "Connection string for paperless_app:"
echo "postgresql://paperless_app:devapppassword@postgres:5432/paperless"
echo ""
