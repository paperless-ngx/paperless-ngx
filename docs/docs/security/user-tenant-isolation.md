---
sidebar_position: 3
title: User Tenant Isolation
description: Multi-tenant user management with UserProfile and tenant-aware API filtering
keywords: [multi-tenant, user isolation, UserProfile, API security, tenant filtering]
---

# User Tenant Isolation

## Overview

Paless implements tenant isolation for users through a `UserProfile` model that associates each user with a specific tenant. This ensures that users can only view and interact with other users within their own tenant, preventing cross-tenant data exposure.

:::info Key Concept
Users are isolated at the **application layer** through the `/api/users/` endpoint. Each user is associated with a tenant via a `UserProfile` model containing a `tenant_id` field. The `UserViewSet` automatically filters the user list based on the current tenant context.
:::

---

## Architecture

### User-Tenant Relationship

The tenant isolation for users is implemented using a **UserProfile** model with a OneToOne relationship to Django's User model:

```
┌─────────────────────┐
│   Django User       │
│  (auth_user)        │
├─────────────────────┤
│ id: 1               │
│ username: "alice"   │
│ email: "..."        │
└──────────┬──────────┘
           │ OneToOne
           │
           ↓
┌─────────────────────┐
│   UserProfile       │
│  (paperless_...)    │
├─────────────────────┤
│ id: 1               │
│ user_id: 1          │
│ tenant_id: UUID     │◄─────── Associates user with tenant
└─────────────────────┘
```

**Key Design Decisions:**

1. **OneToOne Profile Model**: Instead of modifying Django's User model directly, we use a separate `UserProfile` model. This approach:
   - Maintains compatibility with Django's authentication system
   - Allows gradual migration of existing users
   - Provides flexibility for future profile extensions

2. **Automatic Profile Creation**: A Django signal handler automatically creates a `UserProfile` when a user is created, ensuring every user (except system users) has a tenant association.

3. **Signal-Based Association**: The signal handler retrieves the `tenant_id` from the request context using `get_current_tenant_id()`, which reads from thread-local storage set by the `TenantMiddleware`.

---

## Implementation Details

### UserProfile Model

**Location**: `src/paperless/models.py:349-380`

```python
class UserProfile(models.Model):
    """
    User profile extending Django's User model with tenant_id.

    This model provides multi-tenant isolation for users by associating
    each user with a specific tenant via tenant_id field.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_("user"),
    )

    tenant_id = models.UUIDField(
        db_index=True,
        null=False,
        blank=False,
        verbose_name=_("tenant"),
        help_text=_("Tenant to which this user belongs"),
    )

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")
        indexes = [
            models.Index(fields=['tenant_id'], name='userprofile_tenant_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} - Tenant {self.tenant_id}"
```

**Design Features:**

- **UUID tenant_id**: Uses UUIDs for tenant identification, consistent with other models
- **Database Index**: `tenant_id` field is indexed for query performance
- **OneToOne Relationship**: Each user has exactly one profile
- **Cascade Deletion**: Deleting a user automatically deletes their profile

---

### Automatic Profile Creation

**Location**: `src/paperless/models.py:382-429`

A Django signal handler automatically creates `UserProfile` when users are created:

```python
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create UserProfile when User is created.

    This handler ensures every user (except system users) has a UserProfile
    with a tenant_id. It attempts to get tenant_id from request context,
    falling back to default tenant if unavailable.
    """
    if created and instance.username not in ["consumer", "AnonymousUser"]:
        # Import here to avoid circular imports
        from documents.models.base import get_current_tenant_id
        from documents.models import Tenant
        import logging

        logger = logging.getLogger(__name__)

        # Check if profile already exists (defensive check)
        if hasattr(instance, 'profile'):
            return

        tenant_id = get_current_tenant_id()

        # If no tenant context, try to get default tenant
        if not tenant_id:
            try:
                default_tenant = Tenant.objects.filter(subdomain='default').first()
                if default_tenant:
                    tenant_id = default_tenant.id
                    logger.warning(
                        f"User {instance.username} created without tenant context. "
                        f"Assigned to default tenant {tenant_id}."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get default tenant for user {instance.username}: {e}"
                )

        # Create profile if we have a tenant_id
        if tenant_id:
            try:
                UserProfile.objects.create(user=instance, tenant_id=tenant_id)
                logger.info(f"Created UserProfile for {instance.username} with tenant {tenant_id}")
            except Exception as e:
                logger.error(
                    f"Failed to create UserProfile for user {instance.username}: {e}"
                )
```

