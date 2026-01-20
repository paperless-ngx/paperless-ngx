"""
Tests for the Tenant model.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from documents.models import Tenant


class TestTenantModel(TestCase):
    """Test the Tenant model."""

    def test_create_tenant(self):
        """Test creating a basic tenant."""
        tenant = Tenant.objects.create(
            name="Test Organization",
            subdomain="test-org",
        )

        self.assertEqual(tenant.name, "Test Organization")
        self.assertEqual(tenant.subdomain, "test-org")
        self.assertEqual(tenant.region, "us")  # default
        self.assertEqual(tenant.max_storage_gb, 10)  # default
        self.assertEqual(tenant.max_documents, 10000)  # default
        self.assertEqual(tenant.max_users, 10)  # default
        self.assertEqual(tenant.theme_color, "#17541f")  # default
        self.assertEqual(tenant.app_title, "Paperless-ngx")  # default
        self.assertTrue(tenant.is_active)  # default
        self.assertIsNotNone(tenant.id)
        self.assertIsNotNone(tenant.created_at)
        self.assertIsNotNone(tenant.updated_at)

    def test_tenant_storage_container_property(self):
        """Test the storage_container property."""
        tenant = Tenant.objects.create(
            name="Test Org",
            subdomain="test",
        )

        expected = f"paperless-{tenant.id}"
        self.assertEqual(tenant.storage_container, expected)

    def test_tenant_subdomain_unique(self):
        """Test that subdomain must be unique."""
        Tenant.objects.create(
            name="First Tenant",
            subdomain="unique-subdomain",
        )

        with self.assertRaises(IntegrityError):
            Tenant.objects.create(
                name="Second Tenant",
                subdomain="unique-subdomain",
            )

    def test_tenant_subdomain_validation_valid(self):
        """Test subdomain validation with valid inputs."""
        valid_subdomains = [
            "tenant-a",
            "test123",
            "my-org-123",
            "abc",
        ]

        for subdomain in valid_subdomains:
            tenant = Tenant(
                name="Test",
                subdomain=subdomain,
            )
            # Should not raise ValidationError
            tenant.full_clean()
            tenant.save()
            tenant.delete()

    def test_tenant_subdomain_validation_invalid(self):
        """Test subdomain validation with invalid inputs."""
        invalid_subdomains = [
            "Tenant-A",  # uppercase
            "tenant_a",  # underscore
            "tenant.a",  # dot
            "tenant a",  # space
            "tenant@a",  # special character
        ]

        for subdomain in invalid_subdomains:
            tenant = Tenant(
                name="Test",
                subdomain=subdomain,
            )
            with self.assertRaises(ValidationError):
                tenant.full_clean()

    def test_tenant_region_choices(self):
        """Test tenant region field with different choices."""
        regions = ['eu', 'us', 'asia']

        for region in regions:
            tenant = Tenant.objects.create(
                name=f"Tenant in {region}",
                subdomain=f"tenant-{region}",
                region=region,
            )
            self.assertEqual(tenant.region, region)
            tenant.delete()

    def test_tenant_branding_fields(self):
        """Test tenant branding customization fields."""
        tenant = Tenant.objects.create(
            name="Branded Tenant",
            subdomain="branded",
            theme_color="#FF5733",
            app_title="My Custom App",
            logo_url="https://example.com/logo.png",
            custom_css="body { background-color: red; }",
        )

        self.assertEqual(tenant.theme_color, "#FF5733")
        self.assertEqual(tenant.app_title, "My Custom App")
        self.assertEqual(tenant.logo_url, "https://example.com/logo.png")
        self.assertEqual(tenant.custom_css, "body { background-color: red; }")

    def test_tenant_limits_fields(self):
        """Test tenant resource limit fields."""
        tenant = Tenant.objects.create(
            name="Limited Tenant",
            subdomain="limited",
            max_storage_gb=50,
            max_documents=50000,
            max_users=100,
        )

        self.assertEqual(tenant.max_storage_gb, 50)
        self.assertEqual(tenant.max_documents, 50000)
        self.assertEqual(tenant.max_users, 100)

    def test_tenant_is_active_field(self):
        """Test tenant is_active field."""
        tenant = Tenant.objects.create(
            name="Active Tenant",
            subdomain="active",
            is_active=True,
        )
        self.assertTrue(tenant.is_active)

        tenant.is_active = False
        tenant.save()
        tenant.refresh_from_db()
        self.assertFalse(tenant.is_active)

    def test_tenant_str_method(self):
        """Test the __str__ method."""
        tenant = Tenant.objects.create(
            name="Example Org",
            subdomain="example",
        )

        self.assertEqual(str(tenant), "Example Org (example)")

    def test_tenant_ordering(self):
        """Test that tenants are ordered by name."""
        Tenant.objects.create(name="Zebra", subdomain="zebra")
        Tenant.objects.create(name="Alpha", subdomain="alpha")
        Tenant.objects.create(name="Beta", subdomain="beta")

        tenants = list(Tenant.objects.all())
        self.assertEqual(tenants[0].name, "Alpha")
        self.assertEqual(tenants[1].name, "Beta")
        self.assertEqual(tenants[2].name, "Zebra")

    def test_tenant_queryset_operations(self):
        """Test common queryset operations."""
        # Create test tenants
        tenant_a = Tenant.objects.create(name="Tenant A", subdomain="tenant-a")
        tenant_b = Tenant.objects.create(name="Tenant B", subdomain="tenant-b")
        tenant_c = Tenant.objects.create(name="Tenant C", subdomain="tenant-c")

        # Test count
        self.assertEqual(Tenant.objects.count(), 3)

        # Test filter by subdomain
        result = Tenant.objects.get(subdomain="tenant-a")
        self.assertEqual(result.id, tenant_a.id)

        # Test filter by region
        Tenant.objects.filter(id=tenant_b.id).update(region="eu")
        eu_tenants = Tenant.objects.filter(region="eu")
        self.assertEqual(eu_tenants.count(), 1)
        self.assertEqual(eu_tenants.first().id, tenant_b.id)

        # Test exists
        self.assertTrue(Tenant.objects.filter(subdomain="tenant-c").exists())
        self.assertFalse(Tenant.objects.filter(subdomain="nonexistent").exists())
