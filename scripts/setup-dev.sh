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
    postgresql postgresql-client redis-server \
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

# --- Start Postgres + Redis ---
echo ""
echo "--- Starting services ---"
systemctl start postgresql 2>/dev/null || pg_ctlcluster $(pg_lsclusters -h | head -1 | awk '{print $1, $2}') start 2>/dev/null || true
systemctl start redis-server 2>/dev/null || redis-server --daemonize yes 2>/dev/null || true

# Create Postgres user + database if needed
su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='paperless'\" | grep -q 1 || psql -c \"CREATE USER paperless WITH PASSWORD 'paperless' CREATEDB;\"" 2>/dev/null
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='paperless'\" | grep -q 1 || psql -c \"CREATE DATABASE paperless OWNER paperless;\"" 2>/dev/null
echo "  ✓ PostgreSQL ready (paperless/paperless)"
echo "  ✓ Redis ready"

# --- Configure paperless ---
echo ""
echo "--- Configuring paperless ---"
if [ ! -f paperless.conf ]; then
    cp paperless.conf.example paperless.conf
    sed -i 's/^PAPERLESS_SECRET_KEY=.*/PAPERLESS_SECRET_KEY='"$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")"'/' paperless.conf
    # Enable debug and configure services
    cat >> paperless.conf <<CONF
PAPERLESS_DEBUG=true
PAPERLESS_DBHOST=localhost
PAPERLESS_DBNAME=paperless
PAPERLESS_DBUSER=paperless
PAPERLESS_DBPASS=paperless
PAPERLESS_REDIS=redis://localhost:6379
CONF
    echo "  ✓ Created paperless.conf (debug + Postgres + Redis)"
else
    echo "  ✓ paperless.conf already exists"
fi

mkdir -p consume media

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
