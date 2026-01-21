---
sidebar_position: 4
title: Group Tenant Isolation
description: Multi-tenant group management with TenantGroup model and tenant-aware API filtering
keywords: [multi-tenant, group isolation, TenantGroup, API security, tenant filtering, permissions]
---

# Group Tenant Isolation

## Overview

Paless implements tenant isolation for groups through a `TenantGroup` model that provides automatic tenant-scoped group management. This ensures that groups can only be viewed and modified within their own tenant, preventing cross-tenant access to group configurations and permissions.

:::info Key Concept
Groups are isolated using the **TenantGroup** model which inherits from `ModelWithOwner`. This provides automatic tenant filtering via `TenantManager` and integrates with the shared thread-local tenant context. The `/api/groups/` endpoint automatically filters groups based on the current tenant context.
:::

---

## Architecture

### TenantGroup Model Design

The tenant isolation for groups is implemented using a **TenantGroup** model that replaces Django's standard `Group` model:

```
┌─────────────────────────────┐
│   Django Permission         │
│  (auth_permission)          │
├─────────────────────────────┤
│ id: 1                       │
│ codename: "add_document"    │
│ content_type_id: 5          │
└──────────┬──────────────────┘
           │ ManyToMany
           │
           ↓
┌─────────────────────────────┐
│   TenantGroup               │
│  (documents_tenantgroup)    │
├─────────────────────────────┤
│ id: 1                       │
│ name: "Editors"             │
│ tenant_id: UUID             │◄─────── Associates group with tenant
│ owner_id: 5 (optional)      │◄─────── Tracks who created the group
└─────────────────────────────┘
```

**Key Design Decisions:**

1. **Inherits from ModelWithOwner**: Provides automatic tenant isolation through:
   - `tenant_id` field (UUIDField with database index)
   - `TenantManager` for automatic query filtering
   - `owner` field for audit tracking
   - Automatic tenant_id population from thread-local context

2. **Replaces Django Group Model**: Uses `TenantGroup` instead of `django.contrib.auth.models.Group` to ensure all groups are tenant-scoped from the start

3. **Permission Compatibility**: Uses `related_name="tenant_groups"` to avoid conflicts with Django's Group model while maintaining M2M relationship with permissions

4. **Unique Name Constraint**: Group names are unique within a tenant (`unique_together = [["tenant_id", "name"]]`), but different tenants can have groups with the same name

---

## Implementation Details

### TenantGroup Model

**Location**: `src/documents/models/tenant_group.py:14-66`

```python
class TenantGroup(ModelWithOwner):
    """
    Tenant-aware group model that provides automatic tenant isolation.

    This model replaces django.contrib.auth.models.Group for tenant-scoped
    group management. It inherits from ModelWithOwner to get:
    - Automatic tenant_id field
    - TenantManager for automatic tenant filtering
    - owner field for tracking who created the group

    All queries using TenantGroup.objects will be automatically filtered
    by the current tenant context set by TenantMiddleware.
    """

    name = models.CharField(
        max_length=150,
        verbose_name=_("name"),
        help_text=_("The name of the group within this tenant"),
    )

    # Many-to-many relationship for permissions
    permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_("permissions"),
        blank=True,
        related_name="tenant_groups",
    )

    class Meta:
        verbose_name = _("tenant group")
        verbose_name_plural = _("tenant groups")
        # Ensure group names are unique within a tenant
        unique_together = [["tenant_id", "name"]]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def natural_key(self):
        """Return natural key for serialization."""
        return (self.name, str(self.tenant_id))
```

**Model Features:**

- **Inherited Fields from ModelWithOwner**:
  - `tenant_id`: UUIDField (indexed, non-nullable)
  - `owner`: ForeignKey to User (optional, nullable)
  - `created_at`: DateTimeField (auto-generated)
  - `modified_at`: DateTimeField (auto-updated)

- **TenantManager Integration**: The `objects` manager automatically filters by tenant_id from thread-local context
- **Natural Key**: Combines name and tenant_id for serialization uniqueness
- **Ordering**: Groups ordered alphabetically by name
- **Permissions**: Standard Django permission model (unchanged)

