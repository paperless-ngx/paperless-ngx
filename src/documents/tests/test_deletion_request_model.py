"""
Unit tests for DeletionRequest Model

Tests cover:
- Model creation and field validation
- approve() method with different states
- reject() method with different states
- Status transitions and constraints
- Complete workflow scenarios
- Audit trail validation
- Model relationships and data integrity
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from documents.models import (
    Correspondent,
    DeletionRequest,
    Document,
    DocumentType,
    Tag,
)


class TestDeletionRequestModelCreation(TestCase):
    """Test DeletionRequest model creation and basic functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.doc = Document.objects.create(
            title="Test Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

    def test_create_deletion_request_basic(self):
        """Test creating a basic deletion request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test reason",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        self.assertIsNotNone(request)
        self.assertTrue(request.requested_by_ai)
        self.assertEqual(request.ai_reason, "Test reason")
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)

    def test_deletion_request_auto_timestamps(self):
        """Test that timestamps are automatically set."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)

    def test_deletion_request_default_status(self):
        """Test that default status is pending."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)

    def test_deletion_request_with_documents(self):
        """Test adding documents to deletion request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        doc2 = Document.objects.create(
            title="Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
        )
        
        request.documents.add(self.doc, doc2)
        
        self.assertEqual(request.documents.count(), 2)
        self.assertIn(self.doc, request.documents.all())
        self.assertIn(doc2, request.documents.all())

    def test_deletion_request_impact_summary_default(self):
        """Test that impact_summary defaults to empty dict."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        self.assertIsInstance(request.impact_summary, dict)
        self.assertEqual(request.impact_summary, {})

    def test_deletion_request_impact_summary_json(self):
        """Test storing JSON data in impact_summary."""
        impact = {
            "document_count": 5,
            "affected_tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }
        
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            impact_summary=impact,
        )
        
        self.assertEqual(request.impact_summary["document_count"], 5)
        self.assertEqual(request.impact_summary["affected_tags"], ["tag1", "tag2"])

    def test_deletion_request_str_representation(self):
        """Test string representation of deletion request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        request.documents.add(self.doc)
        
        str_repr = str(request)
        
        self.assertIn("Deletion Request", str_repr)
        self.assertIn(str(request.id), str_repr)
        self.assertIn("1 documents", str_repr)
        self.assertIn("pending", str_repr)


class TestDeletionRequestApprove(TestCase):
    """Test approve() method functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="user1", password="pass")
        self.approver = User.objects.create_user(username="approver", password="pass")
        self.doc = Document.objects.create(
            title="Test Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

    def test_approve_pending_request(self):
        """Test approving a pending request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        result = request.approve(self.approver, "Approved")
        
        self.assertTrue(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.review_comment, "Approved")

    def test_approve_with_empty_comment(self):
        """Test approving without a comment."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        result = request.approve(self.approver)
        
        self.assertTrue(result)
        self.assertEqual(request.review_comment, "")

    def test_approve_already_approved_request(self):
        """Test that approving an already approved request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_APPROVED,
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )
        
        result = request.approve(self.approver, "Trying to approve again")
        
        self.assertFalse(result)
        self.assertEqual(request.reviewed_by, self.user)  # Should not change

    def test_approve_rejected_request(self):
        """Test that approving a rejected request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_REJECTED,
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )
        
        result = request.approve(self.approver, "Trying to approve rejected")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)

    def test_approve_cancelled_request(self):
        """Test that approving a cancelled request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_CANCELLED,
        )
        
        result = request.approve(self.approver, "Trying to approve cancelled")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_CANCELLED)

    def test_approve_completed_request(self):
        """Test that approving a completed request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_COMPLETED,
        )
        
        result = request.approve(self.approver, "Trying to approve completed")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_COMPLETED)

    def test_approve_sets_timestamp(self):
        """Test that approve() sets the reviewed_at timestamp."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        before_approval = timezone.now()
        result = request.approve(self.approver, "Approved")
        after_approval = timezone.now()
        
        self.assertTrue(result)
        self.assertIsNotNone(request.reviewed_at)
        self.assertGreaterEqual(request.reviewed_at, before_approval)
        self.assertLessEqual(request.reviewed_at, after_approval)


