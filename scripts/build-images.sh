#!/bin/bash
set -e

# Build script for paperless-ngx split containers
# Creates web, worker, and scheduler images

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
REGISTRY="${REGISTRY:-localhost:5000}"
VERSION="${VERSION:-v2}"

echo -e "${GREEN}=== Paperless-ngx Split Container Build ===${NC}"
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo ""

cd "$PROJECT_ROOT"

# Build web image
echo -e "${YELLOW}[1/3]${NC} Building web image..."
docker build -f Dockerfile.web -t "paless-web:$VERSION" .
docker tag "paless-web:$VERSION" "$REGISTRY/paless-web:$VERSION"
echo -e "  ${GREEN}✓${NC} paless-web:$VERSION built"

# Build worker image
echo -e "${YELLOW}[2/3]${NC} Building worker image..."
docker build -f Dockerfile.worker -t "paless-worker:$VERSION" .
docker tag "paless-worker:$VERSION" "$REGISTRY/paless-worker:$VERSION"
echo -e "  ${GREEN}✓${NC} paless-worker:$VERSION built"

# Build scheduler image
echo -e "${YELLOW}[3/3]${NC} Building scheduler image..."
docker build -f Dockerfile.scheduler -t "paless-scheduler:$VERSION" .
docker tag "paless-scheduler:$VERSION" "$REGISTRY/paless-scheduler:$VERSION"
echo -e "  ${GREEN}✓${NC} paless-scheduler:$VERSION built"

echo ""
echo -e "${GREEN}[BUILD COMPLETE]${NC} All images built successfully!"
echo ""
echo "To push images to registry, run:"
echo "  docker push $REGISTRY/paless-web:$VERSION"
echo "  docker push $REGISTRY/paless-worker:$VERSION"
echo "  docker push $REGISTRY/paless-scheduler:$VERSION"
echo ""
echo "Or run with PUSH=true:"
echo "  PUSH=true $0"
echo ""

# Push if requested
if [ "$PUSH" = "true" ]; then
    echo -e "${YELLOW}[PUSH]${NC} Pushing images to registry..."
    docker push "$REGISTRY/paless-web:$VERSION"
    echo -e "  ${GREEN}✓${NC} Pushed paless-web:$VERSION"

    docker push "$REGISTRY/paless-worker:$VERSION"
    echo -e "  ${GREEN}✓${NC} Pushed paless-worker:$VERSION"

    docker push "$REGISTRY/paless-scheduler:$VERSION"
    echo -e "  ${GREEN}✓${NC} Pushed paless-scheduler:$VERSION"

    echo ""
    echo -e "${GREEN}[PUSH COMPLETE]${NC} All images pushed to $REGISTRY!"
fi