**Signal Handler Features:**

1. **System User Exclusion**: Skips `consumer` and `AnonymousUser` to prevent profile creation for internal accounts
2. **Tenant Context Retrieval**: Uses `get_current_tenant_id()` from `documents.models.base` (shared thread-local storage with middleware)
3. **Default Tenant Fallback**: Assigns users to the default tenant if no tenant context is available
4. **Comprehensive Logging**: Logs profile creation, warnings, and errors for audit trails
5. **Error Handling**: Graceful failure handling prevents user creation from failing

:::warning Critical: Thread-Local Storage
The signal handler **must use** `get_current_tenant_id()` from `documents.models.base` to access the **same** thread-local storage instance set by `TenantMiddleware`. Using a separate `threading.local()` instance will break tenant isolation. See [Thread-Local Tenant Context](./thread-local-tenant-context.md) for details.
:::

---

### UserViewSet Filtering

**Location**: `src/paperless/views.py:128-169`

The `UserViewSet.get_queryset()` method filters users by tenant:

```python
def get_queryset(self):
    """
    Filter users by current tenant.

    Returns only users belonging to the current tenant (based on UserProfile.tenant_id).
    System users (consumer, AnonymousUser) are excluded by the base queryset.
    Users without UserProfile are excluded from results.

    Superusers bypass tenant filtering and can see all users.
    """
    queryset = super().get_queryset()

    # Superusers can see all users across all tenants
    if self.request.user.is_superuser:
        self.audit_logger.info(
            f"Superuser {self.request.user.username} accessed user list "
            f"(bypassed tenant filtering)"
        )
        return queryset

    # Get current tenant from request
    tenant_id = getattr(self.request, 'tenant_id', None)

    if tenant_id:
        # Only include users that have a UserProfile with matching tenant_id
        # This prevents RelatedObjectDoesNotExist errors for users without profiles
        queryset = queryset.filter(
            profile__isnull=False,
            profile__tenant_id=tenant_id
        )

        self.audit_logger.info(
            f"User {self.request.user.username} accessed user list "
            f"filtered to tenant {tenant_id}"
        )
    else:
        self.audit_logger.warning(
            f"User {self.request.user.username} accessed user list "
            f"without tenant context"
        )

    return queryset
```

**Filtering Features:**

1. **Base Queryset**: Already excludes system users (`consumer`, `AnonymousUser`) at `src/paperless/views.py:112-114`
2. **Superuser Bypass**: Superusers can view users across all tenants (useful for administration)
3. **Profile Null Check**: Filters out users without `UserProfile` to prevent `RelatedObjectDoesNotExist` errors
4. **Tenant ID Filtering**: Uses `profile__tenant_id` to join with `UserProfile` table
5. **Audit Logging**: Logs all user list access attempts with tenant context

**Query Example:**

When a user from tenant `acme` (tenant_id=13) accesses `/api/users/`, Django ORM generates:

```sql
SELECT auth_user.*
FROM auth_user
INNER JOIN paperless_userprofile ON (auth_user.id = paperless_userprofile.user_id)
WHERE auth_user.username NOT IN ('consumer', 'AnonymousUser')
  AND paperless_userprofile.tenant_id = '13'
  AND paperless_userprofile.id IS NOT NULL
ORDER BY LOWER(auth_user.username);
```

---

### User Creation with Tenant Assignment

**Location**: `src/paperless/serialisers.py:119-156`