:::info ModelWithOwner
`ModelWithOwner` is defined in `src/paperless/models.py` and provides the foundation for all tenant-aware models. It includes:
- Automatic `tenant_id` population via `save()` override
- `TenantManager` as default manager (filters by tenant)
- `all_objects` manager (bypasses tenant filtering, for superusers)

For more details, see the [Tenant-Aware Models](../development/tenant-aware-models.md) documentation.
:::

---

### GroupViewSet Filtering

**Location**: `src/paperless/views.py:251-299`

The `GroupViewSet` handles all API operations for groups with automatic tenant filtering:

```python
class GroupViewSet(ModelViewSet):
    """
    ViewSet for managing tenant-scoped groups.

    Groups are automatically filtered by current tenant context.
    Only groups belonging to the current tenant are visible and can be modified.
    Creating a group automatically sets tenant_id from request context.
    """
    model = TenantGroup
    queryset = TenantGroup.objects.order_by(Lower("name"))
    serializer_class = GroupSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    def get_queryset(self):
        """
        Filter groups by current tenant.

        Returns only groups belonging to the current tenant via TenantManager.
        The TenantGroup model's default 'objects' manager automatically filters
        by tenant_id from thread-local context.

        Superusers bypass tenant filtering and can see all groups.
        """
        queryset = super().get_queryset()

        # Superusers can see all groups across all tenants
        if self.request.user.is_superuser:
            queryset = TenantGroup.all_objects.order_by(Lower("name"))
            self.audit_logger.info(
                f"Superuser {self.request.user.username} accessed group list "
                f"(bypassed tenant filtering)"
            )
        else:
            tenant_id = getattr(self.request, 'tenant_id', None)
            self.audit_logger.info(
                f"User {self.request.user.username} accessed group list "
                f"filtered to tenant {tenant_id}"
            )

        return queryset
```

**Filtering Features:**

1. **Automatic Tenant Filtering**: `TenantGroup.objects` automatically filters by tenant_id from thread-local context
2. **Superuser Bypass**: Superusers use `TenantGroup.all_objects` to see all groups across tenants
3. **Audit Logging**: All group access attempts logged to `paperless.audit.tenant`
4. **TenantManager**: Leverages shared thread-local storage from `documents.models.base`

**Query Example:**

When a user from tenant `acme` (tenant_id=13) accesses `/api/groups/`, the TenantManager generates:

```sql
SELECT documents_tenantgroup.*
FROM documents_tenantgroup
WHERE documents_tenantgroup.tenant_id = '13'
ORDER BY LOWER(documents_tenantgroup.name);
```

:::warning Critical: Thread-Local Storage
The `TenantManager` **must use** `get_current_tenant_id()` from `documents.models.base` to access the **same** thread-local storage instance set by `TenantMiddleware`. Using a separate `threading.local()` instance will break tenant isolation. See [Thread-Local Tenant Context](./thread-local-tenant-context.md) for details.
:::

---

### GroupSerializer

**Location**: `src/paperless/serialisers.py:159-174`

The `GroupSerializer` handles group serialization with tenant awareness:

```python
class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True,
        queryset=Permission.objects.exclude(content_type__app_label="admin"),
        slug_field="codename",
    )

    class Meta:
        model = TenantGroup
        fields = (
            "id",
            "name",
            "permissions",
        )
        read_only_fields = ("tenant_id",)
```

**Serializer Features:**

1. **Read-Only tenant_id**: The `tenant_id` field is automatically set from request context and cannot be modified by users
2. **Permission Codenames**: Uses slug field for cleaner API (e.g., "add_document" instead of permission ID)
3. **Admin Exclusion**: Excludes admin app permissions from the queryset for security
4. **Automatic Creation**: When creating a group, the `ModelWithOwner.save()` method automatically populates `tenant_id` from thread-local context

---

## API Endpoint Behavior

### GET /api/groups/

Returns groups belonging to the current tenant.

**Request Example:**

```bash
# User from tenant "acme" accessing group list
curl -H "Authorization: Token abc123" \
     http://acme.local:8000/api/groups/
```

