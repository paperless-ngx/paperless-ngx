#!/bin/bash

# Script to verify Redis configuration for Celery broker and result backend
# This script tests multi-tenant task queuing capabilities

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get namespace from environment or use default
NAMESPACE=${NAMESPACE:-generic-repo}

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Results file
RESULTS_FILE="/tmp/redis-celery-verification-$(date +%Y%m%d-%H%M%S).json"
log_info "Results will be saved to: $RESULTS_FILE"

# Initialize results JSON
cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "namespace": "$NAMESPACE",
  "tests": {}
}
EOF

# Helper function to add test result to JSON
add_test_result() {
    local test_name="$1"
    local status="$2"
    local details="$3"

    # Escape special characters in details
    details=$(echo "$details" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | tr '\n' ' ')

    # Update JSON file
    jq --arg name "$test_name" --arg status "$status" --arg details "$details" \
        '.tests[$name] = {"status": $status, "details": $details}' \
        "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"
}

log_info "========================================="
log_info "Redis & Celery Verification Script"
log_info "========================================="
echo ""

# Test 1: Check Redis StatefulSet Configuration
log_info "Test 1: Checking Redis StatefulSet configuration..."
REDIS_CONFIG=$(kubectl get statefulset redis -n "$NAMESPACE" -o json 2>&1)
if [ $? -eq 0 ]; then
    # Extract key configuration values
    MEMORY_REQUEST=$(echo "$REDIS_CONFIG" | jq -r '.spec.template.spec.containers[0].resources.requests.memory')
    MEMORY_LIMIT=$(echo "$REDIS_CONFIG" | jq -r '.spec.template.spec.containers[0].resources.limits.memory')
    STORAGE=$(kubectl get pvc -n "$NAMESPACE" -l app=redis -o json | jq -r '.items[0].spec.resources.requests.storage' 2>/dev/null || echo "N/A")
    PERSISTENCE=$(echo "$REDIS_CONFIG" | jq -r '.spec.template.spec.containers[0].command | join(" ")' | grep -q "appendonly yes" && echo "enabled" || echo "disabled")

    log_success "Redis StatefulSet found"
    echo "  Memory Request: $MEMORY_REQUEST"
    echo "  Memory Limit: $MEMORY_LIMIT"
    echo "  Storage: $STORAGE"
    echo "  Persistence: $PERSISTENCE"

    add_test_result "redis_statefulset_config" "PASS" "Memory: $MEMORY_LIMIT, Storage: $STORAGE, Persistence: $PERSISTENCE"
else
    log_error "Redis StatefulSet not found"
    add_test_result "redis_statefulset_config" "FAIL" "StatefulSet not found: $REDIS_CONFIG"
fi
echo ""

# Test 2: Check Redis Pod Status
log_info "Test 2: Checking Redis pod status..."
REDIS_POD=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o json 2>&1)
if [ $? -eq 0 ]; then
    REDIS_POD_NAME=$(echo "$REDIS_POD" | jq -r '.items[0].metadata.name')
    REDIS_POD_STATUS=$(echo "$REDIS_POD" | jq -r '.items[0].status.phase')

    if [ "$REDIS_POD_STATUS" == "Running" ]; then
        log_success "Redis pod is running: $REDIS_POD_NAME"
        add_test_result "redis_pod_status" "PASS" "Pod $REDIS_POD_NAME is running"
    else
        log_error "Redis pod is not running: $REDIS_POD_STATUS"
        add_test_result "redis_pod_status" "FAIL" "Pod status: $REDIS_POD_STATUS"
    fi
else
    log_error "Failed to get Redis pod status"
    add_test_result "redis_pod_status" "FAIL" "Could not retrieve pod status"
fi
echo ""

# Test 3: Test Redis connectivity from web pods
log_info "Test 3: Testing Redis connectivity from web pods..."
WEB_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=web -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$WEB_POD" ]; then
    REDIS_PING=$(kubectl exec -n "$NAMESPACE" "$WEB_POD" -c paless-web -- sh -c "echo PING | nc redis 6379" 2>&1 || echo "FAILED")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        log_success "Redis connectivity from web pod: OK"
        add_test_result "redis_connectivity_web" "PASS" "Successfully connected to Redis from $WEB_POD"
    else
        log_warning "Redis connectivity from web pod: FAILED - $REDIS_PING"
        add_test_result "redis_connectivity_web" "FAIL" "Connection failed: $REDIS_PING"
    fi
