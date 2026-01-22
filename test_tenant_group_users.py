#!/usr/bin/env python3
"""Test script for TenantGroup users ManyToManyField."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/usr/src/paperless/src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
django.setup()

from django.contrib.auth.models import User
from documents.models import TenantGroup, Tenant
from documents.models.base import set_current_tenant_id

print("=" * 60)
print("Testing TenantGroup users ManyToManyField")
print("=" * 60)

# Get or create a tenant
tenant, created = Tenant.objects.get_or_create(
    name='Test Tenant',
    defaults={
        'subdomain': 'test',
        'region': 'us',
    }
)
print(f"\n✓ Tenant: {tenant.name} (ID: {tenant.id})")

# Set the tenant context (simulating middleware behavior)
set_current_tenant_id(tenant.id)
print(f"✓ Tenant context set to: {tenant.id}")

# Get or create a test user
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
    }
)
print(f"✓ User: {user.username} (ID: {user.id})")

# Create a TenantGroup using the tenant-aware manager
group = TenantGroup.objects.create(
    name='Test Group',
)
print(f"✓ TenantGroup created: {group.name} (ID: {group.id})")

# Test 1: Add user to group
print("\n--- Test 1: Add user to group ---")
group.users.add(user)
print(f"✓ Added user {user.username} to group {group.name}")

# Test 2: Query users in group
print("\n--- Test 2: Query users in group ---")
users_in_group = group.users.all()
print(f"✓ Users in group: {list(users_in_group)}")
assert user in users_in_group, "User should be in group"
print(f"✓ Assertion passed: User is in group")

# Test 3: Query user's tenant groups via related_name
print("\n--- Test 3: Query user's tenant groups ---")
user_tenant_groups = user.tenant_groups.all()
print(f"✓ User's tenant groups: {list(user_tenant_groups)}")
assert group in user_tenant_groups, "Group should be in user's tenant_groups"
print(f"✓ Assertion passed: Group is in user's tenant_groups")

# Test 4: Remove user from group
print("\n--- Test 4: Remove user from group ---")
group.users.remove(user)
print(f"✓ Removed user {user.username} from group {group.name}")
users_in_group_after = group.users.all()
assert user not in users_in_group_after, "User should not be in group"
print(f"✓ Assertion passed: User is not in group anymore")

# Cleanup
print("\n--- Cleanup ---")
group.delete()
print(f"✓ Deleted test group")

print("\n" + "=" * 60)
print("✓ All tests passed!")
print("=" * 60)