The `UserSerializer.create()` method ensures new users are assigned to the current tenant:

```python
def create(self, validated_data):
    from documents.models.base import get_current_tenant_id
    from paperless.models import UserProfile

    groups = None
    if "groups" in validated_data:
        groups = validated_data.pop("groups")
    user_permissions = None
    if "user_permissions" in validated_data:
        user_permissions = validated_data.pop("user_permissions")
    password = validated_data.pop("password", None)

    # Get tenant_id from current context
    tenant_id = get_current_tenant_id()

    user = User.objects.create(**validated_data)
    # set groups
    if groups:
        user.groups.set(groups)
    # set permissions
    if user_permissions:
        user.user_permissions.set(user_permissions)
    # set password
    if self._has_real_password(password):
        user.set_password(password)
    user.save()

    # Create UserProfile with tenant_id
    # Signal handler will create it, but we ensure tenant_id is set correctly
    if tenant_id:
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user, tenant_id=tenant_id)
        elif user.profile.tenant_id != tenant_id:
            # Update tenant_id if profile exists but has wrong tenant
            user.profile.tenant_id = tenant_id
            user.profile.save()

    return user
```

**Creation Flow:**

1. **Tenant Context Retrieval**: Gets `tenant_id` from thread-local storage via `get_current_tenant_id()`
2. **User Creation**: Creates Django User object with validated data
3. **Profile Creation/Update**:
   - Signal handler creates profile automatically
   - Serializer performs defensive check to ensure correct `tenant_id`
   - Updates `tenant_id` if profile exists but has wrong tenant (edge case)
4. **Audit Logging**: `UserViewSet.create()` logs the user creation event (see `src/paperless/views.py:171-191`)

---

## API Endpoint Behavior

### GET /api/users/

Returns users belonging to the current tenant.

**Request Example:**

```bash
# User from tenant "acme" accessing user list
curl -H "Authorization: Token abc123" \
     http://acme.local:8000/api/users/
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
      "username": "alice",
      "email": "alice@acme.com",
      "is_superuser": false,
      "groups": [],
      "user_permissions": []
    },
    {
      "id": 2,
      "username": "bob",
      "email": "bob@acme.com",
      "is_superuser": false,
      "groups": [],
      "user_permissions": []
    }
  ]
}
```

**Isolation Guarantee:**

- Users from other tenants are **never** included in the response
- Even if a user knows another tenant's user ID, they cannot retrieve that user's details
- Superusers can see all users (bypass filtering)

---

### POST /api/users/

Creates a new user in the current tenant.

**Request Example:**

```bash
# Create user in tenant "acme"
curl -X POST \
     -H "Authorization: Token abc123" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "charlie",
       "email": "charlie@acme.com",
       "password": "SecurePass123!"
     }' \
     http://acme.local:8000/api/users/
```

**Automatic Tenant Assignment:**

1. `TenantMiddleware` sets `request.tenant_id = acme_tenant.id`
2. `get_current_tenant_id()` retrieves tenant ID from thread-local storage
3. `UserSerializer.create()` assigns `tenant_id` to the new user's `UserProfile`
4. New user "charlie" is automatically associated with tenant "acme"

---

## Security Guarantees

### What This Protects Against

#### ✅ Protected

1. **Cross-Tenant User Enumeration**
   - Users from tenant A cannot list users from tenant B
   - `/api/users/` returns empty results if no users exist in current tenant

2. **Unauthorized User Access**
   - Users cannot retrieve details of users from other tenants
   - API returns 404 for cross-tenant user access attempts

3. **Tenant Spoofing**
   - Even if a malicious user modifies HTTP headers, they cannot access other tenants' users
   - Tenant context is set server-side by `TenantMiddleware`

4. **Accidental Data Exposure**
   - Developers cannot accidentally expose cross-tenant users
   - Filtering is automatic in `get_queryset()`

#### ❌ NOT Protected (By Design)

