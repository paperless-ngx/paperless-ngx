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
        # Signal handler will auto-create UserProfile when tenant context is set
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
            is_superuser=True,
        )

        self.user_b2 = User.objects.create_user(
            username='user_b2',
            password='testpass123',
        )

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

    def test_signal_auto_creates_profile(self):
        """Test that the post_save signal automatically creates UserProfile."""
        # Set tenant context
        set_current_tenant_id(self.tenant_a.id)

        # Create a new user (signal should auto-create profile)
        new_user = User.objects.create_user(
            username='signal_test_user',
            password='testpass123',
        )

        # Verify profile was auto-created by signal
        self.assertTrue(hasattr(new_user, 'profile'))
        self.assertEqual(new_user.profile.tenant_id, self.tenant_a.id)

    def test_signal_skips_system_users(self):
        """Test that signal doesn't create profiles for system users."""
        # Set tenant context
        set_current_tenant_id(self.tenant_a.id)

        # Create system user
        system_user = User.objects.create_user(username='consumer')

        # Profile should NOT be created for system users
        with self.assertRaises(UserProfile.DoesNotExist):
            _ = system_user.profile

    def test_middleware_sets_tenant_id_on_request(self):
        """Test that middleware properly sets request.tenant_id attribute."""
        from paperless.middleware import TenantMiddleware
        from django.http import HttpRequest
        from unittest.mock import Mock

        # Create mock request
        request = HttpRequest()
        request.META = {
            'HTTP_X_TENANT_ID': str(self.tenant_a.id),
        }

        # Create mock get_response
        get_response = Mock(return_value=Mock())

        # Initialize middleware and process request
        middleware = TenantMiddleware(get_response)
        middleware(request)

        # Verify tenant_id was set on request
        self.assertTrue(hasattr(request, 'tenant_id'))
        self.assertEqual(request.tenant_id, self.tenant_a.id)

    def test_superuser_bypasses_tenant_filtering(self):
        """Test that superusers can see users from all tenants."""
        # Login as superuser from tenant A
        self.client.force_authenticate(user=self.user_a1)

        # Make sure user_a1 is a superuser
        self.assertTrue(self.user_a1.is_superuser)

        # Simulate tenant A request (superuser should see ALL users)
        response = self.client.get(
            '/api/users/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        usernames = [user['username'] for user in response.data['results']]

        # Superuser should see users from ALL tenants
        self.assertIn('user_a1', usernames)
        self.assertIn('user_a2', usernames)
        self.assertIn('user_b1', usernames)
        self.assertIn('user_b2', usernames)

    def test_non_superuser_only_sees_own_tenant(self):
        """Test that non-superusers are limited to their own tenant."""
        # Login as non-superuser from tenant A
        self.client.force_authenticate(user=self.user_a2)

        # Make sure user_a2 is NOT a superuser
        self.assertFalse(self.user_a2.is_superuser)

        # Simulate tenant A request
        response = self.client.get(
            '/api/users/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        usernames = [user['username'] for user in response.data['results']]

        # Non-superuser should only see users from their tenant
        self.assertIn('user_a1', usernames)
        self.assertIn('user_a2', usernames)
        self.assertNotIn('user_b1', usernames)
        self.assertNotIn('user_b2', usernames)

    def test_users_without_profile_excluded(self):
        """Test that users without UserProfile are excluded from results."""
        # Create a user without profile (bypass signal)
        set_current_tenant_id(None)  # Clear tenant context so signal doesn't create profile
        orphan_user = User.objects.create_user(
            username='orphan_user',
            password='testpass123',
        )

        # Verify no profile exists
        with self.assertRaises(UserProfile.DoesNotExist):
            _ = orphan_user.profile

        # Login as non-superuser from tenant A
        self.client.force_authenticate(user=self.user_a2)

        # Request user list
        response = self.client.get(
            '/api/users/',
            HTTP_HOST='tenant-a.localhost',
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200)
        usernames = [user['username'] for user in response.data['results']]

        # Orphan user should NOT appear (no profile)
        self.assertNotIn('orphan_user', usernames)

    def test_signal_fallback_to_default_tenant(self):
        """Test that signal handler falls back to default tenant when no context."""
        # Create default tenant
        default_tenant = Tenant.objects.create(
            subdomain='default',
            name='Default Tenant',
            region='us',
        )

        # Clear tenant context
        set_current_tenant_id(None)

        # Create user (signal should use default tenant)
        fallback_user = User.objects.create_user(
            username='fallback_user',
            password='testpass123',
        )

        # Profile should be created with default tenant
        self.assertTrue(hasattr(fallback_user, 'profile'))
        self.assertEqual(fallback_user.profile.tenant_id, default_tenant.id)
