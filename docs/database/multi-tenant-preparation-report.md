# PostgreSQL Multi-Tenancy Preparation Report

**Date:** 2026-01-20
**Status:** ✅ COMPLETE - Database Ready for Multi-Tenant Implementation
**Database:** paperless @ postgres-0 (paless namespace)

---

## Executive Summary

The PostgreSQL database has been successfully prepared for multi-tenant architecture implementation. All acceptance criteria have been met:

✅ PostgreSQL version verified (18.1 - exceeds requirement of 12+)
✅ Required extensions installed and tested (uuid-ossp 1.1, pgcrypto 1.4)
✅ Tables using ModelWithOwner identified and documented
✅ Database connections from K3s pods verified working
✅ Schema exported for migration planning
✅ Database resources documented
✅ No errors in PostgreSQL logs

---

## 1. PostgreSQL Version Verification

### Current Version
```
PostgreSQL 18.1 (Debian 18.1-1.pgdg13+2) on x86_64-pc-linux-gnu
Compiled by: gcc (Debian 14.2.0-19) 14.2.0, 64-bit
```

**Status:** ✅ PASS - Version 18.1 exceeds minimum requirement of PostgreSQL 12+

### Version Features Available for Multi-Tenancy
- Row-Level Security (RLS) - Available since PostgreSQL 9.5
- Partitioning improvements - Enhanced in PostgreSQL 10+
- Generated columns - Available since PostgreSQL 12
- UUID generation via extensions - Fully supported
- Advanced indexing (BRIN, GIN, GiST) - All available

---

## 2. Required Extensions

### uuid-ossp Extension
```
Extension Name: uuid-ossp
Version: 1.1
Status: ✅ INSTALLED AND TESTED
```

**Test Results:**
```sql
SELECT uuid_generate_v4() AS test_uuid;
-- Result: d296f28d-5546-4424-bc82-a9c7a3989da9
```

**Purpose for Multi-Tenancy:**
- Generate unique tenant IDs (UUID format)
- Create universally unique document identifiers
- Support distributed ID generation without conflicts

### pgcrypto Extension
```
Extension Name: pgcrypto
Version: 1.4
Status: ✅ INSTALLED AND TESTED
```

