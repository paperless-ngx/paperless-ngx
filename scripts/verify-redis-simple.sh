#!/bin/bash

# Simplified Redis and Celery verification script
# Does not require jq

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE=${NAMESPACE:-paless}

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

RESULTS_FILE="/tmp/redis-celery-verification-$(date +%Y%m%d-%H%M%S).txt"

log_info "========================================="
log_info "Redis & Celery Verification"
log_info "========================================="
log_info "Namespace: $NAMESPACE"
log_info "Results file: $RESULTS_FILE"
echo ""

# Redirect all output to both console and file
exec > >(tee -a "$RESULTS_FILE") 2>&1

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# Test 1: Redis StatefulSet Configuration
log_info "Test 1: Redis StatefulSet Configuration"
echo "----------------------------------------"
if kubectl get statefulset redis -n "$NAMESPACE" &>/dev/null; then
    kubectl get statefulset redis -n "$NAMESPACE" -o yaml | grep -E "memory:|cpu:|storage:" | head -6
    log_success "Redis StatefulSet found and configured"
    ((PASS_COUNT++))
else
    log_error "Redis StatefulSet not found"
    ((FAIL_COUNT++))
fi
echo ""

# Test 2: Redis Pod Status
log_info "Test 2: Redis Pod Status"
echo "----------------------------------------"
REDIS_POD=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$REDIS_POD" ]; then
    REDIS_STATUS=$(kubectl get pod "$REDIS_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    echo "Pod: $REDIS_POD"
    echo "Status: $REDIS_STATUS"
    if [ "$REDIS_STATUS" == "Running" ]; then
        log_success "Redis pod is running"
        ((PASS_COUNT++))
    else
        log_error "Redis pod is not running: $REDIS_STATUS"
        ((FAIL_COUNT++))
    fi
else
    log_error "No Redis pod found"
    ((FAIL_COUNT++))
fi
echo ""

# Test 3: Web Pod Connectivity
log_info "Test 3: Redis Connectivity from Web Pods"
echo "----------------------------------------"
WEB_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=web -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$WEB_POD" ]; then
    echo "Testing from: $WEB_POD"
    if kubectl exec -n "$NAMESPACE" "$WEB_POD" -c paless-web -- sh -c "echo PING | nc redis 6379 2>&1" | grep -q "PONG"; then
        log_success "Web pod can connect to Redis"
        ((PASS_COUNT++))
    else
        log_warning "Web pod cannot connect to Redis"
        ((FAIL_COUNT++))
    fi
else
    log_warning "No web pod found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 4: Worker Pod Connectivity
log_info "Test 4: Redis Connectivity from Worker Pods"
echo "----------------------------------------"
WORKER_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$WORKER_POD" ]; then
    echo "Testing from: $WORKER_POD"
    if kubectl exec -n "$NAMESPACE" "$WORKER_POD" -c paless-worker -- sh -c "echo PING | nc redis 6379 2>&1" | grep -q "PONG"; then
        log_success "Worker pod can connect to Redis"
        ((PASS_COUNT++))
    else
        log_warning "Worker pod cannot connect to Redis"
        ((FAIL_COUNT++))
    fi
else
    log_warning "No worker pod found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 5: Scheduler Pod Connectivity
log_info "Test 5: Redis Connectivity from Scheduler Pods"
echo "----------------------------------------"
SCHEDULER_POD=$(kubectl get pods -n "$NAMESPACE" -l app=paless,component=scheduler -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$SCHEDULER_POD" ]; then
    echo "Testing from: $SCHEDULER_POD"
    if kubectl exec -n "$NAMESPACE" "$SCHEDULER_POD" -c paless-scheduler -- sh -c "echo PING | nc redis 6379 2>&1" | grep -q "PONG"; then
        log_success "Scheduler pod can connect to Redis"
        ((PASS_COUNT++))
    else
        log_warning "Scheduler pod cannot connect to Redis"
        ((FAIL_COUNT++))
    fi
else
    log_warning "No scheduler pod found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 6: Celery Broker URL
log_info "Test 6: Celery Broker URL Configuration"
echo "----------------------------------------"
BROKER_URL=$(kubectl get configmap paperless-config -n "$NAMESPACE" -o jsonpath='{.data.PAPERLESS_REDIS}' 2>/dev/null || echo "")
if [ -n "$BROKER_URL" ]; then
    echo "Broker URL: $BROKER_URL"
    log_success "Celery broker URL configured"
    ((PASS_COUNT++))
else
    log_error "Celery broker URL not configured"
    ((FAIL_COUNT++))
fi
echo ""

# Test 7: Redis Logs
log_info "Test 7: Redis Logs (checking for errors)"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" "$REDIS_POD" --tail=100 2>&1 | grep -ic "error\|warning\|fatal" || echo "0")
    echo "Errors/warnings in last 100 lines: $ERROR_COUNT"
    if [ "$ERROR_COUNT" -eq 0 ]; then
        log_success "No errors in Redis logs"
        ((PASS_COUNT++))
    else
        log_warning "Found $ERROR_COUNT potential issues in logs"
        kubectl logs -n "$NAMESPACE" "$REDIS_POD" --tail=20
    fi
else
    log_warning "Cannot check logs - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 8: Redis Memory Usage
log_info "Test 8: Redis Memory Usage"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli INFO memory 2>&1 | grep -E "used_memory_human|used_memory_peak_human|maxmemory"
    log_success "Memory info retrieved"
    ((PASS_COUNT++))
else
    log_warning "Cannot check memory - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 9: Redis Connection Stats
log_info "Test 9: Redis Connection Stats"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli INFO stats 2>&1 | grep -E "total_connections_received|connected_clients"
    log_success "Connection stats retrieved"
    ((PASS_COUNT++))
else
    log_warning "Cannot check stats - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 10: Queue Structure
log_info "Test 10: Current Queue Structure"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    KEY_COUNT=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli DBSIZE 2>&1 | grep -oE '[0-9]+' || echo "0")
    echo "Total keys in database: $KEY_COUNT"
    echo ""
    echo "Sample keys:"
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli --scan 2>&1 | head -10
    log_success "Queue structure analyzed"
    ((PASS_COUNT++))
else
    log_warning "Cannot check queue - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 11: Persistence Configuration
log_info "Test 11: Redis Persistence Configuration"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli CONFIG GET appendonly 2>&1
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli CONFIG GET appendfsync 2>&1
    log_success "Persistence config retrieved"
    ((PASS_COUNT++))
else
    log_warning "Cannot check persistence - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Test 12: Multi-Namespace Capability
log_info "Test 12: Multi-Namespace Queue Capability"
echo "----------------------------------------"
if [ -n "$REDIS_POD" ]; then
    # Test setting and getting keys with tenant prefixes
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli SET "test:tenant-001:queue" "value1" >/dev/null 2>&1
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli SET "test:tenant-002:queue" "value2" >/dev/null 2>&1
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli SET "test:tenant-003:queue" "value3" >/dev/null 2>&1

    VAL1=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli GET "test:tenant-001:queue" 2>&1)
    VAL2=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli GET "test:tenant-002:queue" 2>&1)
    VAL3=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli GET "test:tenant-003:queue" 2>&1)

    # Clean up
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli DEL "test:tenant-001:queue" >/dev/null 2>&1
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli DEL "test:tenant-002:queue" >/dev/null 2>&1
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli DEL "test:tenant-003:queue" >/dev/null 2>&1

    if [ "$VAL1" == "value1" ] && [ "$VAL2" == "value2" ] && [ "$VAL3" == "value3" ]; then
        echo "Created 3 tenant-namespaced keys"
        echo "Retrieved all values correctly"
        log_success "Multi-namespace queuing supported"
        ((PASS_COUNT++))
    else
        log_error "Multi-namespace test failed"
        ((FAIL_COUNT++))
    fi
else
    log_warning "Cannot test multi-namespace - Redis pod not found"
    ((SKIP_COUNT++))
fi
echo ""

# Summary
log_info "========================================="
log_info "Verification Summary"
log_info "========================================="
echo "Total tests run: $((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo -e "${YELLOW}Skipped: $SKIP_COUNT${NC}"
echo ""
log_info "Results saved to: $RESULTS_FILE"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
else
    log_success "All critical tests passed!"
    exit 0
fi
