"""
Tests for CustomField tenant isolation functionality.
"""
import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from documents.models import (
    CustomField,
    CustomFieldInstance,
    Document,
    get_current_tenant_id,
    set_current_tenant_id,
)
from documents.models.tenant import Tenant
from documents.tests.utils import DirectoriesMixin


class CustomFieldTenantIsolationTestCase(TestCase):
    """Test tenant isolation for CustomField model."""

    def setUp(self):
        """Set up test data."""
        # Create two tenants
        self.tenant1 = Tenant.objects.create(
            subdomain='tenant1',
            name='Tenant 1',
            region='us',
        )
        self.tenant2 = Tenant.objects.create(
            subdomain='tenant2',
            name='Tenant 2',
            region='us',
        )

        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123',
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123',
        )

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_customfield_auto_populate_tenant_id(self):
        """Test that CustomField tenant_id is auto-populated from thread-local on save."""
        set_current_tenant_id(self.tenant1.id)

        custom_field = CustomField(
            name='Test Field',
            data_type=CustomField.FieldDataType.STRING,
        )
        custom_field.save()

        self.assertEqual(custom_field.tenant_id, self.tenant1.id)

    def test_customfield_explicit_tenant_id_override(self):
        """Test that explicitly set tenant_id is not overridden."""
        set_current_tenant_id(self.tenant1.id)

        # Explicitly set different tenant_id
        custom_field = CustomField(
            name='Test Field',
            data_type=CustomField.FieldDataType.STRING,
            tenant_id=self.tenant2.id,
        )
        custom_field.save()

        # Should keep explicitly set tenant_id
        self.assertEqual(custom_field.tenant_id, self.tenant2.id)

    def test_customfield_save_without_tenant_id_raises_error(self):
        """Test that saving CustomField without tenant_id raises ValueError."""
        # Ensure thread-local is None
        set_current_tenant_id(None)

        custom_field = CustomField(
            name='Test Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        with self.assertRaises(ValueError) as context:
            custom_field.save()

        self.assertIn('tenant_id cannot be None', str(context.exception))
        self.assertIn('CustomField', str(context.exception))

    def test_customfield_manager_filters_by_tenant(self):
        """Test that CustomField.objects manager filters by current tenant."""
        # Create custom fields for tenant1
        set_current_tenant_id(self.tenant1.id)
        cf1 = CustomField.objects.create(
            name='Tenant1 Field 1',
            data_type=CustomField.FieldDataType.STRING,
        )
        cf2 = CustomField.objects.create(
            name='Tenant1 Field 2',
            data_type=CustomField.FieldDataType.INTEGER,
        )

        # Create custom fields for tenant2
        set_current_tenant_id(self.tenant2.id)
        cf3 = CustomField.objects.create(
            name='Tenant2 Field 1',
            data_type=CustomField.FieldDataType.STRING,
        )

        # Query as tenant1 - should only see tenant1's fields
        set_current_tenant_id(self.tenant1.id)
        tenant1_fields = list(CustomField.objects.all())
        self.assertEqual(len(tenant1_fields), 2)
        self.assertIn(cf1, tenant1_fields)
        self.assertIn(cf2, tenant1_fields)
        self.assertNotIn(cf3, tenant1_fields)

        # Query as tenant2 - should only see tenant2's fields
        set_current_tenant_id(self.tenant2.id)
        tenant2_fields = list(CustomField.objects.all())
        self.assertEqual(len(tenant2_fields), 1)
        self.assertIn(cf3, tenant2_fields)
        self.assertNotIn(cf1, tenant2_fields)
        self.assertNotIn(cf2, tenant2_fields)

    def test_customfield_all_objects_manager_bypasses_filter(self):
        """Test that CustomField.all_objects manager bypasses tenant filtering."""
        # Create custom fields for both tenants
        set_current_tenant_id(self.tenant1.id)
        cf1 = CustomField.objects.create(
            name='Tenant1 Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        set_current_tenant_id(self.tenant2.id)
        cf2 = CustomField.objects.create(
            name='Tenant2 Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        # all_objects should see all custom fields regardless of tenant context
        set_current_tenant_id(self.tenant1.id)
        all_fields = list(CustomField.all_objects.all())
        self.assertGreaterEqual(len(all_fields), 2)
        self.assertIn(cf1, all_fields)
        self.assertIn(cf2, all_fields)

    def test_customfield_no_tenant_context_returns_empty(self):
        """Test that querying CustomField without tenant context returns empty queryset."""
        # Create a custom field
        set_current_tenant_id(self.tenant1.id)
        CustomField.objects.create(
            name='Test Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        # Query without tenant context
        set_current_tenant_id(None)
        fields = list(CustomField.objects.all())
        self.assertEqual(len(fields), 0)

    def test_customfield_tenant_id_indexes_exist(self):
        """Test that database indexes on tenant_id columns exist."""
        from django.db import connection

        with connection.cursor() as cursor:
            # Check for tenant_id index on documents_customfield table
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'documents_customfield'
                AND indexdef LIKE '%tenant_id%'
            """)
            indexes = cursor.fetchall()
            self.assertGreater(
                len(indexes),
                0,
                'At least one index on tenant_id should exist for CustomField',
            )


class CustomFieldAPITenantIsolationTestCase(DirectoriesMixin, APITestCase):
    """Test tenant isolation for CustomField API endpoints."""

    ENDPOINT = "/api/custom_fields/"

    def setUp(self):
        """Set up test data."""
        super().setUp()

        # Create two tenants
        self.tenant1 = Tenant.objects.create(
            subdomain='tenant1',
            name='Tenant 1',
            region='us',
        )
        self.tenant2 = Tenant.objects.create(
            subdomain='tenant2',
            name='Tenant 2',
            region='us',
        )

        # Create users
        self.user1 = User.objects.create_superuser(username='user1', password='pass123')
        self.user2 = User.objects.create_superuser(username='user2', password='pass123')

        # Create custom fields for each tenant
        set_current_tenant_id(self.tenant1.id)
        self.cf1 = CustomField.objects.create(
            name='Tenant1 Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        set_current_tenant_id(self.tenant2.id)
        self.cf2 = CustomField.objects.create(
            name='Tenant2 Field',
            data_type=CustomField.FieldDataType.STRING,
        )

        # Clear tenant context
        set_current_tenant_id(None)

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)
        super().tearDown()

    def test_api_list_filters_by_tenant(self):
        """Test that API list endpoint filters custom fields by tenant."""
        # Authenticate and set tenant context for tenant1
        self.client.force_authenticate(user=self.user1)
        set_current_tenant_id(self.tenant1.id)

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see tenant1's custom field
        results = response.json()['results']
        field_ids = [cf['id'] for cf in results]
        self.assertIn(self.cf1.id, field_ids)
        self.assertNotIn(self.cf2.id, field_ids)

    def test_api_create_assigns_tenant_id(self):
        """Test that API create endpoint assigns tenant_id from context."""
        self.client.force_authenticate(user=self.user1)
        set_current_tenant_id(self.tenant1.id)

        response = self.client.post(
            self.ENDPOINT,
            data={
                'name': 'New Field',
                'data_type': 'string',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify tenant_id was set correctly
        field_id = response.json()['id']
        custom_field = CustomField.all_objects.get(id=field_id)
        self.assertEqual(custom_field.tenant_id, self.tenant1.id)

    def test_api_cannot_access_other_tenant_field(self):
        """Test that API cannot retrieve custom field from another tenant."""
        self.client.force_authenticate(user=self.user1)
        set_current_tenant_id(self.tenant1.id)

        # Try to access tenant2's custom field
        response = self.client.get(f"{self.ENDPOINT}{self.cf2.id}/")

        # Should return 404 since it's not visible to tenant1
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_access_own_tenant_field(self):
        """Test that API can retrieve custom field from own tenant."""
        self.client.force_authenticate(user=self.user1)
        set_current_tenant_id(self.tenant1.id)

        # Access tenant1's custom field
        response = self.client.get(f"{self.ENDPOINT}{self.cf1.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['id'], self.cf1.id)
