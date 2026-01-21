"""
Tests for tenant isolation in ShareLink endpoints.

Verifies that ShareLink endpoints properly filter by tenant:
- ShareLink list/detail endpoints
- ShareLinks associated with documents belong to same tenant
- ShareLinks from other tenants are not accessible
"""

import uuid
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status

from documents.models import (
    Tenant,
    Document,
    ShareLink,
    set_current_tenant_id,
)


class ShareLinkTenantIsolationTestCase(TransactionTestCase):
    """Test tenant isolation in ShareLink endpoints."""

    def setUp(self):
        """Create test tenants, users, documents, and share links."""
        # Create tenant A
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            subdomain="tenant-a",
            is_active=True,
        )

        # Create tenant B
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            subdomain="tenant-b",
            is_active=True,
        )

        # Create users for each tenant
        self.user_a = User.objects.create_user(
            username="user_a",
            password="testpass123",
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            password="testpass123",
        )

        # Create documents for tenant A
        set_current_tenant_id(self.tenant_a.id)
        self.doc_a = Document.objects.create(
            title="Document A",
            content="Content A",
            checksum="a" * 32,
            owner=self.user_a,
        )

        # Create share link for tenant A
        self.sharelink_a = ShareLink.objects.create(
            document=self.doc_a,
            slug="sharelink-a",
            owner=self.user_a,
        )

        # Create documents for tenant B
        set_current_tenant_id(self.tenant_b.id)
        self.doc_b = Document.objects.create(
            title="Document B",
            content="Content B",
            checksum="b" * 32,
            owner=self.user_b,
        )

        # Create share link for tenant B
        self.sharelink_b = ShareLink.objects.create(
            document=self.doc_b,
            slug="sharelink-b",
            owner=self.user_b,
        )

        self.client = APIClient()

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_sharelink_list_tenant_isolation(self):
        """Test: ShareLink list endpoint only shows share links from current tenant."""
        # Set tenant A context
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get("/api/share_links/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see tenant A's share link
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.sharelink_a.id)

        # Set tenant B context
        set_current_tenant_id(self.tenant_b.id)
        self.client.force_authenticate(user=self.user_b)

        response = self.client.get("/api/share_links/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see tenant B's share link
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.sharelink_b.id)

    def test_sharelink_detail_tenant_isolation(self):
        """Test: ShareLink detail endpoint returns 404 for other tenant's share links."""
        # Set tenant A context
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        # Can access own tenant's share link
        response = self.client.get(f"/api/share_links/{self.sharelink_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.sharelink_a.id)

        # Cannot access other tenant's share link (should return 404)
        response = self.client.get(f"/api/share_links/{self.sharelink_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sharelink_inherits_document_tenant(self):
        """Test: ShareLink automatically inherits tenant_id from its document."""
        set_current_tenant_id(self.tenant_a.id)
        
        # Create a new share link - should automatically get tenant_id from document
        new_sharelink = ShareLink.objects.create(
            document=self.doc_a,
            slug="new-sharelink-a",
            owner=self.user_a,
        )

        # Verify tenant_id matches the document's tenant_id
        self.assertEqual(new_sharelink.tenant_id, self.doc_a.tenant_id)
        self.assertEqual(new_sharelink.tenant_id, self.tenant_a.id)

    def test_sharelink_create_via_api_tenant_isolation(self):
        """Test: Creating share links via API respects tenant isolation."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        # Create share link for tenant A's document
        response = self.client.post(
            "/api/share_links/",
            {
                "document": self.doc_a.id,
                "slug": "api-created-a",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify it belongs to tenant A
        sharelink_id = response.data["id"]
        sharelink = ShareLink.objects.get(id=sharelink_id)
        self.assertEqual(sharelink.tenant_id, self.tenant_a.id)

        # Try to create share link for tenant B's document (should fail)
        response = self.client.post(
            "/api/share_links/",
            {
                "document": self.doc_b.id,
                "slug": "api-created-b-fail",
            },
        )
        # Should fail because doc_b is not visible in tenant A's context
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sharelink_delete_tenant_isolation(self):
        """Test: Users can only delete share links from their tenant."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        # Try to delete tenant B's share link (should fail)
        response = self.client.delete(f"/api/share_links/{self.sharelink_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Can delete own tenant's share link
        response = self.client.delete(f"/api/share_links/{self.sharelink_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's deleted
        set_current_tenant_id(self.tenant_a.id)
        self.assertFalse(ShareLink.objects.filter(id=self.sharelink_a.id).exists())

    def test_sharelink_queryset_filtering(self):
        """Test: ShareLink.objects.all() automatically filters by tenant."""
        # Set tenant A context
        set_current_tenant_id(self.tenant_a.id)
        sharelinks = ShareLink.objects.all()
        self.assertEqual(sharelinks.count(), 1)
        self.assertEqual(sharelinks.first().id, self.sharelink_a.id)

        # Set tenant B context
        set_current_tenant_id(self.tenant_b.id)
        sharelinks = ShareLink.objects.all()
        self.assertEqual(sharelinks.count(), 1)
        self.assertEqual(sharelinks.first().id, self.sharelink_b.id)

        # No tenant context - should return empty
        set_current_tenant_id(None)
        sharelinks = ShareLink.objects.all()
        self.assertEqual(sharelinks.count(), 0)
