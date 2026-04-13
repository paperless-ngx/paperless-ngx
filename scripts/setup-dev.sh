#!/usr/bin/env bash
# Automates the "General setup" steps from docs/development.md.
# Run from the repo root: bash scripts/setup-dev.sh
#
# Installs all prerequisites automatically on Debian/Ubuntu.
# Designed to run inside a clean container (LXC, VM, etc.).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== paperless-ngx dev setup ==="

# --- Install system packages ---
echo ""
echo "--- Installing system packages ---"
apt-get update -qq
apt-get install -y -qq \
    build-essential pkg-config git curl \
    python3 python3-dev \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu \
    poppler-utils ghostscript unpaper qpdf \
    imagemagick libmagic-dev libpq-dev \
    >/dev/null
echo "  ✓ System packages installed"

# --- Install uv ---
if ! command -v uv &>/dev/null; then
    echo ""
    echo "--- Installing uv ---"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "  ✓ uv installed"
else
    echo "  ✓ uv already installed"
fi

# Pin Python 3.12 — psycopg-c has pre-built wheels only for 3.12
echo ""
echo "--- Ensuring Python 3.12 ---"
uv python install 3.12 2>/dev/null
export UV_PYTHON=3.12
echo "  ✓ Python 3.12 pinned"

# --- Install Node.js + pnpm ---
if ! command -v node &>/dev/null; then
    echo ""
    echo "--- Installing Node.js ---"
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - >/dev/null 2>&1
    apt-get install -y -qq nodejs >/dev/null
    echo "  ✓ Node.js $(node --version) installed"
else
    echo "  ✓ Node.js $(node --version) already installed"
fi

if ! command -v pnpm &>/dev/null; then
    echo "--- Installing pnpm ---"
    npm install -g pnpm >/dev/null 2>&1
    echo "  ✓ pnpm installed"
else
    echo "  ✓ pnpm already installed"
fi

# --- Check services ---
echo ""
echo "--- Checking services ---"
SERVICES_OK=true

# PostgreSQL — must be >= 14
if command -v psql &>/dev/null; then
    PG_VER=$(psql --version | grep -oP '\d+' | head -1)
    if [ "$PG_VER" -lt 14 ] 2>/dev/null; then
        echo "  ✗ PostgreSQL $PG_VER found — need 14+. Install from https://www.postgresql.org/download/"
        SERVICES_OK=false
    else
        echo "  ✓ PostgreSQL $PG_VER"
    fi
else
    echo "  ✗ PostgreSQL not found. Install it and create a database before running this script."
    SERVICES_OK=false
fi

# Redis
if redis-cli ping &>/dev/null; then
    echo "  ✓ Redis"
else
    echo "  ✗ Redis not reachable on localhost:6379"
    SERVICES_OK=false
fi

if [ "$SERVICES_OK" = false ]; then
    echo ""
    echo "ERROR: Required services missing or too old. Fix the above and rerun."
    exit 1
fi

# --- Configure paperless ---
echo ""
echo "--- Configuring paperless ---"
if [ ! -f paperless.conf ]; then
    cp paperless.conf.example paperless.conf
    sed -i 's/^PAPERLESS_SECRET_KEY=.*/PAPERLESS_SECRET_KEY='"$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")"'/' paperless.conf
    # Enable debug and configure services
    cat >> paperless.conf <<CONF
PAPERLESS_DEBUG=true
PAPERLESS_DBHOST=${PAPERLESS_DBHOST:-localhost}
PAPERLESS_DBNAME=${PAPERLESS_DBNAME:-paperless}
PAPERLESS_DBUSER=${PAPERLESS_DBUSER:-paperless}
PAPERLESS_DBPASS=${PAPERLESS_DBPASS:-paperless}
PAPERLESS_REDIS=${PAPERLESS_REDIS:-redis://localhost:6379}
CONF
    echo "  ✓ Created paperless.conf (debug enabled, configure DB credentials if needed)"
else
    echo "  ✓ paperless.conf already exists"
fi

mkdir -p consume media

# --- Python dependencies ---
echo ""
echo "--- Installing Python dependencies ---"
# Remove stale venv (e.g. from a previous run with a different Python version)
rm -rf .venv
uv sync --group dev
# Ensure psycopg is available — the upstream psycopg-c wheel overrides may
# not cover every platform. Install the binary fallback if psycopg is missing.
if ! uv run python -c "import psycopg" 2>/dev/null; then
    echo "  ⚠ psycopg not found, installing binary fallback..."
    uv pip install "psycopg[binary,pool]==3.3"
fi
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