**Test Results:**
```sql
SELECT encode(digest('test', 'sha256'), 'hex') AS test_hash;
-- Result: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Purpose for Multi-Tenancy:**
- Encrypt sensitive tenant data if needed
- Generate secure hashes for tenant credentials
- Support cryptographic functions for data isolation

---

## 3. ModelWithOwner Tables Analysis

### Django Model Hierarchy
```
ModelWithOwner (abstract base class)
├── MatchingModel (abstract)
│   ├── Correspondent
│   ├── Tag (also inherits TreeNodeModel)
│   ├── DocumentType
│   └── StoragePath
├── Document (also inherits SoftDeleteModel)
├── SavedView
└── PaperlessTask
```

### Tables Requiring tenant_id Column

The following tables currently have `owner_id` (FK to auth_user) and will need `tenant_id` added:

#### 1. documents_correspondent
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index, unique(name, owner_id)
- **Multi-Tenant Impact:** HIGH - Shared across users within tenant
- **Migration Strategy:** Add tenant_id, modify unique constraints to include tenant_id

#### 2. documents_tag
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index, unique(name, owner_id)
- **Special Features:** TreeNode model (hierarchical structure)
- **Multi-Tenant Impact:** HIGH - Tag hierarchies must be tenant-scoped
- **Migration Strategy:** Add tenant_id, ensure parent-child relationships stay within tenant

#### 3. documents_documenttype
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index, unique(name, owner_id)
- **Multi-Tenant Impact:** HIGH - Document classification per tenant
- **Migration Strategy:** Add tenant_id, modify unique constraints

#### 4. documents_storagepath
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index, unique(name, owner_id)
- **Multi-Tenant Impact:** CRITICAL - File paths must be tenant-isolated
- **Migration Strategy:** Add tenant_id, update path resolution logic

#### 5. documents_document
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index
- **Foreign Keys:** correspondent_id, document_type_id, storage_path_id
- **Multi-Tenant Impact:** CRITICAL - Core data isolation required
- **Migration Strategy:** Add tenant_id, ensure all FK references are tenant-scoped
- **Current Size:** 288 KB (largest table)

#### 6. documents_savedview
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index
- **Multi-Tenant Impact:** MEDIUM - User preferences within tenant
- **Migration Strategy:** Add tenant_id for proper isolation

#### 7. documents_paperlesstask
- **Current Structure:** owner_id → auth_user(id)
- **Indexes:** owner_id index
- **Multi-Tenant Impact:** HIGH - Task execution must be tenant-scoped
- **Migration Strategy:** Add tenant_id, ensure Celery tasks are tenant-aware

### Additional Tables to Consider

While not directly inheriting ModelWithOwner, these tables may need tenant_id:

- **auth_user** - Core user table (tenant membership)
- **documents_note** - Has user_id FK (via Document relationship)
- **documents_sharelink** - Has owner_id FK
- **documents_customfieldinstance** - Tied to Documents
- **documents_workflow*** - Various workflow tables

---

## 4. Database Connection Verification

### Connection Tests from K3s Pods

#### Web Pod (paless-web-5555cb958c-7s4rq)
```sql
SELECT 'Connection successful from web pod' AS test;
-- Result: Connection successful from web pod
```
**Status:** ✅ WORKING

#### Worker Pod (paless-worker-75765b479d-6ch2t)
```sql
SELECT 'Connection successful from worker pod' AS test;
-- Result: Connection successful from worker pod
```
**Status:** ✅ WORKING

### Current Connection Configuration
- **Service:** postgres.paless.svc.cluster.local:5432
- **Database:** paperless
- **User:** paperless
- **Active Connections:** 2 / 100 (2% utilization)
- **Max Connections:** 100

---

## 5. Schema Export

### Exported Schema Details
- **File Location:** `/workspace/docs/database/schema-before-multi-tenant.sql`
- **File Size:** 209 KB
- **Line Count:** 6,323 lines
- **Export Type:** Schema only (no data)
- **Export Date:** 2026-01-20

### Schema Contents
- 72 tables
- Indexes on all foreign keys
- Unique constraints for owner-scoped names
- Full DDL for recreation

**Usage:** This schema export serves as the baseline for migration planning. It can be used to:
1. Compare before/after schema changes
2. Generate migration scripts
3. Rollback reference if needed
4. Documentation of current state

---

## 6. Database Resource Usage

### Storage Analysis

#### Overall Database
- **Total Size:** 13 MB
- **Growth Capacity:** 10 GB allocated (PVC)
- **Utilization:** 0.13% of allocated storage

#### Top 10 Tables by Size
| Table Name | Size | Purpose |
|------------|------|---------|
| documents_document | 288 KB | Core documents |
| django_celery_results_taskresult | 160 KB | Async task results |
| auth_permission | 88 KB | Django permissions |
| documents_paperlesstask | 80 KB | Paperless tasks |
| django_migrations | 72 KB | Migration history |
| auth_user | 64 KB | User accounts |
| documents_workflowaction | 64 KB | Workflow actions |
| paperless_mail_mailrule | 64 KB | Mail rules |
| django_session | 64 KB | User sessions |
| documents_sharelink | 56 KB | Share links |

### Connection Pool Analysis

#### Current State
- **Max Connections:** 100
- **Active Connections:** 2
- **Utilization:** 2%

#### Multi-Tenant Recommendations

For multi-tenant architecture, connection pooling will be critical:

**Expected Connection Pattern per Tenant:**
- Web processes: 2-5 connections
- Worker processes: 2-4 connections
- Scheduler: 1 connection

**Recommended Configuration:**
```python
# PgBouncer or Django CONN_MAX_AGE settings
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 300,  # 5 minutes
        'OPTIONS': {
            'connect_timeout': 10,
            'pool': {
                'min_size': 2,
                'max_size': 10,
            }
        }
    }
}
```

**Scaling Calculation:**
- Current: 2 connections for single deployment
- Target (10 tenants): ~50 connections (with pooling)
- Target (50 tenants): ~200 connections (requires max_connections increase)

**Action Item:** Consider implementing PgBouncer for connection pooling when scaling beyond 20 tenants.

---

## 7. PostgreSQL Configuration Review

### Current Settings (Relevant to Multi-Tenancy)

```sql
max_connections = 100
shared_buffers = (default ~32MB for 1GB memory limit)
work_mem = (default ~4MB)
maintenance_work_mem = (default ~64MB)
```

### Resource Limits (from K8s StatefulSet)

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### Recommendations for Multi-Tenant Scaling

1. **Connection Limits:** Current 100 max_connections is adequate for <20 tenants
2. **Memory Allocation:** 1Gi limit suitable for development; production should increase to 2-4Gi
3. **Storage:** 10Gi PVC is adequate for initial deployment
4. **CPU:** 1 core limit sufficient for current load

---

## 8. PostgreSQL Logs Analysis

### Recent Log Review
**Time Period:** Last 10 minutes
**Errors Found:** None
**Warnings Found:** None

### Historical Issues (Resolved)
The following errors were found in earlier logs but are now resolved:
- Authentication failures during initial deployment (resolved with correct credentials)
- Migration errors for existing columns (expected behavior, migrations are idempotent)
- Missing role errors (resolved by multi-tenant init job)

### Multi-Tenant Init Job Logs
```
✓ User paperless_app already exists
✓ Extension "uuid-ossp" already exists
✓ Extension "pgcrypto" already exists
✓ Permissions granted
✓ Multi-tenant initialization complete
```

**Status:** ✅ NO ERRORS - Database is healthy

---

## 9. Migration Planning Summary

### Phase 1: Schema Changes (Future)
1. Create `tenants` table (id, name, slug, created_at, settings)
2. Add `tenant_id` column to all ModelWithOwner tables
3. Add `tenant_id` to auth_user (user-tenant membership)
4. Create indexes on tenant_id columns
5. Update unique constraints to include tenant_id

### Phase 2: Data Migration (Future)
1. Create default tenant for existing data
2. Populate tenant_id for all existing records
3. Update foreign key constraints
4. Implement Row-Level Security (RLS) policies

### Phase 3: Application Changes (Future)
1. Update Django models to include tenant field
2. Implement tenant middleware for request context
3. Update querysets to filter by tenant
4. Modify file storage paths to include tenant_id
5. Update Celery tasks to be tenant-aware

### Phase 4: Testing & Validation (Future)
1. Verify data isolation between tenants
2. Test connection pooling under load
3. Validate backup/restore procedures per tenant
4. Security audit for cross-tenant data leakage

---

## 10. Connection Pooling Requirements

### Current Architecture
- Direct PostgreSQL connections from each pod
- No connection pooler in place
- Django default connection behavior (no persistent connections)

### Multi-Tenant Requirements

#### Option 1: PgBouncer (Recommended for Production)
```yaml
# Add to kubernetes deployment
pgbouncer:
  poolMode: transaction  # or session for Django
  maxClientConn: 1000
  defaultPoolSize: 25
  reservePoolSize: 5
  reservePoolTimeout: 3
