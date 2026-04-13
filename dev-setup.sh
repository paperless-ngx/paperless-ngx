#!/bin/bash
# Local development setup for paperless-ngx OCR templates feature
# Run this script from the repo root: bash dev-setup.sh
set -e

echo "=== paperless-ngx local dev setup ==="

# Ensure PATH includes linuxbrew and nvm
export PATH="/home/linuxbrew/.linuxbrew/bin:/home/artie/.nvm/versions/node/v24.13.0/bin:$PATH"

# 1. System dependencies
echo ""
echo "--- Checking system dependencies ---"
MISSING=""
for cmd in tesseract pdftoppm ghostscript docker; do
    if ! command -v $cmd &>/dev/null; then
        MISSING="$MISSING $cmd"
    else
        echo "  ✓ $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo ""
    echo "Missing:$MISSING"
    echo "Install with: sudo apt install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng poppler-utils ghostscript unpaper qpdf imagemagick libmagic-dev libpq-dev docker.io"
    echo ""
    read -p "Install now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng poppler-utils ghostscript unpaper qpdf imagemagick libmagic-dev libpq-dev docker.io
    else
        echo "Skipping — some tests may fail without these."
    fi
fi

# 2. Start Postgres + Redis via Docker Compose
echo ""
echo "--- Starting Postgres & Redis ---"
docker compose -f docker/compose/docker-compose.dev.yml up -d
echo "  Waiting for Postgres..."
until docker compose -f docker/compose/docker-compose.dev.yml exec -T postgres pg_isready -U paperless &>/dev/null; do
    sleep 1
done
echo "  ✓ Postgres ready"
echo "  ✓ Redis ready"

# 3. Python dependencies
echo ""
echo "--- Setting up Python environment ---"
uv sync --group dev
echo "  ✓ Python deps installed"

# 4. Configure paperless
echo ""
echo "--- Configuring paperless ---"
if [ ! -f paperless.conf ]; then
    cat > paperless.conf <<CONF
PAPERLESS_DEBUG=true
PAPERLESS_CONSUMPTION_DIR=./consume
PAPERLESS_DATA_DIR=./data
PAPERLESS_MEDIA_ROOT=./media
PAPERLESS_STATICDIR=./static
PAPERLESS_DBHOST=localhost
PAPERLESS_DBNAME=paperless
PAPERLESS_DBUSER=paperless
PAPERLESS_DBPASS=paperless
PAPERLESS_REDIS=redis://localhost:6379
CONF
    echo "  ✓ Created paperless.conf"
else
    echo "  ✓ paperless.conf exists"
fi

mkdir -p consume media data static

# 5. Run migrations
echo ""
echo "--- Running migrations ---"
cd src/
uv run manage.py migrate
echo "  ✓ Database migrated"

# Generate migration for OCR templates if needed
uv run manage.py makemigrations documents --name ocr_templates 2>/dev/null || true

# Apply any new migrations
uv run manage.py migrate
echo "  ✓ OCR template migration applied"

# Create superuser if none exists
uv run manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@localhost', 'admin')
    print('  ✓ Created superuser: admin / admin')
else:
    print('  ✓ Superuser already exists')
"

cd ..

# 6. Frontend dependencies
echo ""
echo "--- Setting up frontend ---"
cd src-ui/

if ! command -v pnpm &>/dev/null; then
    echo "  Installing pnpm..."
    npm install -g pnpm
fi

pnpm install
echo "  ✓ Frontend deps installed"
cd ..

# 7. Summary
echo ""
echo "=== Setup complete ==="
echo ""
echo "Services running:"
echo "  PostgreSQL: localhost:5432 (paperless/paperless)"
echo "  Redis:      localhost:6379"
echo ""
echo "Run backend tests (our feature only):"
echo "  cd src/ && uv run pytest documents/tests/test_zone_ocr.py documents/tests/test_api_ocr_templates.py -v"
echo ""
echo "Run ALL backend tests:"
echo "  cd src/ && uv run pytest"
echo ""
echo "Start backend dev server:"
echo "  cd src/ && uv run manage.py runserver"
echo ""
echo "Start frontend dev server:"
echo "  cd src-ui/ && pnpm ng serve"
echo ""
echo "Stop dev services:"
echo "  docker compose -f docker/compose/docker-compose.dev.yml down"
