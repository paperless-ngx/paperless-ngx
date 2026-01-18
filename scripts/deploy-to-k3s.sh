#!/bin/bash
set -e

# K3s Deployment Helper Script
# Auto-detects apps from Dockerfiles and deploys to K3s

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source .env from .context-management if it exists
if [ -f "$PROJECT_ROOT/.context-management/.env" ]; then
    source "$PROJECT_ROOT/.context-management/.env"
fi

REGISTRY="${REGISTRY:-localhost:5000}"
PROJECT_NAME="${PROJECT_NAME:-app}"
K8S_NAMESPACE=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
OVERLAY="${OVERLAY:-dev}"

# Parse arguments
TARGET="${1:-all}"

# Find all Dockerfiles and extract app names
find_apps() {
    local apps=()
    while IFS= read -r dockerfile; do
        local dir=$(dirname "$dockerfile")
        local app_name=$(basename "$dir")
        if [ "$dir" != "$PROJECT_ROOT" ]; then
            apps+=("$app_name")
        fi
    done < <(find "$PROJECT_ROOT" -maxdepth 2 -name "Dockerfile" -type f 2>/dev/null | grep -v node_modules | grep -v .context-management)
    echo "${apps[@]}"
}

build_and_push() {
    local app_name=$1
    local app_dir="$PROJECT_ROOT/$app_name"
    local image_name="${PROJECT_NAME}-${app_name}"

    if [ ! -f "$app_dir/Dockerfile" ]; then
        echo -e "${RED}[ERROR]${NC} No Dockerfile found in $app_dir"
        return 1
    fi

    echo -e "${YELLOW}[BUILD]${NC} Building $image_name..."
    docker build -t "$image_name:latest" "$app_dir"
    echo -e "  ${GREEN}✓${NC} Image built: $image_name:latest"

    echo -e "${YELLOW}[PUSH]${NC} Pushing to registry..."
    docker tag "$image_name:latest" "$REGISTRY/$image_name:latest"
    docker push "$REGISTRY/$image_name:latest"
    echo -e "  ${GREEN}✓${NC} Pushed to $REGISTRY/$image_name:latest"
}

deploy() {
    local overlay_dir="$PROJECT_ROOT/k8s/overlays/$OVERLAY"

    if [ ! -d "$overlay_dir" ]; then
        echo -e "${RED}[ERROR]${NC} K8s overlay not found: $overlay_dir"
        echo "Run init_repo.sh first to create k8s/ structure"
        return 1
    fi

    echo -e "${YELLOW}[DEPLOY]${NC} Applying to K3s ($OVERLAY)..."
    kubectl apply -k "$overlay_dir"
    echo -e "  ${GREEN}✓${NC} Applied kustomize overlay"
}

wait_for_pods() {
    local app_label=$1
    echo -e "${YELLOW}[VERIFY]${NC} Waiting for $app_label pods..."

    if kubectl wait --for=condition=ready pod \
        -l "app=$app_label" \
        -n "$K8S_NAMESPACE" \
        --timeout=120s 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Pods running"
    else
        echo -e "  ${RED}✗${NC} Pods not ready. Checking status..."
        kubectl get pods -n "$K8S_NAMESPACE" -l "app=$app_label"
        echo ""
        echo "Recent events:"
        kubectl get events -n "$K8S_NAMESPACE" --sort-by='.lastTimestamp' | tail -10
        return 1
    fi
}

show_status() {
    echo -e "\n${GREEN}[STATUS]${NC} Current pods in $K8S_NAMESPACE:"
    kubectl get pods -n "$K8S_NAMESPACE" -o wide 2>/dev/null || echo "  No pods found"
}

usage() {
    echo "Usage: $0 [app-name|all|status]"
    echo ""
    echo "Available apps (auto-detected from Dockerfiles):"
    local apps=($(find_apps))
    if [ ${#apps[@]} -eq 0 ]; then
        echo "  (none found - create Dockerfile in subdirectory)"
    else
        for app in "${apps[@]}"; do
            echo "  - $app"
        done
    fi
    echo ""
    echo "Options:"
    echo "  all     Build and deploy all detected apps"
    echo "  status  Show current pod status"
    echo ""
    echo "Environment:"
    echo "  PROJECT_NAME=$PROJECT_NAME"
    echo "  REGISTRY=$REGISTRY"
    echo "  K8S_NAMESPACE=$K8S_NAMESPACE"
    echo "  OVERLAY=$OVERLAY"
}

# Main
cd "$PROJECT_ROOT"

case "$TARGET" in
    -h|--help|help)
        usage
        exit 0
        ;;
    status)
        show_status
        exit 0
        ;;
    all)
        apps=($(find_apps))
        if [ ${#apps[@]} -eq 0 ]; then
            echo -e "${RED}[ERROR]${NC} No apps found. Create Dockerfile in a subdirectory."
            exit 1
        fi
        for app in "${apps[@]}"; do
            build_and_push "$app"
        done
        deploy
        for app in "${apps[@]}"; do
            wait_for_pods "$app" || true
        done
        ;;
    *)
        build_and_push "$TARGET"
        deploy
        wait_for_pods "$TARGET"
        ;;
esac

echo -e "\n${GREEN}[DONE]${NC} Deployment complete!"
show_status
echo ""
echo "Useful commands:"
echo "  kubectl logs -n $K8S_NAMESPACE -l app=$TARGET"
echo "  kubectl describe pods -n $K8S_NAMESPACE"