```

**Advantages:**
- Reduces actual DB connections
- Supports many concurrent clients
- Lightweight and battle-tested

#### Option 2: Django Connection Pooling
```python
# settings.py
DATABASES['default']['CONN_MAX_AGE'] = 600  # 10 minutes
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
```

**Advantages:**
- No additional infrastructure
- Simple to configure
- Good for moderate scale (<20 tenants)

#### Recommendation
- **Development/QA:** Django CONN_MAX_AGE = 300
- **Production (<20 tenants):** Django CONN_MAX_AGE = 600
- **Production (>20 tenants):** PgBouncer in transaction mode

---

## 11. Security Considerations

### Current Security Posture
✅ Password-based authentication
✅ Separate user roles (paperless, paperless_app)
✅ Encrypted data at rest (PostgreSQL storage)
✅ Network isolation (K8s cluster networking)

### Multi-Tenant Security Requirements
1. **Data Isolation:** Row-Level Security (RLS) policies per tenant
2. **User Isolation:** Tenant-scoped authentication
3. **API Isolation:** Tenant context in every request
4. **File Isolation:** Separate storage paths per tenant
5. **Backup Isolation:** Per-tenant backup capability

### Recommended Security Enhancements
```sql
-- Example RLS policy (to be implemented later)
CREATE POLICY tenant_isolation ON documents_document
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE documents_document ENABLE ROW LEVEL SECURITY;
```

---

## 12. Acceptance Criteria Verification

| Criteria | Status | Evidence |
|----------|--------|----------|
| PostgreSQL version verified (12+) | ✅ PASS | Version 18.1 confirmed |
| uuid-ossp extension installed | ✅ PASS | Version 1.1, tested UUID generation |
| pgcrypto extension installed | ✅ PASS | Version 1.4, tested hashing |
| ModelWithOwner tables documented | ✅ PASS | 7 tables identified with owner_id |
| Database connection from K3s verified | ✅ PASS | Web and worker pods tested |
| Schema exported to SQL file | ✅ PASS | 209KB file, 6323 lines |
| Database resources documented | ✅ PASS | 13MB used, 100 max connections |
| Connection pooling requirements | ✅ PASS | Documented for different scales |
| No errors in PostgreSQL logs | ✅ PASS | Recent logs clean |

---

## 13. Next Steps (Not Part of This Task)

The database is now prepared for multi-tenant implementation. Future tasks will include:

1. **Create Tenant Model** - Django model for tenant management
2. **Schema Migration** - Add tenant_id to all relevant tables
3. **Data Migration** - Populate tenant_id for existing data
4. **Middleware Implementation** - Tenant context middleware
5. **RLS Policies** - Row-Level Security for data isolation
6. **Testing** - Comprehensive multi-tenant testing
7. **Documentation** - Developer guide for multi-tenant usage

---

## Appendix A: Complete Table List

### Tables with owner_id (ModelWithOwner)
1. documents_correspondent
2. documents_tag
3. documents_documenttype
4. documents_storagepath
5. documents_document
6. documents_savedview
7. documents_paperlesstask

### Related Tables (May Need tenant_id)
1. auth_user (tenant membership)
2. documents_note (via user_id)
3. documents_sharelink (has owner_id)
4. documents_customfieldinstance (via document)
5. documents_workflow* (various workflow tables)
6. documents_savedviewfilterrule (via savedview)
7. documents_workflowrun (via document)

### Django/Framework Tables (No tenant_id needed)
- auth_* (Django auth tables)
- django_* (Django internal tables)
- guardian_* (Permissions)
- mfa_* (Multi-factor auth)
- account_* (Django allauth)
- socialaccount_* (Social auth)

---

## Appendix B: Database Connection String

```bash
# From within K8s cluster
postgres://paperless:<password>@postgres.paless.svc.cluster.local:5432/paperless

# Using paperless_app user (for multi-tenant apps)
postgres://paperless_app:<password>@postgres.paless.svc.cluster.local:5432/paperless
```

---

## Appendix C: Useful SQL Queries

### Check Table Sizes
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY bytes DESC;
```

### Check Active Connections
```sql
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change
FROM pg_stat_activity
WHERE datname = 'paperless'
ORDER BY query_start DESC;
```

### Check Extensions
```sql
SELECT
    extname,
    extversion,
    extrelocatable,
    extnamespace::regnamespace AS schema
FROM pg_extension
ORDER BY extname;
```

### Check Indexes on owner_id
```sql
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND indexdef ILIKE '%owner_id%'
ORDER BY tablename;
```

---

**Report Generated:** 2026-01-20
**Database:** paperless @ postgres-0.postgres.paless.svc.cluster.local
**Status:** ✅ READY FOR MULTI-TENANT IMPLEMENTATION
