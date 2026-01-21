"""
Tests for tenant isolation in document view endpoints.

Verifies that document endpoints properly filter by tenant:
- Document list/detail endpoints
- Document download/preview endpoints
- Document notes, metadata, suggestions endpoints
- SavedView endpoints
"""

import uuid
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status

from documents.models import (
    Tenant,
    Document,
    SavedView,
    set_current_tenant_id,
)


class DocumentViewsTenantIsolationTestCase(TransactionTestCase):
    """Test tenant isolation in document view endpoints."""

    def setUp(self):
        """Create test tenants, users, and documents."""
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

        # Create documents for tenant B
        set_current_tenant_id(self.tenant_b.id)
        self.doc_b = Document.objects.create(
            title="Document B",
            content="Content B",
            checksum="b" * 32,
            owner=self.user_b,
        )

        # Create saved views
        self.saved_view_a = SavedView.objects.create(
            name="View A",
            show_on_dashboard=True,
            show_in_sidebar=True,
            owner=self.user_a,
        )

        set_current_tenant_id(self.tenant_a.id)
        self.saved_view_a2 = SavedView.objects.create(
            name="View A2",
            show_on_dashboard=False,
            show_in_sidebar=True,
            owner=self.user_a,
        )

        self.client = APIClient()

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_document_list_tenant_isolation(self):
        """Test: Document list endpoint only shows documents from current tenant."""
        # Set tenant A context
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get("/api/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only return tenant A's document
        doc_ids = [doc["id"] for doc in response.data["results"]]
        self.assertIn(self.doc_a.id, doc_ids)
        self.assertNotIn(self.doc_b.id, doc_ids)

    def test_document_detail_cross_tenant_access_denied(self):
        """Test: Document detail returns 404 for documents in other tenants."""
        # User A tries to access tenant B's document
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_detail_same_tenant_access_allowed(self):
        """Test: Document detail works for documents in same tenant."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.doc_a.id)
        self.assertEqual(response.data["title"], "Document A")

    def test_document_metadata_cross_tenant_blocked(self):
        """Test: Metadata endpoint blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_b.id}/metadata/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_metadata_same_tenant_allowed(self):
        """Test: Metadata endpoint works for same tenant."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_a.id}/metadata/")
        # May return 200 or 404 depending on file existence, but should not return 403
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
        )

    def test_document_suggestions_cross_tenant_blocked(self):
        """Test: Suggestions endpoint blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_b.id}/suggestions/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_notes_cross_tenant_blocked(self):
        """Test: Notes endpoint blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_b.id}/notes/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_download_cross_tenant_blocked(self):
        """Test: Download endpoint blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(f"/api/documents/{self.doc_b.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_saved_view_list_tenant_isolation(self):
        """Test: SavedView list only shows views from current tenant."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return both views from tenant A (filtered by owner)
        view_ids = [view["id"] for view in response.data["results"]]
        self.assertEqual(len(view_ids), 2)
        self.assertIn(self.saved_view_a.id, view_ids)
        self.assertIn(self.saved_view_a2.id, view_ids)

    def test_saved_view_cross_tenant_access_denied(self):
        """Test: SavedView detail blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        # Create a saved view in tenant B to test against
        set_current_tenant_id(self.tenant_b.id)
        saved_view_b = SavedView.objects.create(
            name="View B",
            show_on_dashboard=True,
            show_in_sidebar=False,
            owner=self.user_b,
        )

        # Switch back to tenant A and try to access tenant B's view
        set_current_tenant_id(self.tenant_a.id)
        response = self.client.get(f"/api/saved_views/{saved_view_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_update_cross_tenant_blocked(self):
        """Test: Document update blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        update_data = {"title": "Updated Title"}
        response = self.client.patch(
            f"/api/documents/{self.doc_b.id}/",
            update_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_delete_cross_tenant_blocked(self):
        """Test: Document delete blocks cross-tenant access."""
        set_current_tenant_id(self.tenant_a.id)
        self.client.force_authenticate(user=self.user_a)

        response = self.client.delete(f"/api/documents/{self.doc_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify document B still exists
        set_current_tenant_id(self.tenant_b.id)
        self.assertTrue(Document.objects.filter(id=self.doc_b.id).exists())