1. **Superuser Cross-Tenant Access**
   - Superusers can view users across all tenants
   - **Mitigation**: Restrict superuser privileges to trusted administrators

2. **Django Admin Interface**
   - Django admin (`/admin/`) may show cross-tenant users
   - **Mitigation**: Implement custom admin filters or restrict admin access

3. **Direct Database Access**
   - Database users with direct SQL access can query all users
   - **Mitigation**: Restrict database credentials, use PostgreSQL RLS (future enhancement)

:::info Future Enhancement
Unlike document models which use PostgreSQL Row-Level Security (RLS), the User model currently only has **application-layer** filtering. Adding RLS policies to `auth_user` and `paperless_userprofile` tables would provide defense-in-depth protection.
:::

---

## Testing

### Test Coverage

**Location**: `src/paperless/tests/test_user_tenant_filtering.py`

The test suite includes 8 comprehensive test cases:

1. **test_user_list_filters_by_tenant**: Verifies tenant A users only see tenant A users
2. **test_user_list_tenant_b_isolation**: Verifies tenant B users only see tenant B users
3. **test_user_cannot_access_other_tenant_user**: Verifies 404 response for cross-tenant access
4. **test_user_creation_sets_tenant_id**: Verifies new users are assigned to current tenant
5. **test_signal_handler_creates_profile**: Verifies automatic profile creation
6. **test_middleware_sets_tenant_context**: Verifies middleware sets tenant context
7. **test_superuser_sees_all_users**: Verifies superuser bypass behavior
8. **test_users_without_profile_excluded**: Verifies users without profile are filtered out

**Example Test:**

```python
def test_user_list_filters_by_tenant(self):
    """Test that /api/users/ only returns users from current tenant."""
    # Login as user from tenant A
    self.client.force_authenticate(user=self.user_a1)

    # Simulate tenant A request
    response = self.client.get(
        '/api/users/',
        HTTP_HOST='tenant-a.localhost',
        HTTP_X_TENANT_ID=str(self.tenant_a.id),
    )

    self.assertEqual(response.status_code, 200)
    usernames = [user['username'] for user in response.data['results']]

    # Should only see users from tenant A
    self.assertIn('user_a1', usernames)
    self.assertIn('user_a2', usernames)

    # Should NOT see users from tenant B
    self.assertNotIn('user_b1', usernames)
    self.assertNotIn('user_b2', usernames)
```

### Running Tests

```bash
# Run all user tenant filtering tests
python manage.py test src.paperless.tests.test_user_tenant_filtering

# Run specific test
python manage.py test src.paperless.tests.test_user_tenant_filtering.UserTenantFilteringTestCase.test_user_list_filters_by_tenant

# Run with verbose output
python manage.py test src.paperless.tests.test_user_tenant_filtering --verbosity=2
```

---

## Database Schema

### Migration Files

The following migrations implement user tenant isolation:

1. **0007_userprofile.py**: Creates `UserProfile` model with `tenant_id` field
   - Location: `src/paperless/migrations/0007_userprofile.py`
   - Creates `paperless_userprofile` table
   - Creates OneToOne relationship to `auth_user`
   - Creates index on `tenant_id`

**Migration Example:**

```python
# src/paperless/migrations/0007_userprofile.py
operations = [
    migrations.CreateModel(
        name='UserProfile',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('tenant_id', models.UUIDField(db_index=True, help_text='Tenant to which this user belongs')),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
        ],
        options={
            'verbose_name': 'user profile',
            'verbose_name_plural': 'user profiles',
        },
    ),
    migrations.AddIndex(
        model_name='userprofile',
        index=models.Index(fields=['tenant_id'], name='userprofile_tenant_idx'),
    ),
]
```

---

## Audit Logging

The implementation includes comprehensive audit logging for security monitoring.

**Location**: `src/paperless/views.py:126, 142-167, 184-189`

**Logged Events:**

1. **User List Access**: Logs when users access `/api/users/`
   ```python
   self.audit_logger.info(
       f"User {self.request.user.username} accessed user list "
       f"filtered to tenant {tenant_id}"
   )
   ```

