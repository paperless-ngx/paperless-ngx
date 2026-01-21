#!/bin/bash
# Verification script for tenant_id implementation
# Run this after deploying to K3s with rebuilt images

set -e

echo "=== Tenant ID Implementation Verification ==="
echo ""

# Check if we're in K3s
if ! kubectl get namespace paless >/dev/null 2>&1; then
    echo "ERROR: Cannot access paless namespace. Make sure K3s is running."
    exit 1
fi

POD=$(kubectl get pods -n paless -l app=paless-scheduler --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD" ]; then
    echo "ERROR: No running paless-scheduler pod found"
    exit 1
fi

echo "Using pod: $POD"
echo ""

echo "1. Checking if migrations were applied..."
MIGRATIONS=$(kubectl exec -n paless "$POD" -c paless-scheduler -- python manage.py showmigrations documents 2>/dev/null | grep -E "(1078|1079|1080)")
if echo "$MIGRATIONS" | grep -q "\[X\] 1078_add_tenant_id_to_models"; then
    echo "   ✓ Migration 1078 (add tenant_id fields) applied"
else
    echo "   ✗ Migration 1078 NOT applied"
    exit 1
fi

if echo "$MIGRATIONS" | grep -q "\[X\] 1079_create_default_tenant_and_backfill"; then
    echo "   ✓ Migration 1079 (create default tenant and backfill) applied"
else
    echo "   ✗ Migration 1079 NOT applied"
    exit 1
fi

if echo "$MIGRATIONS" | grep -q "\[X\] 1080_make_tenant_id_non_nullable"; then
    echo "   ✓ Migration 1080 (make tenant_id non-nullable) applied"
else
    echo "   ✗ Migration 1080 NOT applied"
    exit 1
fi

echo ""
echo "2. Checking if default tenant was created..."
DEFAULT_TENANT=$(kubectl exec -n paless "$POD" -c paless-scheduler -- python manage.py shell -c "from documents.models.tenant import Tenant; t=Tenant.objects.filter(subdomain='default').first(); print('EXISTS' if t else 'NOT_FOUND')" 2>/dev/null | grep -E "EXISTS|NOT_FOUND")

if [ "$DEFAULT_TENANT" = "EXISTS" ]; then
    echo "   ✓ Default tenant exists"
else
    echo "   ✗ Default tenant NOT found"
    exit 1
fi

echo ""
echo "3. Checking database schema for tenant_id columns..."
for table in documents_correspondent documents_tag documents_documenttype documents_storagepath documents_document documents_savedview documents_paperlesstask; do
    HAS_COLUMN=$(kubectl exec -n paless postgres-0 -- psql -U paless -d paless -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='$table' AND column_name='tenant_id';" 2>/dev/null | tr -d ' ')
    if [ "$HAS_COLUMN" = "tenant_id" ]; then
        echo "   ✓ $table has tenant_id column"
    else
        echo "   ✗ $table missing tenant_id column"
        exit 1
    fi
done

echo ""
echo "4. Checking if existing records have tenant_id values..."
for table in documents_correspondent documents_tag documents_documenttype documents_storagepath documents_document documents_savedview documents_paperlesstask; do
    NULL_COUNT=$(kubectl exec -n paless postgres-0 -- psql -U paless -d paless -t -c "SELECT COUNT(*) FROM $table WHERE tenant_id IS NULL;" 2>/dev/null | tr -d ' ')
    if [ "$NULL_COUNT" = "0" ]; then
        echo "   ✓ All records in $table have tenant_id"
    else
        echo "   ✗ $table has $NULL_COUNT records with NULL tenant_id"
        exit 1
    fi
done

echo ""
echo "5. Testing thread-local storage functions..."
kubectl exec -n paless "$POD" -c paless-scheduler -- python manage.py shell <<'EOF' >/dev/null 2>&1
import uuid
from documents.models import set_current_tenant_id, get_current_tenant_id

# Test set and get
test_id = uuid.uuid4()
set_current_tenant_id(test_id)
assert get_current_tenant_id() == test_id, "Thread-local storage failed"

# Test clear
set_current_tenant_id(None)
assert get_current_tenant_id() is None, "Thread-local clear failed"

print("Thread-local functions working correctly")
EOF

if [ $? -eq 0 ]; then
    echo "   ✓ Thread-local storage functions work correctly"
else
    echo "   ✗ Thread-local storage functions failed"
    exit 1
fi

echo ""
echo "6. Testing auto-population of tenant_id on save..."
kubectl exec -n paless "$POD" -c paless-scheduler -- python manage.py shell <<'EOF' >/dev/null 2>&1
from documents.models import Correspondent, set_current_tenant_id
from documents.models.tenant import Tenant
from django.contrib.auth.models import User

# Get or create a tenant
tenant = Tenant.objects.filter(subdomain='default').first()
if not tenant:
    raise Exception("Default tenant not found")

# Set current tenant
set_current_tenant_id(tenant.id)

# Create a test correspondent
user = User.objects.first()
correspondent = Correspondent(name='Test Auto Populate', owner=user)
correspondent.save()

# Verify tenant_id was auto-populated
assert correspondent.tenant_id == tenant.id, "tenant_id was not auto-populated"

# Clean up
correspondent.delete()
print("Auto-population test passed")
EOF

if [ $? -eq 0 ]; then
    echo "   ✓ tenant_id auto-population works"
else
    echo "   ✗ tenant_id auto-population failed"
    exit 1
fi

echo ""
echo "7. Testing ValueError when tenant_id is missing..."
kubectl exec -n paless "$POD" -c paless-scheduler -- python manage.py shell <<'EOF' >/dev/null 2>&1
from documents.models import Correspondent, set_current_tenant_id
from django.contrib.auth.models import User

# Clear thread-local
set_current_tenant_id(None)

# Try to save without tenant_id
user = User.objects.first()
correspondent = Correspondent(name='Test Error', owner=user)

try:
    correspondent.save()
    raise Exception("Should have raised ValueError")
except ValueError as e:
    if "tenant_id cannot be None" not in str(e):
        raise Exception(f"Wrong error message: {e}")
    print("ValueError raised correctly")
EOF

if [ $? -eq 0 ]; then
    echo "   ✓ ValueError raised when tenant_id missing"
else
    echo "   ✗ ValueError test failed"
    exit 1
fi

echo ""
echo "8. Checking database indexes..."
for table in documents_correspondent documents_tag documents_documenttype documents_storagepath documents_document documents_savedview documents_paperlesstask; do
    INDEX_COUNT=$(kubectl exec -n paless postgres-0 -- psql -U paless -d paless -t -c "SELECT COUNT(*) FROM pg_indexes WHERE tablename='$table' AND indexdef LIKE '%tenant_id%';" 2>/dev/null | tr -d ' ')
    if [ "$INDEX_COUNT" -ge "1" ]; then
        echo "   ✓ $table has tenant_id index(es)"
    else
        echo "   ✗ $table missing tenant_id indexes"
        exit 1
    fi
done

echo ""
echo "=== All Verification Checks Passed! ==="
echo ""
echo "Summary:"
echo "  - ModelWithOwner updated with tenant_id field"
echo "  - Thread-local helper functions working"
echo "  - Migrations applied successfully"
echo "  - Default tenant created"
echo "  - All existing records have tenant_id"
echo "  - Database indexes created"
echo "  - Auto-population working"
echo "  - ValueError raised when tenant_id missing"
echo ""