class TestDeletionRequestReject(TestCase):
    """Test reject() method functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="user1", password="pass")
        self.reviewer = User.objects.create_user(username="reviewer", password="pass")

    def test_reject_pending_request(self):
        """Test rejecting a pending request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        result = request.reject(self.reviewer, "Not necessary")
        
        self.assertTrue(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)
        self.assertEqual(request.reviewed_by, self.reviewer)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.review_comment, "Not necessary")

    def test_reject_with_empty_comment(self):
        """Test rejecting without a comment."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        result = request.reject(self.reviewer)
        
        self.assertTrue(result)
        self.assertEqual(request.review_comment, "")

    def test_reject_already_rejected_request(self):
        """Test that rejecting an already rejected request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_REJECTED,
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )
        
        result = request.reject(self.reviewer, "Trying to reject again")
        
        self.assertFalse(result)
        self.assertEqual(request.reviewed_by, self.user)  # Should not change

    def test_reject_approved_request(self):
        """Test that rejecting an approved request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_APPROVED,
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
        )
        
        result = request.reject(self.reviewer, "Trying to reject approved")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)

    def test_reject_cancelled_request(self):
        """Test that rejecting a cancelled request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_CANCELLED,
        )
        
        result = request.reject(self.reviewer, "Trying to reject cancelled")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_CANCELLED)

    def test_reject_completed_request(self):
        """Test that rejecting a completed request fails."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_COMPLETED,
        )
        
        result = request.reject(self.reviewer, "Trying to reject completed")
        
        self.assertFalse(result)
        self.assertEqual(request.status, DeletionRequest.STATUS_COMPLETED)

    def test_reject_sets_timestamp(self):
        """Test that reject() sets the reviewed_at timestamp."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        before_rejection = timezone.now()
        result = request.reject(self.reviewer, "Rejected")
        after_rejection = timezone.now()
        
        self.assertTrue(result)
        self.assertIsNotNone(request.reviewed_at)
        self.assertGreaterEqual(request.reviewed_at, before_rejection)
        self.assertLessEqual(request.reviewed_at, after_rejection)