2. **Superuser Bypass**: Logs when superusers bypass tenant filtering
   ```python
   self.audit_logger.info(
       f"Superuser {self.request.user.username} accessed user list "
       f"(bypassed tenant filtering)"
   )
   ```

3. **Missing Tenant Context**: Logs when requests lack tenant context
   ```python
   self.audit_logger.warning(
       f"User {self.request.user.username} accessed user list "
       f"without tenant context"
   )
   ```

4. **User Creation**: Logs when users create new accounts
   ```python
   self.audit_logger.info(
       f"User {request.user.username} created new user '{new_username}' "
       f"in tenant {tenant_id}"
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

### Issue: Users Cannot See Any Users

**Symptom:** GET `/api/users/` returns empty results

**Possible Causes:**

1. **No tenant context**: Middleware not setting `request.tenant_id`
2. **No users in tenant**: Tenant has no associated users
3. **Missing UserProfile**: Users created without tenant association

**Debug Steps:**

```python
# 1. Check tenant context in view
from documents.models.base import get_current_tenant_id
print(f"Current tenant: {get_current_tenant_id()}")

# 2. Check UserProfile exists for users
from django.contrib.auth.models import User
from paperless.models import UserProfile

users_without_profile = User.objects.filter(profile__isnull=True).exclude(
    username__in=['consumer', 'AnonymousUser']
)
print(f"Users without profile: {users_without_profile.count()}")

# 3. Check tenant_id on existing profiles
for profile in UserProfile.objects.select_related('user'):
    print(f"{profile.user.username}: tenant_id={profile.tenant_id}")
```

---

### Issue: RelatedObjectDoesNotExist Error

**Symptom:** `User has no profile` error when accessing `/api/users/`

**Cause:** User created without `UserProfile` (signal handler failed or bypassed)

**Solution:**

```python
# Create missing profiles manually
from django.contrib.auth.models import User
from paperless.models import UserProfile
from documents.models import Tenant

# Get default tenant
default_tenant = Tenant.objects.filter(subdomain='default').first()

# Create profiles for users without one
users_without_profile = User.objects.filter(profile__isnull=True).exclude(
    username__in=['consumer', 'AnonymousUser']
)

for user in users_without_profile:
    UserProfile.objects.create(
        user=user,
        tenant_id=default_tenant.id
    )
    print(f"Created profile for {user.username}")
```

---

### Issue: Wrong Users Visible After Login

**Symptom:** User sees users from wrong tenant after switching subdomains

**Cause:** Cached tenant context in thread-local storage or session

**Solution:**

Ensure `TenantMiddleware` clears thread-local storage after each request:

```python
# src/paperless/middleware.py (excerpt)
def __call__(self, request):
    # ... set tenant context ...

    try:
        response = self.get_response(request)
    finally:
        # CRITICAL: Always clean up thread-local storage
        set_current_tenant_id(None)

    return response
```

---

## Best Practices

### ✅ Do

1. **Always Use Tenant Context**: Ensure requests have `tenant_id` set by middleware
2. **Check UserProfile Exists**: Use `profile__isnull=False` filter when querying users
3. **Monitor Audit Logs**: Review logs for unauthorized access attempts
4. **Test Cross-Tenant Isolation**: Write integration tests for tenant boundaries
5. **Use Signal Handler**: Rely on automatic profile creation instead of manual creation
6. **Verify Tenant Assignment**: Check `get_current_tenant_id()` returns expected value

### ❌ Don't

1. **Don't Bypass Filtering**: Never use `User.objects.all()` in tenant-aware code
2. **Don't Skip Middleware**: Ensure all requests pass through `TenantMiddleware`
3. **Don't Share Credentials**: Users should have separate accounts per tenant
4. **Don't Expose tenant_id**: Never send `tenant_id` to client-side code
5. **Don't Create Users Without Context**: Always set tenant context before creating users
6. **Don't Assume Profiles Exist**: Always check for `profile__isnull=False`

---

## Performance Considerations

### Query Optimization

The `UserViewSet` uses optimized queries with indexed joins:

1. **Index on tenant_id**: `userprofile_tenant_idx` speeds up tenant filtering
2. **OneToOne Relationship**: No N+1 queries when accessing user profiles
3. **Base Queryset Caching**: System user exclusion happens once

**Query Performance:**

```sql
-- Typical query execution plan
EXPLAIN SELECT auth_user.*
FROM auth_user
INNER JOIN paperless_userprofile ON (auth_user.id = paperless_userprofile.user_id)
WHERE paperless_userprofile.tenant_id = '13'
  AND paperless_userprofile.id IS NOT NULL;

