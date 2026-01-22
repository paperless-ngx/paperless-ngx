#!/bin/bash
# ============================================================================
# Paless Development Environment Manager
# ============================================================================
# Simplified wrapper for Docker Compose development workflow
# Usage: ./dev-env.sh {up|down|logs|ps|clean|rebuild|help}
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env.dev"
MAX_WAIT=120  # 2 minutes for health checks

# Helper functions
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check if required files exist
check_requirements() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file not found: $ENV_FILE"
        print_info "Using default environment variables from docker-compose.dev.yml"
    fi

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
}

# Start services
cmd_up() {
    print_header "Starting Paless Development Environment"

    check_requirements

    print_info "Building base image (paless:latest)..."
    docker build -t localhost:5000/paless:latest -f Dockerfile .

    if [ $? -ne 0 ]; then
        print_error "Failed to build base image"
        exit 1
    fi

    print_success "Base image built successfully"
    echo ""

    print_info "Building and starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up --build -d

    if [ $? -ne 0 ]; then
        print_error "Failed to start services"
        exit 1
    fi

    print_success "Services started successfully"
    echo ""

    print_info "Waiting for health checks (max ${MAX_WAIT}s)..."
    local elapsed=0
    local interval=5

    while [ $elapsed -lt $MAX_WAIT ]; do
        local unhealthy=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format json 2>/dev/null | \
            jq -r '.[] | select(.Health != "healthy" and .Health != "") | .Name' 2>/dev/null || echo "")

        local starting=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format json 2>/dev/null | \
            jq -r '.[] | select(.State == "running" and .Health == "") | .Name' 2>/dev/null || echo "")

        if [ -z "$unhealthy" ] && [ -z "$starting" ]; then
            echo ""
            print_success "All services healthy!"
            echo ""
            cmd_ps
            echo ""
            print_info "Development environment ready:"
            echo "  📱 Web UI:        http://localhost:8080"
            echo "  🗄️  MinIO Console: http://localhost:8001"
            echo "  🗃️  PostgreSQL:    localhost:8432"
            echo "  📮 Redis:         localhost:8379"
            echo ""
            print_info "Next steps:"
            echo "  • Browser test:   npx playwright screenshot http://localhost:8080 screenshots/test.png"
            echo "  • View logs:      ./dev-env.sh logs"
            echo "  • Stop services:  ./dev-env.sh down"
            return 0
        fi

        echo -n "."
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    echo ""
    print_warning "Timeout waiting for health checks"
    print_info "Current service status:"
    cmd_ps
    echo ""
    print_info "Check logs for issues: ./dev-env.sh logs"
    exit 1
}

# Stop services
cmd_down() {
    print_header "Stopping Paless Development Environment"

    print_info "Stopping services (keeping data)..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down

    if [ $? -eq 0 ]; then
        print_success "Services stopped successfully"
        print_info "Data volumes preserved. Use './dev-env.sh clean' to remove all data."
    else
        print_error "Failed to stop services"
        exit 1
    fi
}

# View logs
cmd_logs() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        print_header "Viewing All Service Logs"
        print_info "Press Ctrl+C to stop following logs"
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
    else
        print_header "Viewing Logs for: $service"
        print_info "Press Ctrl+C to stop following logs"
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service"
    fi
}

# Show service status
cmd_ps() {
    print_header "Service Status"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

# Clean all data
cmd_clean() {
    print_header "Clean Slate - Remove All Data"

    print_warning "This will PERMANENTLY DELETE all data volumes!"
    print_warning "This includes: database, uploaded documents, redis cache, minio storage"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "Clean operation cancelled"
        return 0
    fi

    echo ""
    print_info "Stopping services and removing volumes..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v

    if [ $? -eq 0 ]; then
        print_success "All services stopped and data volumes removed"
        print_info "Run './dev-env.sh up' to start fresh"
    else
        print_error "Failed to clean environment"
        exit 1
    fi
}

# Rebuild images
cmd_rebuild() {
    print_header "Rebuilding Images"

    print_info "Stopping services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down

    print_info "Rebuilding base image without cache..."
    docker build --no-cache -t localhost:5000/paless:latest -f Dockerfile .

    if [ $? -ne 0 ]; then
        print_error "Failed to rebuild base image"
        exit 1
    fi

    print_info "Rebuilding service images without cache..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache

    if [ $? -eq 0 ]; then
        print_success "Images rebuilt successfully"
        print_info "Run './dev-env.sh up' to start services"
    else
        print_error "Failed to rebuild images"
        exit 1
    fi
}

# Show help
cmd_help() {
    print_header "Paless Development Environment Manager"
    echo ""
    echo "Usage: ./dev-env.sh {command} [options]"
    echo ""
    echo "Commands:"
    echo "  up        Start all services (builds images if needed)"
    echo "  down      Stop all services (keeps data)"
    echo "  logs      View logs (optional: specify service name)"
    echo "  ps        Show service status"
    echo "  clean     Stop services and remove all data volumes"
    echo "  rebuild   Rebuild all images without cache"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./dev-env.sh up                  # Start environment"
    echo "  ./dev-env.sh logs paless-web     # View web service logs"
    echo "  ./dev-env.sh ps                  # Check service status"
    echo "  ./dev-env.sh down                # Stop environment"
    echo "  ./dev-env.sh clean               # Fresh start (removes all data)"
    echo ""
    echo "Services:"
    echo "  paless-web       - Web application (port 8080)"
    echo "  paless-worker    - Celery worker"
    echo "  paless-scheduler - Celery beat scheduler"
    echo "  app-postgres     - PostgreSQL database (port 8432)"
    echo "  app-redis        - Redis cache (port 8379)"
    echo "  app-minio        - MinIO S3 storage (ports 8000, 8001)"
    echo ""
}

# Main command router
main() {
    local command="${1:-help}"
    shift || true  # Remove command from arguments

    case "$command" in
        up)
            cmd_up "$@"
            ;;
        down)
            cmd_down "$@"
            ;;
        logs)
            cmd_logs "$@"
            ;;
        ps|status)
            cmd_ps "$@"
            ;;
        clean)
            cmd_clean "$@"
            ;;
        rebuild)
            cmd_rebuild "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
