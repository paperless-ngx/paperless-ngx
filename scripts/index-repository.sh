#!/bin/bash
set -e

#=============================================================================
# Initial Repository Indexing Script
#=============================================================================
# Purpose: Full code indexing for forked/new repositories
# Usage: ./scripts/index-repository.sh
# Requirements: Docker services must be running (docker compose up -d)
#=============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$PROJECT_ROOT/.context-management/.env" ]; then
    source "$PROJECT_ROOT/.context-management/.env"
else
    echo "ERROR: .env file not found at $PROJECT_ROOT/.context-management/.env"
    echo ""
    echo "Run init_repo.sh first to set up the project"
    exit 1
fi

REPO_NAME=${PROJECT_NAME:-generic-repo}

echo "============================================================="
echo "Full Repository Indexing"
echo "============================================================="
echo "Repository: $REPO_NAME"
echo "Path: $PROJECT_ROOT"
echo ""

# Health checks
echo "1. Checking services..."
echo ""

# Check PostgreSQL
if ! docker exec "${REPO_NAME}-postgres" pg_isready -U ${POSTGRES_USER:-context_user} >/dev/null 2>&1; then
    echo "❌ ERROR: PostgreSQL not ready"
    echo ""
    echo "Start services first:"
    echo "  cd $PROJECT_ROOT/.context-management"
    echo "  docker compose up -d"
    echo ""
    echo "Then wait ~30 seconds for services to become healthy:"
    echo "  docker ps"
    echo ""
    exit 1
fi
echo "  ✓ PostgreSQL ready"

# Check Neo4j
if ! docker exec "${REPO_NAME}-neo4j" cypher-shell -u ${NEO4J_USERNAME:-neo4j} -p "${NEO4J_PASSWORD:-context_graph}" "RETURN 1" >/dev/null 2>&1; then
    echo "❌ ERROR: Neo4j not ready"
    echo ""
    echo "Wait for services to start (~30 seconds)"
    echo "Check status: docker ps"
    echo ""
    exit 1
fi
echo "  ✓ Neo4j ready"

# Check Qdrant
if ! curl -sf http://localhost:${QDRANT_PORT:-6333}/collections >/dev/null 2>&1; then
    echo "❌ ERROR: Qdrant not ready"
    echo ""
    echo "Wait for services to start (~30 seconds)"
    echo "Check status: docker ps"
    echo ""
    exit 1
fi
echo "  ✓ Qdrant ready"

# Check Infinity embeddings (code)
if ! curl -sf http://localhost:${TEI_CODE_PORT:-8081}/health >/dev/null 2>&1; then
    echo "⚠️  WARNING: Infinity code embeddings not ready"
    echo "  Indexing will continue but semantic search may not work optimally"
    echo "  Check: docker logs ${REPO_NAME}-infinity-code"
    echo ""
else
    echo "  ✓ Infinity code embeddings ready"
fi

# Check Infinity embeddings (text)
if ! curl -sf http://localhost:${TEI_TEXT_PORT:-8080}/health >/dev/null 2>&1; then
    echo "⚠️  WARNING: Infinity text embeddings not ready"
    echo "  Indexing will continue but some features may not work"
    echo "  Check: docker logs ${REPO_NAME}-infinity-text"
    echo ""
else
    echo "  ✓ Infinity text embeddings ready"
fi

echo ""
echo "============================================================="
echo "2. Indexing codebase..."
echo "============================================================="
echo ""
echo "This may take 2-15 minutes depending on repository size:"
echo "  • Small repo (<100 files):     ~30 seconds"
echo "  • Medium repo (100-1k files):  2-5 minutes"
echo "  • Large repo (1k+ files):      5-15 minutes"
echo ""
echo "Progress will be shown below:"
echo "-------------------------------------------------------------"
echo ""

# Run indexing with verbose output
cd "$PROJECT_ROOT/.context-management"
python3 tools/codebase_mapper.py "$PROJECT_ROOT" --name "$REPO_NAME" --verbose

echo ""
echo "-------------------------------------------------------------"
echo ""
echo "============================================================="
echo "✅ Indexing Complete!"
echo "============================================================="
echo ""
echo "Your code is now fully indexed and searchable."
echo ""
echo "Available code analysis tools:"
echo "  • search_code_semantic(query)      - Find code by meaning"
echo "  • find_files_by_topic(topic)       - Discover relevant files"
echo "  • get_code_structure(file_path)    - Analyze file contents"
echo "  • find_function_calls(function)    - Trace call chains"
echo "  • get_class_details(class_name)    - Inspect classes"
echo "  • trace_imports(file_path)         - Map dependencies"
echo ""
echo "Future updates are automatic via git post-merge hook."
echo "When you merge code to main, changed files are re-indexed automatically."
echo ""
echo "To verify indexing:"
echo "  check_indexing_status()  # MCP tool"
echo ""
echo "============================================================="