**Response Example:**

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Editors",
      "permissions": ["add_document", "change_document", "view_document"]
    },
    {
      "id": 2,
      "name": "Viewers",
      "permissions": ["view_document"]
    }
  ]
}
```

**Isolation Guarantee:**

- Groups from other tenants are **never** included in the response
- Even if a user knows another tenant's group ID, they cannot retrieve that group's details
- Superusers can see all groups (bypass filtering)

---

### POST /api/groups/

Creates a new group in the current tenant.

**Request Example:**

```bash
# Create group in tenant "acme"
curl -X POST \
     -H "Authorization: Token abc123" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Administrators",
       "permissions": ["add_document", "change_document", "delete_document"]
     }' \
     http://acme.local:8000/api/groups/
```

**Automatic Tenant Assignment:**

1. `TenantMiddleware` sets `request.tenant_id = acme_tenant.id` in thread-local storage
2. `GroupSerializer` creates new `TenantGroup` instance
3. `ModelWithOwner.save()` calls `get_current_tenant_id()` to retrieve tenant_id
4. New group is automatically associated with tenant "acme"

**Response Example:**

```json
{
  "id": 3,
  "name": "Administrators",
  "permissions": ["add_document", "change_document", "delete_document"]
}
```

---

### PUT/PATCH /api/groups/{id}/

Updates an existing group within the current tenant.

**Request Example:**

```bash
# Update group permissions
curl -X PATCH \
     -H "Authorization: Token abc123" \
     -H "Content-Type: application/json" \
     -d '{
       "permissions": ["add_document", "change_document", "delete_document", "view_document"]
     }' \
     http://acme.local:8000/api/groups/1/
```

**Tenant Isolation:**

- Can only update groups within current tenant
- Attempting to access group from another tenant returns 404
- Permissions remain associated with the group

---

### DELETE /api/groups/{id}/

Deletes a group within the current tenant.

**Request Example:**

```bash
# Delete group
curl -X DELETE \
     -H "Authorization: Token abc123" \
     http://acme.local:8000/api/groups/1/
```

**Tenant Isolation:**

- Can only delete groups within current tenant
- Attempting to delete group from another tenant returns 404
- Cascade behavior follows Django's standard group deletion

---

## Migration Strategy

### Migration 1083: TenantGroup Creation

**Location**: `src/documents/migrations/1083_create_tenant_group.py`

This migration handles the transition from Django's global `Group` model to tenant-scoped `TenantGroup`:

**Migration Operations:**

1. **Create TenantGroup Model**:
   - Creates `documents_tenantgroup` table with tenant_id, name, owner fields
   - Creates unique constraint on (tenant_id, name)
   - Creates index on tenant_id for query performance
   - Creates M2M relationship with auth.Permission

2. **Migrate Existing Groups** (`migrate_groups_to_tenant_groups()`):
   - Retrieves default tenant (created in migration 1079)
   - Creates TenantGroup for each existing Group
   - Migrates permissions from Group to TenantGroup
   - Assigns all groups to default tenant

3. **Reverse Migration** (`reverse_migrate_groups()`):
   - Deletes all TenantGroup instances
   - Note: Does NOT restore original Group objects (one-way migration)

**Migration Code Excerpt:**

```python
def migrate_groups_to_tenant_groups(apps, schema_editor):
    """
    Migrate existing Django Group objects to TenantGroup.

    This function:
    1. Gets the default tenant (created in migration 1079)
    2. Creates TenantGroup instances for each existing Group
    3. Migrates permissions from Group to TenantGroup
    """
    Group = apps.get_model('auth', 'Group')
    TenantGroup = apps.get_model('documents', 'TenantGroup')
    Tenant = apps.get_model('documents', 'Tenant')

    # Get the default tenant
    default_tenant = Tenant.objects.first()
    if not default_tenant:
        default_tenant = Tenant.objects.create(
            name='Default Tenant',
            subdomain='default',
            region='us',
        )

    # Migrate each existing Group to TenantGroup
    for group in Group.objects.all():
        tenant_group = TenantGroup.objects.create(
            name=group.name,
            tenant_id=default_tenant.id,
            owner=None,  # No owner for migrated groups
        )

        # Migrate permissions
        for permission in group.permissions.all():
            tenant_group.permissions.add(permission)
