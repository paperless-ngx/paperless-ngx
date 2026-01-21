"""
Tests for tenant-filtered TenantGroup API endpoints.

Verifies that /api/groups/ only returns groups belonging to the current tenant.
"""
import uuid
from django.contrib.auth.models import User, Permission
from django.test import TestCase
from rest_framework.test import APIClient

from documents.models import Tenant, TenantGroup
from documents.models.base import set_current_tenant_id
from paperless.models import UserProfile


class TenantGroupFilteringTestCase(TestCase):
    """Test tenant filtering on TenantGroup API endpoints."""

    def setUp(self):
        """Set up test data with multiple tenants, users, and groups."""
        # Create tenants
        self.tenant_a = Tenant.objects.create(
            subdomain='tenant-a',
            name='Tenant A',
            region='us',
        )
        self.tenant_b = Tenant.objects.create(
            subdomain='tenant-b',
            name='Tenant B',
            region='us',
        )

        # Create users for tenant A
        set_current_tenant_id(self.tenant_a.id)
        self.user_a1 = User.objects.create_user(
            username='user_a1',
            password='testpass123',
            is_superuser=True,
        )
        self.user_a2 = User.objects.create_user(
            username='user_a2',
            password='testpass123',
        )

        # Create users for tenant B
        set_current_tenant_id(self.tenant_b.id)
        self.user_b1 = User.objects.create_user(
            username='user_b1',
            password='testpass123',
        )

        # Create groups for tenant A
        set_current_tenant_id(self.tenant_a.id)
        self.group_a1 = TenantGroup.objects.create(
            name='Editors A',
            tenant_id=self.tenant_a.id,
            owner=self.user_a1,
        )
        self.group_a2 = TenantGroup.objects.create(
            name='Viewers A',
            tenant_id=self.tenant_a.id,
            owner=self.user_a2,
        )

        # Create groups for tenant B
        set_current_tenant_id(self.tenant_b.id)
        self.group_b1 = TenantGroup.objects.create(
            name='Editors B',
            tenant_id=self.tenant_b.id,
            owner=self.user_b1,
        )
        self.group_b2 = TenantGroup.objects.create(
            name='Viewers B',
            tenant_id=self.tenant_b.id,
        )

        # Clear tenant context after setup
        set_current_tenant_id(None)

        self.client = APIClient()

    def test_group_list_filtered_by_tenant_a(self):
        """Test that /api/groups/ only returns Tenant A's groups."""
        self.client.force_authenticate(user=self.user_a2)

        response = self.client.get(
            '/api/groups/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should only return groups from tenant A
        self.assertEqual(data['count'], 2)
        group_names = {g['name'] for g in data['results']}
        self.assertEqual(group_names, {'Editors A', 'Viewers A'})

    def test_group_list_filtered_by_tenant_b(self):
        """Test that /api/groups/ only returns Tenant B's groups."""
        self.client.force_authenticate(user=self.user_b1)

        response = self.client.get(
            '/api/groups/',
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should only return groups from tenant B
        self.assertEqual(data['count'], 2)
        group_names = {g['name'] for g in data['results']}
        self.assertEqual(group_names, {'Editors B', 'Viewers B'})

    def test_group_create_sets_tenant_id(self):
        """Test that creating a group automatically sets tenant_id."""
        self.client.force_authenticate(user=self.user_a2)

        response = self.client.post(
            '/api/groups/',
            {'name': 'New Group A', 'permissions': []},
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
            format='json',
        )

        self.assertEqual(response.status_code, 201)

        # Verify the group was created with correct tenant_id
        set_current_tenant_id(self.tenant_a.id)
        new_group = TenantGroup.objects.get(name='New Group A')
        self.assertEqual(new_group.tenant_id, self.tenant_a.id)
        set_current_tenant_id(None)

    def test_group_cannot_access_other_tenant_group(self):
        """Test that users cannot access groups from other tenants."""
        self.client.force_authenticate(user=self.user_a2)

        # Try to access a group from tenant B while authenticated as tenant A
        response = self.client.get(
            f'/api/groups/{self.group_b1.id}/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Should return 404 since the group doesn't exist in tenant A's context
        self.assertEqual(response.status_code, 404)

    def test_group_superuser_sees_all_groups(self):
        """Test that superusers can see groups from all tenants."""
        self.client.force_authenticate(user=self.user_a1)

        response = self.client.get(
            '/api/groups/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Superuser should see all groups (from both tenants)
        self.assertEqual(data['count'], 4)
        group_names = {g['name'] for g in data['results']}
        self.assertEqual(
            group_names,
            {'Editors A', 'Viewers A', 'Editors B', 'Viewers B'},
        )

    def test_group_unique_name_within_tenant(self):
        """Test that group names must be unique within a tenant."""
        self.client.force_authenticate(user=self.user_a2)

        # Try to create a group with a name that already exists in tenant A
        response = self.client.post(
            '/api/groups/',
            {'name': 'Editors A', 'permissions': []},
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
            format='json',
        )

        # Should fail due to unique constraint
        self.assertEqual(response.status_code, 400)

    def test_group_same_name_different_tenants(self):
        """Test that same group name can exist in different tenants."""
        self.client.force_authenticate(user=self.user_a2)

        # Create a group with name that exists in tenant B
        response = self.client.post(
            '/api/groups/',
            {'name': 'Editors B', 'permissions': []},
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
            format='json',
        )

        # Should succeed since it's a different tenant
        self.assertEqual(response.status_code, 201)

        # Verify both groups exist
        set_current_tenant_id(self.tenant_a.id)
        group_a = TenantGroup.objects.get(name='Editors B')
        self.assertEqual(group_a.tenant_id, self.tenant_a.id)

        set_current_tenant_id(self.tenant_b.id)
        group_b = TenantGroup.objects.get(name='Editors B')
        self.assertEqual(group_b.tenant_id, self.tenant_b.id)

        set_current_tenant_id(None)

    def test_group_permissions_work_correctly(self):
        """Test that group permissions can be assigned and retrieved."""
        self.client.force_authenticate(user=self.user_a2)

        # Get some permissions
        permissions = Permission.objects.filter(
            content_type__app_label='documents',
        )[:2]
        permission_codenames = [p.codename for p in permissions]

        # Create group with permissions
        response = self.client.post(
            '/api/groups/',
            {
                'name': 'Permissioned Group',
                'permissions': permission_codenames,
            },
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()

        # Verify permissions were assigned
        self.assertEqual(
            set(data['permissions']),
            set(permission_codenames),
        )

    def test_group_update_maintains_tenant_id(self):
        """Test that updating a group doesn't change its tenant_id."""
        self.client.force_authenticate(user=self.user_a2)

        original_tenant_id = self.group_a2.tenant_id

        # Update the group name
        response = self.client.patch(
            f'/api/groups/{self.group_a2.id}/',
            {'name': 'Updated Viewers A'},
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
            format='json',
        )

        self.assertEqual(response.status_code, 200)

        # Verify tenant_id didn't change
        set_current_tenant_id(self.tenant_a.id)
        updated_group = TenantGroup.objects.get(id=self.group_a2.id)
        self.assertEqual(updated_group.tenant_id, original_tenant_id)
        self.assertEqual(updated_group.name, 'Updated Viewers A')
        set_current_tenant_id(None)

    def test_group_delete_only_own_tenant(self):
        """Test that users can only delete groups in their own tenant."""
        self.client.force_authenticate(user=self.user_a2)

        # Try to delete a group from tenant B
        response = self.client.delete(
            f'/api/groups/{self.group_b1.id}/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Should fail with 404 (group not found in tenant A's context)
        self.assertEqual(response.status_code, 404)

        # Verify the group still exists
        set_current_tenant_id(self.tenant_b.id)
        self.assertTrue(
            TenantGroup.objects.filter(id=self.group_b1.id).exists(),
        )
        set_current_tenant_id(None)

        # Now delete a group from own tenant
        response = self.client.delete(
            f'/api/groups/{self.group_a2.id}/',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Should succeed
        self.assertEqual(response.status_code, 204)

        # Verify the group was deleted
        set_current_tenant_id(self.tenant_a.id)
        self.assertFalse(
            TenantGroup.objects.filter(id=self.group_a2.id).exists(),
        )
        set_current_tenant_id(None)


class TenantGroupModelTestCase(TestCase):
    """Test TenantGroup model behavior."""

    def setUp(self):
        """Set up test tenant."""
        self.tenant = Tenant.objects.create(
            subdomain='test-tenant',
            name='Test Tenant',
            region='us',
        )
        set_current_tenant_id(self.tenant.id)

    def tearDown(self):
        """Clear tenant context."""
        set_current_tenant_id(None)

    def test_tenant_group_auto_populates_tenant_id(self):
        """Test that TenantGroup automatically populates tenant_id on save."""
        group = TenantGroup(name='Test Group')
        group.save()

        self.assertEqual(group.tenant_id, self.tenant.id)

    def test_tenant_group_requires_tenant_id(self):
        """Test that TenantGroup raises error if no tenant context."""
        set_current_tenant_id(None)

        group = TenantGroup(name='Test Group')

        with self.assertRaises(ValueError) as context:
            group.save()

        self.assertIn('tenant_id cannot be None', str(context.exception))

    def test_tenant_group_str_method(self):
        """Test TenantGroup string representation."""
        group = TenantGroup.objects.create(name='Test Group')

        self.assertEqual(str(group), 'Test Group')

    def test_tenant_group_natural_key(self):
        """Test TenantGroup natural key method."""
        group = TenantGroup.objects.create(name='Test Group')

        natural_key = group.natural_key()
        self.assertEqual(natural_key, ('Test Group', str(self.tenant.id)))

    def test_tenant_manager_filters_by_tenant(self):
        """Test that TenantManager automatically filters by tenant."""
        tenant2 = Tenant.objects.create(
            subdomain='tenant2',
            name='Tenant 2',
            region='us',
        )

        # Create groups in different tenants
        set_current_tenant_id(self.tenant.id)
        group1 = TenantGroup.objects.create(name='Group 1')

        set_current_tenant_id(tenant2.id)
        group2 = TenantGroup.objects.create(name='Group 2')

        # Query with tenant 1 context
        set_current_tenant_id(self.tenant.id)
        groups = TenantGroup.objects.all()
        self.assertEqual(groups.count(), 1)
        self.assertEqual(groups.first().id, group1.id)

        # Query with tenant 2 context
        set_current_tenant_id(tenant2.id)
        groups = TenantGroup.objects.all()
        self.assertEqual(groups.count(), 1)
        self.assertEqual(groups.first().id, group2.id)

        # Query with all_objects (bypass filtering)
        all_groups = TenantGroup.all_objects.all()
        self.assertEqual(all_groups.count(), 2)

    def test_tenant_manager_returns_empty_without_context(self):
        """Test that TenantManager returns empty queryset without tenant context."""
        TenantGroup.objects.create(name='Group 1')

        set_current_tenant_id(None)

        groups = TenantGroup.objects.all()
        self.assertEqual(groups.count(), 0)
