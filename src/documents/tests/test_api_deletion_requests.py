"""
API tests for DeletionRequest endpoints.

Tests cover:
- List and retrieve deletion requests
- Approve endpoint with permissions and status validation
- Reject endpoint with permissions and status validation
- Cancel endpoint with permissions and status validation
- Permission checking (owner vs non-owner vs admin)
- Execution flow when approved
"""

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import (
    Correspondent,
    DeletionRequest,
    Document,
    DocumentType,
    Tag,
)


class TestDeletionRequestAPI(APITestCase):
    """Test DeletionRequest API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create users
        self.user1 = User.objects.create_user(username="user1", password="pass123")
        self.user2 = User.objects.create_user(username="user2", password="pass123")
        self.admin = User.objects.create_superuser(username="admin", password="admin123")
        
        # Create test documents
        self.doc1 = Document.objects.create(
            title="Test Document 1",
            content="Content 1",
            checksum="checksum1",
            mime_type="application/pdf",
        )
        self.doc2 = Document.objects.create(
            title="Test Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
        )
        self.doc3 = Document.objects.create(
            title="Test Document 3",
            content="Content 3",
            checksum="checksum3",
            mime_type="application/pdf",
        )
        
        # Create deletion requests
        self.request1 = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Duplicate document detected",
            user=self.user1,
            status=DeletionRequest.STATUS_PENDING,
            impact_summary={"document_count": 1},
        )
        self.request1.documents.add(self.doc1)
        
        self.request2 = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Low quality document",
            user=self.user2,
            status=DeletionRequest.STATUS_PENDING,
            impact_summary={"document_count": 1},
        )
        self.request2.documents.add(self.doc2)

    def test_list_deletion_requests_as_owner(self):
        """Test that users can list their own deletion requests."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/deletion-requests/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.request1.id)

    def test_list_deletion_requests_as_admin(self):
        """Test that admin can list all deletion requests."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/deletion-requests/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_deletion_request(self):
        """Test retrieving a single deletion request."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"/api/deletion-requests/{self.request1.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.request1.id)
        self.assertEqual(response.data["ai_reason"], "Duplicate document detected")
        self.assertEqual(response.data["status"], DeletionRequest.STATUS_PENDING)
        self.assertIn("document_details", response.data)

    def test_approve_deletion_request_as_owner(self):
        """Test approving a deletion request as the owner."""
        self.client.force_authenticate(user=self.user1)
        
        # Verify document exists
        self.assertTrue(Document.objects.filter(id=self.doc1.id).exists())
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/approve/",
            {"comment": "Approved by owner"},
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("execution_result", response.data)
        self.assertEqual(response.data["execution_result"]["deleted_count"], 1)
        
        # Verify document was deleted
        self.assertFalse(Document.objects.filter(id=self.doc1.id).exists())
        
        # Verify deletion request was updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_COMPLETED)
        self.assertIsNotNone(self.request1.reviewed_at)
        self.assertEqual(self.request1.reviewed_by, self.user1)
        self.assertEqual(self.request1.review_comment, "Approved by owner")

    def test_approve_deletion_request_as_admin(self):
        """Test approving a deletion request as admin."""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request2.id}/approve/",
            {"comment": "Approved by admin"},
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("execution_result", response.data)
        
        # Verify document was deleted
        self.assertFalse(Document.objects.filter(id=self.doc2.id).exists())
        
        # Verify deletion request was updated
        self.request2.refresh_from_db()
        self.assertEqual(self.request2.status, DeletionRequest.STATUS_COMPLETED)
        self.assertEqual(self.request2.reviewed_by, self.admin)

    def test_approve_deletion_request_without_permission(self):
        """Test that non-owners cannot approve deletion requests."""
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/approve/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify document was NOT deleted
        self.assertTrue(Document.objects.filter(id=self.doc1.id).exists())
        
        # Verify deletion request was NOT updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_PENDING)

    def test_approve_already_approved_request(self):
        """Test that already approved requests cannot be approved again."""
        self.request1.status = DeletionRequest.STATUS_APPROVED
        self.request1.save()
        
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/approve/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("pending", response.data["error"].lower())

    def test_reject_deletion_request_as_owner(self):
        """Test rejecting a deletion request as the owner."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/reject/",
            {"comment": "Not needed"},
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        
        # Verify document was NOT deleted
        self.assertTrue(Document.objects.filter(id=self.doc1.id).exists())
        
        # Verify deletion request was updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_REJECTED)
        self.assertIsNotNone(self.request1.reviewed_at)
        self.assertEqual(self.request1.reviewed_by, self.user1)
        self.assertEqual(self.request1.review_comment, "Not needed")

    def test_reject_deletion_request_as_admin(self):
        """Test rejecting a deletion request as admin."""
        self.client.force_authenticate(user=self.admin)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request2.id}/reject/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify document was NOT deleted
        self.assertTrue(Document.objects.filter(id=self.doc2.id).exists())
        
        # Verify deletion request was updated
        self.request2.refresh_from_db()
        self.assertEqual(self.request2.status, DeletionRequest.STATUS_REJECTED)
        self.assertEqual(self.request2.reviewed_by, self.admin)

    def test_reject_deletion_request_without_permission(self):
        """Test that non-owners cannot reject deletion requests."""
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/reject/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify deletion request was NOT updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_PENDING)

    def test_reject_already_rejected_request(self):
        """Test that already rejected requests cannot be rejected again."""
        self.request1.status = DeletionRequest.STATUS_REJECTED
        self.request1.save()
        
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/reject/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_cancel_deletion_request_as_owner(self):
        """Test canceling a deletion request as the owner."""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/cancel/",
            {"comment": "Changed my mind"},
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        
        # Verify document was NOT deleted
        self.assertTrue(Document.objects.filter(id=self.doc1.id).exists())
        
        # Verify deletion request was updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_CANCELLED)
        self.assertIsNotNone(self.request1.reviewed_at)
        self.assertEqual(self.request1.reviewed_by, self.user1)
        self.assertIn("Changed my mind", self.request1.review_comment)

    def test_cancel_deletion_request_without_permission(self):
        """Test that non-owners cannot cancel deletion requests."""
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/cancel/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify deletion request was NOT updated
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DeletionRequest.STATUS_PENDING)

    def test_cancel_already_approved_request(self):
        """Test that approved requests cannot be cancelled."""
        self.request1.status = DeletionRequest.STATUS_APPROVED
        self.request1.save()
        
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/cancel/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_approve_with_multiple_documents(self):
        """Test approving a deletion request with multiple documents."""
        # Create a deletion request with multiple documents
        multi_request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Multiple duplicates",
            user=self.user1,
            status=DeletionRequest.STATUS_PENDING,
            impact_summary={"document_count": 2},
        )
        multi_request.documents.add(self.doc1, self.doc3)
        
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.post(
            f"/api/deletion-requests/{multi_request.id}/approve/",
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["execution_result"]["deleted_count"], 2)
        self.assertEqual(response.data["execution_result"]["total_documents"], 2)
        
        # Verify both documents were deleted
        self.assertFalse(Document.objects.filter(id=self.doc1.id).exists())
        self.assertFalse(Document.objects.filter(id=self.doc3.id).exists())

    def test_document_details_in_response(self):
        """Test that document details are properly included in response."""
        # Add some metadata to the document
        tag = Tag.objects.create(name="test-tag")
        correspondent = Correspondent.objects.create(name="Test Corp")
        doc_type = DocumentType.objects.create(name="Invoice")
        
        self.doc1.tags.add(tag)
        self.doc1.correspondent = correspondent
        self.doc1.document_type = doc_type
        self.doc1.save()
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"/api/deletion-requests/{self.request1.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc_details = response.data["document_details"]
        self.assertEqual(len(doc_details), 1)
        self.assertEqual(doc_details[0]["id"], self.doc1.id)
        self.assertEqual(doc_details[0]["title"], "Test Document 1")
        self.assertEqual(doc_details[0]["correspondent"], "Test Corp")
        self.assertEqual(doc_details[0]["document_type"], "Invoice")
        self.assertIn("test-tag", doc_details[0]["tags"])

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access the API."""
        response = self.client.get("/api/deletion-requests/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        response = self.client.post(
            f"/api/deletion-requests/{self.request1.id}/approve/",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
