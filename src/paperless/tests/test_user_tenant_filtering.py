"""
Tests for tenant-filtered User API endpoints.

Verifies that /api/users/ only returns users belonging to the current tenant.
"""
import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from documents.models import Tenant
from documents.models.base import set_current_tenant_id
from paperless.models import UserProfile


class UserTenantFilteringTestCase(TestCase):
    """Test tenant filtering on User API endpoints."""

    def setUp(self):
        """Set up test data with multiple tenants and users."""
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
        UserProfile.objects.create(user=self.user_a1, tenant_id=self.tenant_a.id)

        self.user_a2 = User.objects.create_user(
            username='user_a2',
            password='testpass123',
        )
        UserProfile.objects.create(user=self.user_a2, tenant_id=self.tenant_a.id)

        # Create users for tenant B
        set_current_tenant_id(self.tenant_b.id)
        self.user_b1 = User.objects.create_user(
            username='user_b1',
            password='testpass123',
            is_superuser=True,
        )
        UserProfile.objects.create(user=self.user_b1, tenant_id=self.tenant_b.id)

        self.user_b2 = User.objects.create_user(
            username='user_b2',
            password='testpass123',
        )
        UserProfile.objects.create(user=self.user_b2, tenant_id=self.tenant_b.id)

        # API client
        self.client = APIClient()

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

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

    def test_user_list_tenant_b_isolation(self):
        """Test that tenant B users only see tenant B users."""
        # Login as user from tenant B
        self.client.force_authenticate(user=self.user_b1)

        # Simulate tenant B request
        response = self.client.get(
            '/api/users/',
            HTTP_HOST='tenant-b.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )

        self.assertEqual(response.status_code, 200)
        usernames = [user['username'] for user in response.data['results']]

        # Should only see users from tenant B
        self.assertIn('user_b1', usernames)
        self.assertIn('user_b2', usernames)

        # Should NOT see users from tenant A
        self.assertNotIn('user_a1', usernames)
        self.assertNotIn('user_a2', usernames)

    def test_create_user_sets_tenant_id(self):
        """Test that creating a user via API sets tenant_id from request context."""
        # Login as superuser from tenant A
        self.client.force_authenticate(user=self.user_a1)

        # Set tenant context
        set_current_tenant_id(self.tenant_a.id)

        # Create new user
        response = self.client.post(
            '/api/users/',
            {
                'username': 'new_user_a',
                'password': 'newpass123',
                'email': 'new@example.com',
            },
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 201)

        # Verify user was created with correct tenant_id
        new_user = User.objects.get(username='new_user_a')
        self.assertTrue(hasattr(new_user, 'profile'))
        self.assertEqual(new_user.profile.tenant_id, self.tenant_a.id)

    def test_system_users_excluded(self):
        """Test that system users (consumer, AnonymousUser) are excluded from results."""
        # Create system users
        consumer_user = User.objects.create_user(username='consumer')
        anon_user = User.objects.create_user(username='AnonymousUser')

        # Login as user from tenant A
        self.client.force_authenticate(user=self.user_a1)

        # Request users
        response = self.client.get(
            '/api/users/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        usernames = [user['username'] for user in response.data['results']]

        # System users should not appear
        self.assertNotIn('consumer', usernames)
        self.assertNotIn('AnonymousUser', usernames)

    def test_user_cannot_access_other_tenant_user(self):
        """Test that a user cannot retrieve details of a user from another tenant."""
        # Login as user from tenant A
        self.client.force_authenticate(user=self.user_a1)

        # Try to get user from tenant B
        response = self.client.get(
            f'/api/users/{self.user_b1.id}/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Should return 404 (user not found in tenant A's scope)
        self.assertEqual(response.status_code, 404)

    def test_user_can_access_same_tenant_user(self):
        """Test that a user can retrieve details of another user in the same tenant."""
        # Login as user from tenant A
        self.client.force_authenticate(user=self.user_a1)

        # Get user from same tenant
        response = self.client.get(
            f'/api/users/{self.user_a2.id}/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'user_a2')
