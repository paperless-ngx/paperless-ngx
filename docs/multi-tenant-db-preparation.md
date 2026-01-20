# PostgreSQL Multi-Tenant Database Preparation Report

**Date:** 2026-01-20
**PostgreSQL Version:** 18.1 (Debian 18.1-1.pgdg13+2)
**Database:** paperless
**User:** paperless

## Executive Summary

This document provides a comprehensive assessment of the PostgreSQL database in preparation for multi-tenant architecture implementation. All verification tasks have been completed successfully.

## 1. PostgreSQL Version Verification

**Status:** ✅ PASSED

- **Installed Version:** PostgreSQL 18.1
- **Minimum Required:** PostgreSQL 12+
- **Result:** Version is well above minimum requirements and includes latest features

## 2. Required Extensions

**Status:** ✅ INSTALLED AND TESTED

### uuid-ossp Extension
- **Version:** 1.1
- **Purpose:** Generate universally unique identifiers (UUIDs) for tenant isolation
- **Test Result:** Successfully generated UUID: `f7d7de0a-a4c8-4906-8f26-93c94867d94d`
- **Location:** public schema

### pgcrypto Extension
- **Version:** 1.4
- **Purpose:** Cryptographic functions for encryption and hashing
- **Test Result:** Successfully hashed test string with SHA-256
- **Location:** public schema

## 3. Tables Using ModelWithOwner Base Class

The following tables inherit from `ModelWithOwner` and already have an `owner_id` column. These tables will need a `tenant_id` column added in the migration phase:

### Core Document Models
1. **documents_correspondent** - Document correspondents/senders
2. **documents_document** - Main document table
3. **documents_documenttype** - Document type classifications
4. **documents_storagepath** - Document storage path configurations
5. **documents_tag** - Document tags/labels

### Supporting Models
6. **documents_paperlesstask** - Background task tracking
7. **documents_savedview** - User-saved document views

### ShareLink Model
8. **documents_sharelink** - Document sharing links (has `owner_id`)

### Mail Integration Models
9. **paperless_mail_mailaccount** - Mail account configurations
10. **paperless_mail_mailrule** - Mail processing rules
11. **paperless_mail_processedmail** - Processed mail tracking

**Total:** 11 tables requiring tenant_id column

## 4. ModelWithOwner Implementation

**Location:** `src/documents/models.py:31-42`

```python
class ModelWithOwner(models.Model):
    owner = models.ForeignKey(
        User,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name=_("owner"),
    )

    class Meta:
        abstract = True
```

### Models Inheriting from ModelWithOwner

1. **MatchingModel** (abstract base) → inherits from ModelWithOwner
   - Correspondent
   - Tag
   - DocumentType
   - StoragePath

2. **Document** → inherits from SoftDeleteModel and ModelWithOwner

3. **SavedView** → inherits from ModelWithOwner

4. **PaperlessTask** → inherits from ModelWithOwner

## 5. Database Connection Verification

**Status:** ✅ VERIFIED

- **Pod Name:** postgres-0
- **Namespace:** paless
- **Pod Status:** Running (1/1)
- **Connection:** Successfully connected from K3s pod
- **Secrets:** All required secrets present in `paless-secret`
  - db-password
  - paperless-app-password

## 6. Database Resource Usage

### Current Storage
- **Database Size:** 13 MB
- **Allocated Storage:** 10 Gi (PVC)
- **Utilization:** < 1%
- **Storage Class:** local-path

### Connection Pool Settings
- **max_connections:** 100
- **Current Connections:** ~5-10 (estimated from active pods)
- **Recommendation:** Current settings adequate for multi-tenant workload

### Resource Limits (from StatefulSet)
**Requests:**
- Memory: 256Mi
- CPU: 250m

**Limits:**
- Memory: 1Gi
- CPU: 1000m

**Assessment:** Resource allocation is appropriate for current workload

## 7. Schema Export

**Status:** ✅ COMPLETED