```

**Migration Considerations:**

- **Default Tenant**: All existing groups are assigned to the default tenant
- **No Owner**: Migrated groups have `owner=None` (created before tracking)
- **Permission Preservation**: All group permissions are preserved during migration
- **One-Way Migration**: Reverse migration deletes TenantGroup but doesn't restore Group

---

## Security Guarantees

### What This Protects Against

#### ✅ Protected

1. **Cross-Tenant Group Enumeration**
   - Users from tenant A cannot list groups from tenant B
   - `/api/groups/` returns only groups in current tenant

2. **Unauthorized Group Access**
   - Users cannot retrieve details of groups from other tenants
   - API returns 404 for cross-tenant group access attempts

3. **Cross-Tenant Permission Leakage**
   - Group permissions are isolated within tenant boundaries
   - Cannot apply permissions from another tenant's groups

4. **Tenant Spoofing**
   - Even if a malicious user modifies HTTP headers, they cannot access other tenants' groups
   - Tenant context is set server-side by `TenantMiddleware`

5. **Accidental Data Exposure**
   - Developers cannot accidentally expose cross-tenant groups
   - Filtering is automatic via `TenantManager`

6. **Group Name Conflicts**
   - Different tenants can have groups with the same name (e.g., "Editors")
   - Unique constraint is per-tenant, not global

#### ❌ NOT Protected (By Design)

1. **Superuser Cross-Tenant Access**
   - Superusers can view and manage groups across all tenants via `TenantGroup.all_objects`
   - **Mitigation**: Restrict superuser privileges to trusted administrators

2. **Django Admin Interface**
   - Django admin (`/admin/`) may show cross-tenant groups for superusers
   - **Mitigation**: Implement custom admin filters or restrict admin access

3. **Direct Database Access**
   - Database users with direct SQL access can query all groups
   - **Mitigation**: Restrict database credentials, use PostgreSQL RLS (future enhancement)

:::info Future Enhancement
Unlike document models which use PostgreSQL Row-Level Security (RLS), the TenantGroup model currently only has **application-layer** filtering via `TenantManager`. Adding RLS policies to the `documents_tenantgroup` table would provide defense-in-depth protection similar to document models.
:::

---

## Testing

### Test Coverage

**Location**: `src/paperless/tests/test_tenant_group_filtering.py`

The test suite includes comprehensive test cases covering:

1. **test_group_list_filters_by_tenant**: Verifies tenant A users only see tenant A groups
2. **test_group_list_tenant_b_isolation**: Verifies tenant B users only see tenant B groups
3. **test_group_create_sets_tenant_id**: Verifies new groups are assigned to current tenant
4. **test_group_cannot_access_other_tenant_group**: Verifies 404 response for cross-tenant access
5. **test_group_update_respects_tenant**: Verifies updates only work within current tenant
6. **test_group_delete_respects_tenant**: Verifies deletions only work within current tenant
7. **test_superuser_sees_all_groups**: Verifies superuser bypass behavior
8. **test_group_unique_name_per_tenant**: Verifies unique constraint within tenant
9. **test_group_permissions_work**: Verifies permission M2M relationship functions correctly

**Example Test:**

```python
def test_group_list_filters_by_tenant(self):
    """Test that /api/groups/ only returns groups from current tenant."""
    # Create groups in different tenants
    group_a = TenantGroup.objects.create(
        name="Editors",
        tenant_id=self.tenant_a.id
    )
    group_b = TenantGroup.objects.create(
        name="Editors",
        tenant_id=self.tenant_b.id
    )

    # Login as user from tenant A
    self.client.force_authenticate(user=self.user_a)

    # Access groups as tenant A
    response = self.client.get(
        '/api/groups/',
        HTTP_HOST='tenant-a.localhost',
    )

    self.assertEqual(response.status_code, 200)
    group_names = [g['name'] for g in response.data['results']]

    # Should only see groups from tenant A
    self.assertIn(group_a.name, group_names)
    self.assertNotIn(group_b.name, group_names)  # Tenant B group not visible
```

### Running Tests

```bash
# Run all group tenant filtering tests
python manage.py test src.paperless.tests.test_tenant_group_filtering

# Run specific test
python manage.py test src.paperless.tests.test_tenant_group_filtering.TenantGroupFilteringTestCase.test_group_list_filters_by_tenant