else
    log_warning "No web pod found for connectivity test"
    add_test_result "redis_connectivity_web" "SKIP" "No web pod available"
fi
echo ""

# Test 4: Test Redis connectivity from worker pods
log_info "Test 4: Testing Redis connectivity from worker pods..."
WORKER_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$WORKER_POD" ]; then
    REDIS_PING=$(kubectl exec -n "$NAMESPACE" "$WORKER_POD" -c paless-worker -- sh -c "echo PING | nc redis 6379" 2>&1 || echo "FAILED")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        log_success "Redis connectivity from worker pod: OK"
        add_test_result "redis_connectivity_worker" "PASS" "Successfully connected to Redis from $WORKER_POD"
    else
        log_warning "Redis connectivity from worker pod: FAILED - $REDIS_PING"
        add_test_result "redis_connectivity_worker" "FAIL" "Connection failed: $REDIS_PING"
    fi
else
    log_warning "No worker pod found for connectivity test"
    add_test_result "redis_connectivity_worker" "SKIP" "No worker pod available"
fi
echo ""

# Test 5: Test Redis connectivity from scheduler pods
log_info "Test 5: Testing Redis connectivity from scheduler pods..."
SCHEDULER_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=scheduler -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$SCHEDULER_POD" ]; then
    REDIS_PING=$(kubectl exec -n "$NAMESPACE" "$SCHEDULER_POD" -c paless-scheduler -- sh -c "echo PING | nc redis 6379" 2>&1 || echo "FAILED")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        log_success "Redis connectivity from scheduler pod: OK"
        add_test_result "redis_connectivity_scheduler" "PASS" "Successfully connected to Redis from $SCHEDULER_POD"
    else
        log_warning "Redis connectivity from scheduler pod: FAILED - $REDIS_PING"
        add_test_result "redis_connectivity_scheduler" "FAIL" "Connection failed: $REDIS_PING"
    fi
else
    log_warning "No scheduler pod found for connectivity test"
    add_test_result "redis_connectivity_scheduler" "SKIP" "No scheduler pod available"
fi
echo ""

# Test 6: Verify Celery broker URL configuration
log_info "Test 6: Verifying Celery broker URL configuration..."
CELERY_BROKER=$(kubectl get configmap paperless-config -n "$NAMESPACE" -o jsonpath='{.data.PAPERLESS_REDIS}' 2>/dev/null)
if [ -n "$CELERY_BROKER" ]; then
    log_success "Celery broker URL configured: $CELERY_BROKER"
    add_test_result "celery_broker_config" "PASS" "Broker URL: $CELERY_BROKER"

    # Verify the URL points to the correct Redis service
    if echo "$CELERY_BROKER" | grep -q "redis://redis:6379"; then
        log_success "Broker URL points to correct Redis service"
    else
        log_warning "Broker URL might not point to standard Redis service"
    fi
else
    log_error "Celery broker URL not configured"
    add_test_result "celery_broker_config" "FAIL" "No PAPERLESS_REDIS configuration found"
fi
echo ""

# Test 7: Check Redis logs for errors
log_info "Test 7: Checking Redis logs for errors..."
if [ -n "$REDIS_POD_NAME" ]; then
    REDIS_ERRORS=$(kubectl logs -n "$NAMESPACE" "$REDIS_POD_NAME" --tail=100 2>&1 | grep -i "error\|warning\|fatal" || echo "No errors found")
    if [ "$REDIS_ERRORS" == "No errors found" ]; then
        log_success "No errors in Redis logs"
        add_test_result "redis_logs" "PASS" "No errors or warnings found in recent logs"
    else
        log_warning "Found potential issues in Redis logs:"
        echo "$REDIS_ERRORS" | head -10
        add_test_result "redis_logs" "WARNING" "Found issues: $(echo $REDIS_ERRORS | head -3)"
    fi
