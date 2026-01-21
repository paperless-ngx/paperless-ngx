#!/bin/bash
# PostgreSQL inspection helper for Paless
# Usage: ./scripts/db-inspect.sh [query-name]

set -e

NAMESPACE="paless"
POD="postgres-0"
USER="paperless"
DB="paperless"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

function run_query() {
    kubectl exec -n "$NAMESPACE" "$POD" -- psql -U "$USER" -d "$DB" -c "$1"
}

function show_menu() {
    echo -e "${GREEN}=== Paless Database Inspector ===${NC}"
    echo ""
    echo "Available commands:"
    echo "  tenants      - Show all tenants"
    echo "  docs         - Show document counts per tenant"
    echo "  tables       - List all tables"
    echo "  rls          - Show RLS policies"
    echo "  sizes        - Show table sizes"
    echo "  users        - Show Django users"
    echo "  connections  - Show active connections"
    echo "  shell        - Open interactive psql shell"
    echo "  custom       - Run custom query"
    echo ""
}

case "${1:-menu}" in
    tenants)
        echo -e "${YELLOW}Tenants:${NC}"
        run_query "SELECT id, name, subdomain, is_active, created_at FROM paperless_tenant ORDER BY subdomain;"
        ;;

    docs)
        echo -e "${YELLOW}Document counts:${NC}"
        run_query "SELECT COUNT(*) as total_documents FROM documents_document;"
        echo ""
        echo -e "${YELLOW}Documents by tenant_id (UUID):${NC}"
        run_query "SELECT tenant_id, COUNT(*) as document_count FROM documents_document GROUP BY tenant_id ORDER BY tenant_id;"
        ;;

    tables)
        echo -e "${YELLOW}All tables:${NC}"
        run_query "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
        ;;

    rls)
        echo -e "${YELLOW}RLS Policies:${NC}"
        run_query "SELECT tablename, policyname, qual FROM pg_policies WHERE tablename LIKE 'documents_%' ORDER BY tablename;"
        ;;

    sizes)
        echo -e "${YELLOW}Table sizes:${NC}"
        run_query "SELECT schemaname||'.'||tablename AS table, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
        ;;

    users)
        echo -e "${YELLOW}Django users:${NC}"
        run_query "SELECT id, username, email, is_staff, is_superuser, is_active, date_joined FROM auth_user ORDER BY id;"
        ;;

    connections)
        echo -e "${YELLOW}Active connections:${NC}"
        run_query "SELECT pid, usename, application_name, client_addr, state FROM pg_stat_activity WHERE datname = 'paperless';"
        ;;

    shell)
        echo -e "${YELLOW}Opening PostgreSQL shell...${NC}"
        kubectl exec -n "$NAMESPACE" "$POD" -it -- psql -U "$USER" -d "$DB"
        ;;

    custom)
        if [ -z "$2" ]; then
            echo "Usage: $0 custom \"SELECT * FROM tablename;\""
            exit 1
        fi
        run_query "$2"
        ;;

    menu|*)
        show_menu
        ;;
esac