# Run with verbose output
python manage.py test src.paperless.tests.test_tenant_group_filtering --verbosity=2
```

---

## Audit Logging

The implementation includes comprehensive audit logging for security monitoring.

**Location**: `src/paperless/views.py:273, 290-298`

**Logged Events:**

1. **Group List Access**: Logs when users access `/api/groups/`
   ```python
   self.audit_logger.info(
       f"User {self.request.user.username} accessed group list "
       f"filtered to tenant {tenant_id}"
   )
   ```

2. **Superuser Bypass**: Logs when superusers bypass tenant filtering
   ```python
   self.audit_logger.info(
       f"Superuser {self.request.user.username} accessed group list "
       f"(bypassed tenant filtering)"
   )
   ```

**Log Configuration:**

Logs are written to the `paperless.audit.tenant` logger. Configure in Django settings:

```python
# settings.py
LOGGING = {
    'loggers': {
        'paperless.audit.tenant': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

## Troubleshooting

### Issue: Groups Not Visible

**Symptom:** GET `/api/groups/` returns empty results

**Possible Causes:**

1. **No tenant context**: Middleware not setting thread-local tenant_id
2. **No groups in tenant**: Tenant has no associated groups
3. **Wrong tenant context**: Thread-local storage points to wrong tenant

**Debug Steps:**

```python
# 1. Check tenant context
from documents.models.base import get_current_tenant_id
print(f"Current tenant: {get_current_tenant_id()}")

# 2. Check groups exist for tenant
from documents.models import TenantGroup
groups = TenantGroup.all_objects.filter(tenant_id='<tenant-uuid>')
print(f"Groups in tenant: {groups.count()}")

# 3. Verify TenantManager filtering
from documents.models import TenantGroup
from documents.models.base import set_current_tenant_id

set_current_tenant_id('<tenant-uuid>')
filtered_groups = TenantGroup.objects.all()
print(f"Filtered groups: {filtered_groups.count()}")
```

---

### Issue: Duplicate Group Name Error

**Symptom:** `IntegrityError: duplicate key value violates unique constraint "documents_tenantgroup_tenant_id_name_<hash>_uniq"`

**Cause:** Attempting to create a group with a name that already exists in the current tenant

**Solution:**

Group names must be unique within a tenant. Either:
1. Choose a different name for the new group
2. Update the existing group instead of creating a new one
3. Delete the existing group before creating a new one with the same name

```python
# Check if group name exists in current tenant
from documents.models import TenantGroup
existing_group = TenantGroup.objects.filter(name="Editors").first()

if existing_group:
    # Update existing group
    existing_group.permissions.set(new_permissions)
    existing_group.save()
else:
    # Create new group
    TenantGroup.objects.create(name="Editors", ...)
```

---

### Issue: Cannot Access Group from Another Tenant

**Symptom:** GET `/api/groups/{id}/` returns 404 for valid group ID

**Cause:** The group belongs to a different tenant than the current user

**Expected Behavior:**

This is correct security behavior. Groups are tenant-isolated and cannot be accessed across tenant boundaries.

**Solution:**

- Verify the user is accessing the correct subdomain for their tenant
- Check that the group ID is correct for the current tenant
- If cross-tenant access is needed, use a superuser account

---

## Best Practices

### ✅ Do

1. **Always Use Tenant Context**: Ensure requests have tenant_id set by middleware
2. **Use TenantGroup.objects**: For tenant-filtered queries (default manager)
3. **Use TenantGroup.all_objects**: Only for superuser operations requiring cross-tenant access
4. **Monitor Audit Logs**: Review logs for unauthorized access attempts
5. **Test Cross-Tenant Isolation**: Write integration tests for tenant boundaries
6. **Rely on Automatic tenant_id**: Let `ModelWithOwner.save()` set tenant_id from context
7. **Use Unique Names per Tenant**: Group names should be descriptive and unique within each tenant

### ❌ Don't

1. **Don't Bypass TenantManager**: Never use `TenantGroup.all_objects` in tenant-aware code (unless superuser)
2. **Don't Skip Middleware**: Ensure all requests pass through `TenantMiddleware`
3. **Don't Manually Set tenant_id**: Let the model automatically populate tenant_id from context
4. **Don't Share Group IDs**: Group IDs are tenant-specific and should not be shared across tenants
5. **Don't Use Django's Group Model**: Always use `TenantGroup` for tenant-aware group management
6. **Don't Assume Global Uniqueness**: Group names are unique per tenant, not globally

---

## Performance Considerations

### Query Optimization

The `TenantManager` uses optimized queries with indexed filtering:

1. **Index on tenant_id**: `tenant_id` field has database index for fast filtering
2. **Automatic Query Filtering**: TenantManager adds WHERE clause at query generation time
3. **Case-Insensitive Ordering**: Uses `Lower("name")` for alphabetical sorting

**Query Performance:**

```sql
-- Typical query execution plan
EXPLAIN SELECT documents_tenantgroup.*
FROM documents_tenantgroup
WHERE documents_tenantgroup.tenant_id = '13'
ORDER BY LOWER(documents_tenantgroup.name);

-- Uses index: documents_tenantgroup_tenant_id_<hash>_idx
-- Cost: ~5ms for 100 groups per tenant
```

### Optimization Tips

1. **Use Select Related for Permissions**: Prefetch permissions when querying groups
   ```python
   groups = TenantGroup.objects.prefetch_related('permissions')
   ```

2. **Cache Group Counts**: Cache group count per tenant to reduce queries
   ```python
   cache.set(f'group_count_{tenant_id}', count, timeout=300)
   ```

3. **Paginate Large Results**: Use `StandardPagination` for tenants with many groups

---

## Comparison with User and Document Models

| Aspect | TenantGroup | User Model | Document Models |
|--------|------------|-----------|----------------|
| **Isolation Layer** | Application-layer (TenantManager) | Application-layer (ViewSet filtering) | Application + Database (RLS) |
| **Filtering Mechanism** | `TenantManager.get_queryset()` | `UserViewSet.get_queryset()` | `TenantManager` + PostgreSQL RLS |
| **Defense-in-Depth** | ❌ No (single layer) | ❌ No (single layer) | ✅ Yes (two layers) |
| **Superuser Bypass** | ✅ Allowed (all_objects) | ✅ Allowed | ❌ Not allowed (FORCE RLS) |
| **Model Design** | Inherits ModelWithOwner | Uses UserProfile (OneToOne) | Direct tenant_id field |
| **Automatic tenant_id** | ✅ Yes (save() override) | ✅ Yes (signal handler) | ✅ Yes (save() override) |

**Why Different from Documents?**

1. **Lower Security Risk**: Groups don't contain sensitive user data (just permissions)
2. **Admin Flexibility**: Superusers need to manage groups across tenants
3. **Performance**: Application-layer filtering is sufficient for group operations
4. **Migration Path**: RLS can be added later without breaking changes

---

## References

- **Implementation Files**:
  - TenantGroup Model: `src/documents/models/tenant_group.py:14-66`
  - GroupViewSet: `src/paperless/views.py:251-299`
  - GroupSerializer: `src/paperless/serialisers.py:159-174`
  - Test Suite: `src/paperless/tests/test_tenant_group_filtering.py`
  - Migration: `src/documents/migrations/1083_create_tenant_group.py`

- **Related Documentation**:
  - [Multi-Tenant Isolation Architecture](./tenant-isolation.md)
  - [Thread-Local Tenant Context](./thread-local-tenant-context.md) - Critical: Shared storage implementation
  - [User Tenant Isolation](./user-tenant-isolation.md)
  - [Tenant-Aware Models](../development/tenant-aware-models.md)
  - [Security Debt Tracker](./deferred-findings.md)

- **External Resources**:
  - [Django Group and Permission System](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization)
  - [OWASP Multi-Tenancy Security](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Architecture_Cheat_Sheet.html)

---

## Summary

Paless implements group tenant isolation through the **TenantGroup** model with the following key features:

✅ **Inherits from ModelWithOwner** for automatic tenant_id field and TenantManager
✅ **Automatic Tenant Filtering** via `TenantGroup.objects` manager
✅ **Unique Names per Tenant** enforced by database constraint
✅ **Permission Compatibility** with Django's auth system
✅ **Superuser Bypass** for administrative access via `TenantGroup.all_objects`
✅ **Comprehensive Audit Logging** for security monitoring
✅ **Migration Strategy** to transition from global Group model
✅ **Extensive Test Coverage** with 9 test cases covering all scenarios

**Security Model**: Application-layer filtering via `TenantManager` (no PostgreSQL RLS)
**Future Enhancement**: Add Row-Level Security policies for defense-in-depth protection