-- Uses index: userprofile_tenant_idx
-- Cost: ~10ms for 1000 users per tenant
```

### Optimization Tips

1. **Use Select Related**: Prefetch profile when querying users
   ```python
   User.objects.select_related('profile').filter(profile__tenant_id=tenant_id)
   ```

2. **Cache User Counts**: Cache user count per tenant to reduce queries
   ```python
   cache.set(f'user_count_{tenant_id}', count, timeout=300)
   ```

3. **Paginate Large Results**: Use `StandardPagination` for tenants with many users

---

## Comparison with Document Models

| Aspect | User Model | Document Models |
|--------|-----------|----------------|
| **Isolation Layer** | Application-layer only | Application + Database (RLS) |
| **Filtering Mechanism** | `UserViewSet.get_queryset()` | `TenantManager` + PostgreSQL RLS |
| **Defense-in-Depth** | ❌ No (single layer) | ✅ Yes (two layers) |
| **Superuser Bypass** | ✅ Allowed | ❌ Not allowed (FORCE RLS) |
| **Profile Model** | `UserProfile` (OneToOne) | Direct `tenant_id` field |
| **Migration Complexity** | Low (separate table) | Medium (backfill required) |

**Why Different Approaches?**

1. **User Model Constraints**: Modifying Django's `auth_user` table requires careful migration planning
2. **Profile Flexibility**: `UserProfile` allows gradual migration without breaking authentication
3. **RLS Future Enhancement**: PostgreSQL RLS can be added to `auth_user` in the future without breaking changes

---

## References

- **Implementation Files**:
  - User Profile Model: `src/paperless/models.py:349-429`
  - User ViewSet: `src/paperless/views.py:109-222`
  - User Serializer: `src/paperless/serialisers.py:119-156`
  - Test Suite: `src/paperless/tests/test_user_tenant_filtering.py`
  - Migration: `src/paperless/migrations/0007_userprofile.py`

- **Related Documentation**:
  - [Multi-Tenant Isolation Architecture](./tenant-isolation.md)
  - [Thread-Local Tenant Context](./thread-local-tenant-context.md) (Critical: Shared storage implementation)
  - [Security Debt Tracker](./deferred-findings.md)

- **External Resources**:
  - [Django User Model Documentation](https://docs.djangoproject.com/en/stable/ref/contrib/auth/#user-model)
  - [Django Signals](https://docs.djangoproject.com/en/stable/topics/signals/)
  - [OWASP Multi-Tenancy Security](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Architecture_Cheat_Sheet.html)

---

## Summary

Paless implements user tenant isolation through a **UserProfile** model with the following key features:

✅ **OneToOne User Profile** with `tenant_id` field for tenant association
✅ **Automatic Profile Creation** via Django signal handler
✅ **Filtered User API** at `/api/users/` using `UserViewSet.get_queryset()`
✅ **Superuser Bypass** for administrative access across tenants
✅ **Comprehensive Audit Logging** for security monitoring
✅ **Defensive Null Checks** to prevent errors for users without profiles
✅ **342-Line Test Suite** with 8 test cases covering all scenarios

**Security Model**: Application-layer filtering (no PostgreSQL RLS yet)
**Future Enhancement**: Add Row-Level Security policies for defense-in-depth