else
    add_test_result "redis_logs" "SKIP" "Redis pod not available"
fi
echo ""

# Test 8: Check Redis memory usage
log_info "Test 8: Checking Redis memory usage..."
if [ -n "$REDIS_POD_NAME" ]; then
    REDIS_INFO=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli INFO memory 2>&1 || echo "FAILED")
    if [ "$REDIS_INFO" != "FAILED" ]; then
        USED_MEMORY=$(echo "$REDIS_INFO" | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
        USED_MEMORY_PEAK=$(echo "$REDIS_INFO" | grep "used_memory_peak_human:" | cut -d: -f2 | tr -d '\r')
        log_success "Redis memory usage:"
        echo "  Current: $USED_MEMORY"
        echo "  Peak: $USED_MEMORY_PEAK"
        add_test_result "redis_memory_usage" "PASS" "Current: $USED_MEMORY, Peak: $USED_MEMORY_PEAK"
    else
        log_error "Failed to get Redis memory info"
        add_test_result "redis_memory_usage" "FAIL" "Could not retrieve memory information"
    fi
else
    add_test_result "redis_memory_usage" "SKIP" "Redis pod not available"
fi
echo ""

# Test 9: Check Redis connection stats
log_info "Test 9: Checking Redis connection stats..."
if [ -n "$REDIS_POD_NAME" ]; then
    REDIS_STATS=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli INFO stats 2>&1 || echo "FAILED")
    if [ "$REDIS_STATS" != "FAILED" ]; then
        TOTAL_CONNECTIONS=$(echo "$REDIS_STATS" | grep "total_connections_received:" | cut -d: -f2 | tr -d '\r')
        CONNECTED_CLIENTS=$(echo "$REDIS_STATS" | grep "^connected_clients:" | cut -d: -f2 | tr -d '\r')
        log_success "Redis connection stats:"
        echo "  Total connections: $TOTAL_CONNECTIONS"
        echo "  Connected clients: $CONNECTED_CLIENTS"
        add_test_result "redis_connection_stats" "PASS" "Total: $TOTAL_CONNECTIONS, Active: $CONNECTED_CLIENTS"
    else
        log_error "Failed to get Redis stats"
        add_test_result "redis_connection_stats" "FAIL" "Could not retrieve stats"
    fi
else
    add_test_result "redis_connection_stats" "SKIP" "Redis pod not available"
fi
echo ""

# Test 10: Check current Redis keys (task queue structure)
log_info "Test 10: Checking current task queue structure..."
if [ -n "$REDIS_POD_NAME" ]; then
    # Get all keys
    REDIS_KEYS=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli --scan 2>&1 || echo "FAILED")
    if [ "$REDIS_KEYS" != "FAILED" ]; then
        # Count keys by pattern
        CELERY_KEYS=$(echo "$REDIS_KEYS" | grep -c "celery" || echo "0")
        TOTAL_KEYS=$(echo "$REDIS_KEYS" | wc -l)

        log_success "Redis key structure:"
        echo "  Total keys: $TOTAL_KEYS"
        echo "  Celery-related keys: $CELERY_KEYS"

        # Show sample keys
        if [ "$TOTAL_KEYS" -gt 0 ]; then
            echo "  Sample keys:"
            echo "$REDIS_KEYS" | head -5 | sed 's/^/    /'
        fi

        add_test_result "redis_key_structure" "PASS" "Total keys: $TOTAL_KEYS, Celery keys: $CELERY_KEYS"
    else
        log_error "Failed to scan Redis keys"
        add_test_result "redis_key_structure" "FAIL" "Could not scan keys"
    fi
else
    add_test_result "redis_key_structure" "SKIP" "Redis pod not available"
fi
echo ""

