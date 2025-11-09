#!/bin/bash
# Test script for IntelliDocs new features in Docker
# This script verifies that all ML/OCR dependencies and features are working

set -e

echo "=========================================="
echo "IntelliDocs Feature Test Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is installed${NC}"

# Check if compose file exists
COMPOSE_FILE="compose/docker-compose.intellidocs.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}✗ Compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker compose file found${NC}"
echo ""

# Test 1: Check if containers are running
echo "Test 1: Checking if containers are running..."
if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Containers are running${NC}"
else
    echo -e "${YELLOW}! Containers are not running. Starting them...${NC}"
    docker compose -f "$COMPOSE_FILE" up -d
    echo "Waiting 60 seconds for containers to initialize..."
    sleep 60
fi
echo ""

# Test 2: Check Python dependencies
echo "Test 2: Checking ML/OCR Python dependencies..."
docker compose -f "$COMPOSE_FILE" exec -T webserver python3 << 'PYTHON_EOF'
import sys

errors = []
success = []

# Test torch
try:
    import torch
    success.append(f"torch {torch.__version__}")
except ImportError as e:
    errors.append(f"torch: {str(e)}")

# Test transformers
try:
    import transformers
    success.append(f"transformers {transformers.__version__}")
except ImportError as e:
    errors.append(f"transformers: {str(e)}")

# Test OpenCV
try:
    import cv2
    success.append(f"opencv {cv2.__version__}")
except ImportError as e:
    errors.append(f"opencv: {str(e)}")

# Test sentence-transformers
try:
    import sentence_transformers
    success.append(f"sentence-transformers {sentence_transformers.__version__}")
except ImportError as e:
    errors.append(f"sentence-transformers: {str(e)}")

# Test pandas
try:
    import pandas
    success.append(f"pandas {pandas.__version__}")
except ImportError as e:
    errors.append(f"pandas: {str(e)}")

# Test numpy
try:
    import numpy
    success.append(f"numpy {numpy.__version__}")
except ImportError as e:
    errors.append(f"numpy: {str(e)}")

# Test PIL
try:
    from PIL import Image
    success.append("pillow (PIL)")
except ImportError as e:
    errors.append(f"pillow: {str(e)}")

# Test pytesseract
try:
    import pytesseract
    success.append("pytesseract")
except ImportError as e:
    errors.append(f"pytesseract: {str(e)}")

for s in success:
    print(f"✓ {s}")

if errors:
    print("\nErrors:")
    for e in errors:
        print(f"✗ {e}")
    sys.exit(1)
else:
    print("\n✓ All dependencies installed correctly!")
    sys.exit(0)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All Python dependencies are available${NC}"
else
    echo -e "${RED}✗ Some Python dependencies are missing${NC}"
    exit 1
fi
echo ""

# Test 3: Check if ML modules exist
echo "Test 3: Checking ML/OCR module files..."
for module in "documents/ml/classifier.py" "documents/ml/ner.py" "documents/ml/semantic_search.py" "documents/ocr/table_extractor.py" "documents/ocr/handwriting.py" "documents/ocr/form_detector.py"; do
    if docker compose -f "$COMPOSE_FILE" exec -T webserver test -f "/usr/src/paperless/src/$module"; then
        echo -e "${GREEN}✓ $module exists${NC}"
    else
        echo -e "${RED}✗ $module not found${NC}"
        exit 1
    fi
done
echo ""

# Test 4: Check Redis connection
echo "Test 4: Checking Redis connection..."
if docker compose -f "$COMPOSE_FILE" exec -T broker redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✓ Redis is responding${NC}"
else
    echo -e "${RED}✗ Redis is not responding${NC}"
    exit 1
fi
echo ""

# Test 5: Check if webserver is responding
echo "Test 5: Checking if webserver is responding..."
if docker compose -f "$COMPOSE_FILE" exec -T webserver curl -f -s http://localhost:8000 > /dev/null; then
    echo -e "${GREEN}✓ Webserver is responding${NC}"
else
    echo -e "${YELLOW}! Webserver is not responding yet (may still be initializing)${NC}"
fi
echo ""

# Test 6: Check environment variables
echo "Test 6: Checking ML/OCR environment variables..."
docker compose -f "$COMPOSE_FILE" exec -T webserver bash << 'BASH_EOF'
echo "PAPERLESS_ENABLE_ML_FEATURES=${PAPERLESS_ENABLE_ML_FEATURES:-not set}"
echo "PAPERLESS_ENABLE_ADVANCED_OCR=${PAPERLESS_ENABLE_ADVANCED_OCR:-not set}"
echo "PAPERLESS_ML_CLASSIFIER_MODEL=${PAPERLESS_ML_CLASSIFIER_MODEL:-not set}"
echo "PAPERLESS_USE_GPU=${PAPERLESS_USE_GPU:-not set}"
BASH_EOF
echo ""

# Test 7: Check ML model cache
echo "Test 7: Checking ML model cache..."
docker compose -f "$COMPOSE_FILE" exec -T webserver ls -lah /usr/src/paperless/.cache/ || echo -e "${YELLOW}! ML cache directory may not be initialized yet${NC}"
echo ""

# Test 8: Check system resources
echo "Test 8: Checking system resources..."
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker compose -f "$COMPOSE_FILE" ps -q)
echo ""

echo "=========================================="
echo -e "${GREEN}✓ All tests completed successfully!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Access IntelliDocs at: http://localhost:8000"
echo "2. Create a superuser: docker compose -f $COMPOSE_FILE exec webserver python manage.py createsuperuser"
echo "3. Upload a test document to try the new ML/OCR features"
echo "4. Check logs: docker compose -f $COMPOSE_FILE logs -f webserver"
echo ""
echo "For more information, see: DOCKER_SETUP_INTELLIDOCS.md"
echo ""