class TestDeletionRequestWorkflowScenarios(TestCase):
    """Test complete workflow scenarios."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="user1", password="pass")
        self.approver = User.objects.create_user(username="approver", password="pass")
        
        self.correspondent = Correspondent.objects.create(name="Test Corp")
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.tag = Tag.objects.create(name="Important")
        
        self.doc1 = Document.objects.create(
            title="Document 1",
            content="Content 1",
            checksum="checksum1",
            mime_type="application/pdf",
            correspondent=self.correspondent,
            document_type=self.doc_type,
        )
        self.doc1.tags.add(self.tag)
        
        self.doc2 = Document.objects.create(
            title="Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
        )

    def test_workflow_pending_to_approved(self):
        """Test workflow transition from pending to approved."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Duplicate documents",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
            impact_summary={"document_count": 2},
        )
        request.documents.add(self.doc1, self.doc2)
        
        # Verify initial state
        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)
        self.assertIsNone(request.reviewed_by)
        self.assertIsNone(request.reviewed_at)
        
        # Approve
        success = request.approve(self.approver, "Confirmed duplicates")
        
        # Verify final state
        self.assertTrue(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.review_comment, "Confirmed duplicates")

    def test_workflow_pending_to_rejected(self):
        """Test workflow transition from pending to rejected."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Suspected duplicates",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        request.documents.add(self.doc1)
        
        # Verify initial state
        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)
        
        # Reject
        success = request.reject(self.approver, "Not duplicates")
        
        # Verify final state
        self.assertTrue(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.review_comment, "Not duplicates")

    def test_workflow_cannot_approve_after_rejection(self):
        """Test that request cannot be approved after rejection."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        # Reject first
        request.reject(self.user, "Rejected")
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)
        
        # Try to approve
        success = request.approve(self.approver, "Changed my mind")
        
        # Should fail
        self.assertFalse(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)

    def test_workflow_cannot_reject_after_approval(self):
        """Test that request cannot be rejected after approval."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        # Approve first
        request.approve(self.approver, "Approved")
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)
        
        # Try to reject
        success = request.reject(self.user, "Changed my mind")
        
        # Should fail
        self.assertFalse(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)


class TestDeletionRequestAuditTrail(TestCase):
    """Test audit trail and tracking functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="user1", password="pass")
        self.approver = User.objects.create_user(username="approver", password="pass")

    def test_audit_trail_records_creator(self):
        """Test that audit trail records the user who needs to approve."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        self.assertEqual(request.user, self.user)

    def test_audit_trail_records_reviewer(self):
        """Test that audit trail records who reviewed the request."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        request.approve(self.approver, "Approved")
        
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertNotEqual(request.reviewed_by, request.user)

    def test_audit_trail_records_timestamps(self):
        """Test that all timestamps are properly recorded."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        created_at = request.created_at
        
        # Approve the request
        request.approve(self.approver, "Approved")
        
        # Verify timestamps
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)
        self.assertIsNotNone(request.reviewed_at)
        self.assertGreaterEqual(request.reviewed_at, created_at)

    def test_audit_trail_preserves_ai_reason(self):
        """Test that AI's original reason is preserved."""
        original_reason = "AI detected duplicates based on content similarity"
        
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason=original_reason,
            user=self.user,
        )
        
        # Approve with different comment
        request.approve(self.approver, "User confirmed")
        
        # Original AI reason should be preserved
        self.assertEqual(request.ai_reason, original_reason)
        self.assertEqual(request.review_comment, "User confirmed")

    def test_audit_trail_completion_details(self):
        """Test that completion details can be stored."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_COMPLETED,
            completion_details={
                "deleted_count": 5,
                "failed_count": 0,
                "completed_by": "system",
            },
        )
        
        self.assertEqual(request.completion_details["deleted_count"], 5)
        self.assertEqual(request.completion_details["failed_count"], 0)

    def test_audit_trail_multiple_requests_same_user(self):
        """Test audit trail with multiple requests for same user."""
        request1 = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Reason 1",
            user=self.user,
        )
        
        request2 = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Reason 2",
            user=self.user,
        )
        
        # Approve one, reject another
        request1.approve(self.approver, "Approved")
        request2.reject(self.approver, "Rejected")
        
        # Verify each has its own audit trail
        self.assertEqual(request1.status, DeletionRequest.STATUS_APPROVED)
        self.assertEqual(request2.status, DeletionRequest.STATUS_REJECTED)
        self.assertEqual(request1.review_comment, "Approved")
        self.assertEqual(request2.review_comment, "Rejected")


class TestDeletionRequestModelRelationships(TestCase):
    """Test model relationships and data integrity."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="user1", password="pass")

    def test_user_deletion_cascades_to_requests(self):
        """Test that deleting a user deletes their deletion requests."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        request_id = request.id
        self.assertEqual(DeletionRequest.objects.filter(id=request_id).count(), 1)
        
        # Delete user
        self.user.delete()
        
        # Request should be deleted
        self.assertEqual(DeletionRequest.objects.filter(id=request_id).count(), 0)

    def test_document_relationship_many_to_many(self):
        """Test many-to-many relationship with documents."""
        doc1 = Document.objects.create(
            title="Doc 1",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )
        doc2 = Document.objects.create(
            title="Doc 2",
            content="Content",
            checksum="checksum2",
            mime_type="application/pdf",
        )
        
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
        )
        
        request.documents.add(doc1, doc2)
        
        self.assertEqual(request.documents.count(), 2)
        self.assertEqual(doc1.deletion_requests.count(), 1)
        self.assertEqual(doc2.deletion_requests.count(), 1)

    def test_reviewed_by_nullable(self):
        """Test that reviewed_by can be null."""
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        self.assertIsNone(request.reviewed_by)

    def test_reviewed_by_set_null_on_delete(self):
        """Test that reviewed_by is set to null when reviewer is deleted."""
        approver = User.objects.create_user(username="approver", password="pass")
        
        request = DeletionRequest.objects.create(
            requested_by_ai=True,
            ai_reason="Test",
            user=self.user,
            status=DeletionRequest.STATUS_PENDING,
        )
        
        request.approve(approver, "Approved")
        self.assertEqual(request.reviewed_by, approver)
        
        # Delete approver
        approver.delete()
        
        # Refresh request
        request.refresh_from_db()
        
        # reviewed_by should be null
        self.assertIsNone(request.reviewed_by)
        # But the request should still exist
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)