- **File:** `/tmp/paperless_schema_baseline.sql`
- **Size:** 209 KB
- **Contents:** Complete schema-only dump including:
  - All table definitions
  - Indexes
  - Constraints
  - Extensions (pgcrypto, uuid-ossp)
  - Foreign keys
  - Sequences

This baseline schema will be used for:
- Migration planning
- Rollback procedures
- Schema comparison after tenant_id column additions

## 8. Connection Pooling Requirements

### Current Setup
- Direct connections from Django application pods
- No connection pooler currently deployed

### Recommendations for Multi-Tenant Architecture
1. **PgBouncer Deployment**
   - Connection pooling to handle multiple tenants efficiently
   - Recommended pool_mode: transaction or session
   - Suggested max_client_conn: 500
   - Suggested default_pool_size: 20

2. **Connection String Updates**
   - Applications should connect through PgBouncer
   - Maintain direct connection for admin tasks
   - Configure read replicas if needed

## 9. PostgreSQL Logs Review

**Status:** ✅ NO ERRORS

Checked recent PostgreSQL logs via kubectl - no errors or warnings detected. System is healthy and ready for migration.

## 10. Migration Readiness Checklist

- [x] PostgreSQL version 12 or higher
- [x] uuid-ossp extension installed and tested
- [x] pgcrypto extension installed and tested
- [x] All ModelWithOwner tables identified (11 tables)
- [x] Database connection from K3s pods verified
- [x] Current schema exported to SQL file
- [x] Database resource usage documented
- [x] Connection pooling requirements documented
- [x] No errors in PostgreSQL logs

## 11. Next Steps for Multi-Tenant Implementation

1. **Schema Migration Planning**
   - Add `tenant_id UUID` column to all 11 tables
   - Create foreign key to tenants table
   - Add composite indexes: (tenant_id, id), (tenant_id, owner_id)
   - Update unique constraints to include tenant_id

2. **Tenant Management**
   - Create `tenants` table with tenant metadata
   - Implement tenant registration workflow
   - Set up default tenant for existing data

3. **Application Layer Changes**
   - Update Django ORM queries to filter by tenant_id
   - Implement tenant middleware for automatic filtering
   - Update model save() methods to set tenant_id

4. **Testing Strategy**
   - Test data isolation between tenants
   - Performance testing with multiple tenants
   - Backup/restore testing per tenant

## Appendix A: Table Structure Summary

| Table Name | Primary Key | Has owner_id | Has Foreign Keys | Estimated Rows |
|------------|-------------|--------------|------------------|----------------|
| documents_correspondent | id | Yes | tags, user | 0 |
| documents_document | id | Yes | correspondent, type, storage_path, owner, tags | 0 |
| documents_documenttype | id | Yes | tags, user | 0 |
| documents_storagepath | id | Yes | tags, user | 0 |
| documents_tag | id | Yes | parent, user | 0 |
| documents_paperlesstask | id | Yes | user | 0 |
| documents_savedview | id | Yes | user | 0 |
| documents_sharelink | id | Yes | document, user | 0 |
| paperless_mail_mailaccount | id | Yes | user | 0 |
| paperless_mail_mailrule | id | Yes | account, user | 0 |
| paperless_mail_processedmail | id | Yes | rule, user | 0 |

## Appendix B: Database Configuration

```yaml
StatefulSet: postgres
Image: postgres:18
Database: paperless
User: paperless
Port: 5432
Service: postgres.paless.svc.cluster.local
PVC: postgres-data (10Gi, local-path)
```

## Conclusion

The PostgreSQL database is fully prepared for multi-tenant architecture implementation. All acceptance criteria have been met:

✅ PostgreSQL 18.1 verified (requirement: 12+)
✅ Extensions installed and tested (uuid-ossp, pgcrypto)
✅ 11 tables with ModelWithOwner identified and documented
✅ Database connection from K3s verified
✅ Schema exported (209 KB baseline)
✅ Resource usage documented (13 MB used, 100 max connections)
✅ Connection pooling requirements documented
✅ No PostgreSQL errors detected

The database is ready to proceed with multi-tenant schema modifications.
