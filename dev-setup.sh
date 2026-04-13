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
for cmd in tesseract redis-server pdftoppm ghostscript; do
    if ! command -v $cmd &>/dev/null; then
        MISSING="$MISSING $cmd"
    else
        echo "  ✓ $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo ""
    echo "Missing:$MISSING"
    echo "Install with: sudo apt install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng redis-server poppler-utils ghostscript unpaper qpdf imagemagick libmagic-dev libpq-dev"
    echo ""
    read -p "Install now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng redis-server poppler-utils ghostscript unpaper qpdf imagemagick libmagic-dev libpq-dev
    else
        echo "Skipping — some tests may fail without these."
    fi
fi

# 2. Python dependencies
echo ""
echo "--- Setting up Python environment ---"
cd src/
uv sync --group dev
echo "  ✓ Python deps installed"

# 3. Database setup (SQLite for dev)
echo ""
echo "--- Setting up database ---"
if [ ! -f ../paperless.conf ]; then
    cat > ../paperless.conf <<CONF
PAPERLESS_DEBUG=true
PAPERLESS_CONSUMPTION_DIR=../consume
PAPERLESS_DATA_DIR=../data
PAPERLESS_MEDIA_ROOT=../media
PAPERLESS_STATICDIR=../static
CONF
    echo "  ✓ Created paperless.conf"
fi

mkdir -p ../consume ../media ../data ../static

# Run migrations (includes our OCR template tables)
uv run manage.py migrate --run-syncdb
echo "  ✓ Database migrated"

# Create superuser if none exists
uv run manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@localhost', 'admin')
    print('  ✓ Created superuser: admin / admin')
else:
    print('  ✓ Superuser already exists')
"

# 4. Frontend dependencies
echo ""
echo "--- Setting up frontend ---"
cd ../src-ui/

if ! command -v pnpm &>/dev/null; then
    echo "  Installing pnpm..."
    npm install -g pnpm
fi

pnpm install
echo "  ✓ Frontend deps installed"

# 5. Summary
echo ""
echo "=== Setup complete ==="
echo ""
echo "To run backend tests (our feature only):"
echo "  cd src/ && uv run pytest documents/tests/test_zone_ocr.py documents/tests/test_api_ocr_templates.py -v"
echo ""
echo "To run ALL backend tests:"
echo "  cd src/ && uv run pytest"
echo ""
echo "To run backend dev server:"
echo "  cd src/ && uv run manage.py runserver"
echo ""
echo "To run frontend dev server:"
echo "  cd src-ui/ && pnpm ng serve"
echo ""
echo "To run frontend tests:"
echo "  cd src-ui/ && pnpm run test"