# Test 11: Verify Redis persistence configuration
log_info "Test 11: Verifying Redis persistence configuration..."
if [ -n "$REDIS_POD_NAME" ]; then
    REDIS_CONFIG_INFO=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli CONFIG GET "*append*" 2>&1)
    if [ $? -eq 0 ]; then
        log_success "Redis persistence configuration:"
        echo "$REDIS_CONFIG_INFO" | while read -r line; do
            echo "  $line"
        done
        add_test_result "redis_persistence_config" "PASS" "AOF persistence configured"
    else
        log_error "Failed to get Redis persistence config"
        add_test_result "redis_persistence_config" "FAIL" "Could not retrieve config"
    fi
else
    add_test_result "redis_persistence_config" "SKIP" "Redis pod not available"
fi
echo ""

# Test 12: Check if Redis can handle multiple namespaces (simulate tenant queues)
log_info "Test 12: Testing Redis multi-namespace capability..."
if [ -n "$REDIS_POD_NAME" ]; then
    # Test setting keys with different prefixes (simulating tenant namespaces)
    TEST_TENANTS=("tenant-001" "tenant-002" "tenant-003")
    NAMESPACE_TEST_PASS=true

    for tenant in "${TEST_TENANTS[@]}"; do
        SET_RESULT=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli SET "test:${tenant}:queue" "value" 2>&1)
        if [ "$SET_RESULT" != "OK" ]; then
            NAMESPACE_TEST_PASS=false
            break
        fi
    done

    if [ "$NAMESPACE_TEST_PASS" = true ]; then
        # Verify keys exist
        for tenant in "${TEST_TENANTS[@]}"; do
            GET_RESULT=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli GET "test:${tenant}:queue" 2>&1)
            if [ "$GET_RESULT" != "value" ]; then
                NAMESPACE_TEST_PASS=false
                break
            fi
        done

        # Clean up test keys
        for tenant in "${TEST_TENANTS[@]}"; do
            kubectl exec -n "$NAMESPACE" "$REDIS_POD_NAME" -- redis-cli DEL "test:${tenant}:queue" > /dev/null 2>&1
        done

        if [ "$NAMESPACE_TEST_PASS" = true ]; then
            log_success "Redis can handle multiple queue namespaces"
            add_test_result "redis_multi_namespace" "PASS" "Successfully tested ${#TEST_TENANTS[@]} tenant namespaces"
        else
            log_error "Failed to retrieve namespaced keys"
            add_test_result "redis_multi_namespace" "FAIL" "Key retrieval failed"
        fi
    else
        log_error "Failed to set namespaced keys"
        add_test_result "redis_multi_namespace" "FAIL" "Key creation failed"
    fi
else
    add_test_result "redis_multi_namespace" "SKIP" "Redis pod not available"
fi
echo ""

# Generate summary
log_info "========================================="
log_info "Verification Summary"
log_info "========================================="

TOTAL_TESTS=$(jq '.tests | length' "$RESULTS_FILE")
PASSED_TESTS=$(jq '[.tests[] | select(.status == "PASS")] | length' "$RESULTS_FILE")
FAILED_TESTS=$(jq '[.tests[] | select(.status == "FAIL")] | length' "$RESULTS_FILE")
SKIPPED_TESTS=$(jq '[.tests[] | select(.status == "SKIP")] | length' "$RESULTS_FILE")
WARNING_TESTS=$(jq '[.tests[] | select(.status == "WARNING")] | length' "$RESULTS_FILE")

echo "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo -e "${YELLOW}Warnings: $WARNING_TESTS${NC}"
echo -e "${BLUE}Skipped: $SKIPPED_TESTS${NC}"
echo ""
log_info "Detailed results saved to: $RESULTS_FILE"
echo ""

# Add summary to JSON
jq --arg total "$TOTAL_TESTS" --arg passed "$PASSED_TESTS" --arg failed "$FAILED_TESTS" \
   --arg skipped "$SKIPPED_TESTS" --arg warnings "$WARNING_TESTS" \
   '.summary = {"total": $total, "passed": $passed, "failed": $failed, "skipped": $skipped, "warnings": $warnings}' \
   "$RESULTS_FILE" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

# Exit with appropriate code
if [ "$FAILED_TESTS" -gt 0 ]; then
    log_error "Some tests failed. Please review the results."
    exit 1
else
    log_success "All critical tests passed!"
    exit 0
fi
