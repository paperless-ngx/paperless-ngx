#!/usr/bin/env bash
# Automates the "General setup" steps from docs/development.md.
# Run from the repo root: bash scripts/setup-dev.sh
#
# Prerequisites (install before running):
#   - Python 3.11+, uv, Node.js 24+, pnpm, Docker
#   - System packages: tesseract-ocr poppler-utils ghostscript unpaper qpdf
#     imagemagick libmagic-dev libpq-dev
#
# This script is meant to run inside a clean container (LXC, VM, etc.)
# where the above are already installed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== paperless-ngx dev setup ==="

# --- Check required commands ---
echo ""
echo "--- Checking prerequisites ---"
MISSING=()
for cmd in python3 uv node pnpm docker tesseract pdftoppm ghostscript; do
    if command -v "$cmd" &>/dev/null; then
        echo "  ✓ $cmd ($(command -v "$cmd"))"
    else
        MISSING+=("$cmd")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: Missing required commands: ${MISSING[*]}"
    echo "Install them before running this script."
    exit 1
fi

# --- Configure paperless ---
echo ""
echo "--- Configuring paperless ---"
if [ ! -f paperless.conf ]; then
    cp paperless.conf.example paperless.conf
    sed -i 's/^PAPERLESS_SECRET_KEY=.*/PAPERLESS_SECRET_KEY='"$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")"'/' paperless.conf
    sed -i 's/^#PAPERLESS_DEBUG=.*/PAPERLESS_DEBUG=true/' paperless.conf
    # Uncomment if not already set
    grep -q '^PAPERLESS_DEBUG=' paperless.conf || echo "PAPERLESS_DEBUG=true" >> paperless.conf
    echo "  ✓ Created paperless.conf with debug enabled"
else
    echo "  ✓ paperless.conf already exists"
fi

mkdir -p consume media

# --- Start services (Redis, Postgres, etc.) ---
echo ""
echo "--- Starting services ---"
if [ -f scripts/start_services.sh ]; then
    bash scripts/start_services.sh
    echo "  Waiting for Postgres..."
    for i in $(seq 1 30); do
        if docker exec "$(docker ps -q --filter ancestor=postgres:15)" pg_isready -U postgres &>/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    echo "  ✓ Services started"
else
    echo "  No start_services.sh found — starting Redis only"
    docker run -d -p 6379:6379 --restart unless-stopped --name paperless-redis redis:latest 2>/dev/null || true
    echo "  ✓ Redis running"
fi

# --- Python dependencies ---
echo ""
echo "--- Installing Python dependencies ---"
uv sync --group dev
echo "  ✓ Python deps installed"

# --- Pre-commit hooks ---
echo ""
echo "--- Installing pre-commit hooks ---"
uv run prek install
echo "  ✓ Pre-commit hooks installed"

# --- Database migrations + superuser ---
echo ""
echo "--- Running migrations ---"
cd src/
uv run manage.py migrate
echo "  ✓ Database migrated"

uv run manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@localhost', 'admin')
    print('  ✓ Created superuser: admin / admin')
else:
    print('  ✓ Superuser already exists')
"
cd ..

# --- Frontend dependencies ---
echo ""
echo "--- Setting up frontend ---"
cd src-ui/
pnpm install
echo "  ✓ Frontend deps installed"
cd ..

# --- Summary ---
echo ""
echo "=== Setup complete ==="
echo ""
echo "Start backend:"
echo "  cd src/ && uv run manage.py runserver"
echo ""
echo "Start frontend:"
echo "  cd src-ui/ && pnpm ng serve"
echo ""
echo "Run backend tests:"
echo "  cd src/ && uv run pytest"
echo ""
echo "Build frontend for production:"
echo "  cd src-ui/ && pnpm ng build --configuration production"
