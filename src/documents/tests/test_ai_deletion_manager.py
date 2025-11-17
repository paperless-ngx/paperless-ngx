"""
Unit tests for AI Deletion Manager (ai_deletion_manager.py)

Tests cover:
- create_deletion_request() with impact analysis
- _analyze_impact() with different document scenarios
- format_deletion_request_for_user() with various scenarios
- get_pending_requests() with filters
- can_ai_delete_automatically() security constraint
- Complete deletion workflows
- Audit trail and tracking
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from documents.ai_deletion_manager import AIDeletionManager
from documents.models import Correspondent
from documents.models import DeletionRequest
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag


class TestAIDeletionManagerCreateRequest(TestCase):
    """Test create_deletion_request() functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass")

        # Create test documents with various metadata
        self.correspondent = Correspondent.objects.create(name="Test Corp")
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.tag1 = Tag.objects.create(name="Important")
        self.tag2 = Tag.objects.create(name="2024")

        self.doc1 = Document.objects.create(
            title="Test Document 1",
            content="Test content 1",
            checksum="checksum1",
            mime_type="application/pdf",
            correspondent=self.correspondent,
            document_type=self.doc_type,
        )
        self.doc1.tags.add(self.tag1, self.tag2)

        self.doc2 = Document.objects.create(
            title="Test Document 2",
            content="Test content 2",
            checksum="checksum2",
            mime_type="application/pdf",
            correspondent=self.correspondent,
        )
        self.doc2.tags.add(self.tag1)

    def test_create_deletion_request_basic(self):
        """Test creating a basic deletion request."""
        documents = [self.doc1, self.doc2]
        reason = "Duplicate documents detected"

        request = AIDeletionManager.create_deletion_request(
            documents=documents,
            reason=reason,
            user=self.user,
        )

        self.assertIsNotNone(request)
        self.assertIsInstance(request, DeletionRequest)
        self.assertEqual(request.ai_reason, reason)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)
        self.assertTrue(request.requested_by_ai)
        self.assertEqual(request.documents.count(), 2)

    def test_create_deletion_request_with_impact_analysis(self):
        """Test that deletion request includes impact analysis."""
        documents = [self.doc1, self.doc2]
        reason = "Test deletion"

        request = AIDeletionManager.create_deletion_request(
            documents=documents,
            reason=reason,
            user=self.user,
        )

        impact = request.impact_summary
        self.assertIsNotNone(impact)
        self.assertEqual(impact["document_count"], 2)
        self.assertIn("documents", impact)
        self.assertIn("affected_tags", impact)
        self.assertIn("affected_correspondents", impact)
        self.assertIn("affected_types", impact)
        self.assertIn("date_range", impact)

    def test_create_deletion_request_with_custom_impact(self):
        """Test creating request with pre-computed impact analysis."""
        documents = [self.doc1]
        reason = "Test deletion"
        custom_impact = {
            "document_count": 1,
            "custom_field": "custom_value",
        }

        request = AIDeletionManager.create_deletion_request(
            documents=documents,
            reason=reason,
            user=self.user,
            impact_analysis=custom_impact,
        )

        self.assertEqual(request.impact_summary, custom_impact)
        self.assertEqual(request.impact_summary["custom_field"], "custom_value")

    def test_create_deletion_request_empty_documents(self):
        """Test creating request with empty document list."""
        documents = []
        reason = "Test deletion"

        request = AIDeletionManager.create_deletion_request(
            documents=documents,
            reason=reason,
            user=self.user,
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.documents.count(), 0)
        self.assertEqual(request.impact_summary["document_count"], 0)


class TestAIDeletionManagerAnalyzeImpact(TestCase):
    """Test _analyze_impact() functionality."""

    def setUp(self):
        """Set up test data."""
        self.correspondent1 = Correspondent.objects.create(name="Corp A")
        self.correspondent2 = Correspondent.objects.create(name="Corp B")
        self.doc_type1 = DocumentType.objects.create(name="Invoice")
        self.doc_type2 = DocumentType.objects.create(name="Receipt")
        self.tag1 = Tag.objects.create(name="Important")
        self.tag2 = Tag.objects.create(name="Archive")
        self.tag3 = Tag.objects.create(name="2024")

    def test_analyze_impact_single_document(self):
        """Test impact analysis for a single document."""
        doc = Document.objects.create(
            title="Test Document",
            content="Test content",
            checksum="checksum1",
            mime_type="application/pdf",
            correspondent=self.correspondent1,
            document_type=self.doc_type1,
        )
        doc.tags.add(self.tag1, self.tag2)

        impact = AIDeletionManager._analyze_impact([doc])

        self.assertEqual(impact["document_count"], 1)
        self.assertEqual(len(impact["documents"]), 1)
        self.assertEqual(impact["documents"][0]["id"], doc.id)
        self.assertEqual(impact["documents"][0]["title"], "Test Document")
        self.assertIn("Corp A", impact["affected_correspondents"])
        self.assertIn("Invoice", impact["affected_types"])
        self.assertIn("Important", impact["affected_tags"])
        self.assertIn("Archive", impact["affected_tags"])

    def test_analyze_impact_multiple_documents(self):
        """Test impact analysis for multiple documents."""
        doc1 = Document.objects.create(
            title="Document 1",
            content="Content 1",
            checksum="checksum1",
            mime_type="application/pdf",
            correspondent=self.correspondent1,
            document_type=self.doc_type1,
        )
        doc1.tags.add(self.tag1)

        doc2 = Document.objects.create(
            title="Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
            correspondent=self.correspondent2,
            document_type=self.doc_type2,
        )
        doc2.tags.add(self.tag2, self.tag3)

        impact = AIDeletionManager._analyze_impact([doc1, doc2])

        self.assertEqual(impact["document_count"], 2)
        self.assertEqual(len(impact["documents"]), 2)
        self.assertIn("Corp A", impact["affected_correspondents"])
        self.assertIn("Corp B", impact["affected_correspondents"])
        self.assertIn("Invoice", impact["affected_types"])
        self.assertIn("Receipt", impact["affected_types"])
        self.assertEqual(len(impact["affected_tags"]), 3)

    def test_analyze_impact_document_without_metadata(self):
        """Test impact analysis for document without correspondent/type."""
        doc = Document.objects.create(
            title="Basic Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

        impact = AIDeletionManager._analyze_impact([doc])

        self.assertEqual(impact["document_count"], 1)
        self.assertEqual(impact["documents"][0]["correspondent"], None)
        self.assertEqual(impact["documents"][0]["document_type"], None)
        self.assertEqual(impact["documents"][0]["tags"], [])
        self.assertEqual(len(impact["affected_correspondents"]), 0)
        self.assertEqual(len(impact["affected_types"]), 0)
        self.assertEqual(len(impact["affected_tags"]), 0)

    def test_analyze_impact_date_range(self):
        """Test that date range is properly calculated."""
        # Create documents with different dates
        doc1 = Document.objects.create(
            title="Old Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )
        # Force set the created date to an earlier time
        doc1.created = timezone.make_aware(datetime(2023, 1, 1))
        doc1.save()

        doc2 = Document.objects.create(
            title="New Document",
            content="Content",
            checksum="checksum2",
            mime_type="application/pdf",
        )
        doc2.created = timezone.make_aware(datetime(2024, 12, 31))
        doc2.save()

        impact = AIDeletionManager._analyze_impact([doc1, doc2])

        self.assertIsNotNone(impact["date_range"]["earliest"])
        self.assertIsNotNone(impact["date_range"]["latest"])
        # Check that dates are ISO formatted strings
        self.assertIn("2023-01-01", impact["date_range"]["earliest"])
        self.assertIn("2024-12-31", impact["date_range"]["latest"])

    def test_analyze_impact_empty_list(self):
        """Test impact analysis with empty document list."""
        impact = AIDeletionManager._analyze_impact([])

        self.assertEqual(impact["document_count"], 0)
        self.assertEqual(len(impact["documents"]), 0)
        self.assertEqual(len(impact["affected_correspondents"]), 0)
        self.assertEqual(len(impact["affected_types"]), 0)
        self.assertEqual(len(impact["affected_tags"]), 0)


class TestAIDeletionManagerFormatRequest(TestCase):
    """Test format_deletion_request_for_user() functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass")

        self.correspondent = Correspondent.objects.create(name="Test Corp")
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.tag = Tag.objects.create(name="Important")

        self.doc = Document.objects.create(
            title="Test Document",
            content="Test content",
            checksum="checksum1",
            mime_type="application/pdf",
            correspondent=self.correspondent,
            document_type=self.doc_type,
        )
        self.doc.tags.add(self.tag)

    def test_format_deletion_request_basic(self):
        """Test basic formatting of deletion request."""
        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Test reason for deletion",
            user=self.user,
        )

        message = AIDeletionManager.format_deletion_request_for_user(request)

        self.assertIsInstance(message, str)
        self.assertIn("AI DELETION REQUEST", message)
        self.assertIn("Test reason for deletion", message)
        self.assertIn("Test Document", message)
        self.assertIn("REQUIRED ACTION", message)

    def test_format_deletion_request_includes_impact_summary(self):
        """Test that formatted message includes impact summary."""
        doc2 = Document.objects.create(
            title="Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
        )

        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc, doc2],
            reason="Multiple documents",
            user=self.user,
        )

        message = AIDeletionManager.format_deletion_request_for_user(request)

        self.assertIn("Number of documents: 2", message)
        self.assertIn("Test Corp", message)
        self.assertIn("Invoice", message)
        self.assertIn("Important", message)

    def test_format_deletion_request_with_no_metadata(self):
        """Test formatting when documents have no metadata."""
        doc = Document.objects.create(
            title="Basic Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

        request = AIDeletionManager.create_deletion_request(
            documents=[doc],
            reason="Test deletion",
            user=self.user,
        )

        message = AIDeletionManager.format_deletion_request_for_user(request)

        self.assertIn("Basic Document", message)
        self.assertIn("None", message)  # Should show None for missing metadata

    def test_format_deletion_request_shows_security_warning(self):
        """Test that formatted message emphasizes user approval requirement."""
        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Test",
            user=self.user,
        )

        message = AIDeletionManager.format_deletion_request_for_user(request)

        self.assertIn("explicit approval", message.lower())
        self.assertIn("no files will be deleted until you confirm", message.lower())


class TestAIDeletionManagerGetPendingRequests(TestCase):
    """Test get_pending_requests() functionality."""

    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(username="user1", password="pass1")
        self.user2 = User.objects.create_user(username="user2", password="pass2")

        self.doc = Document.objects.create(
            title="Test Document",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

    def test_get_pending_requests_for_user(self):
        """Test getting pending requests for a specific user."""
        # Create requests for user1
        req1 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 1",
            user=self.user1,
        )
        req2 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 2",
            user=self.user1,
        )

        # Create request for user2
        AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 3",
            user=self.user2,
        )

        pending = AIDeletionManager.get_pending_requests(self.user1)

        self.assertEqual(len(pending), 2)
        self.assertIn(req1, pending)
        self.assertIn(req2, pending)

    def test_get_pending_requests_excludes_approved(self):
        """Test that approved requests are not returned."""
        req1 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 1",
            user=self.user1,
        )
        req2 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 2",
            user=self.user1,
        )

        # Approve one request
        req1.approve(self.user1, "Approved")

        pending = AIDeletionManager.get_pending_requests(self.user1)

        self.assertEqual(len(pending), 1)
        self.assertNotIn(req1, pending)
        self.assertIn(req2, pending)

    def test_get_pending_requests_excludes_rejected(self):
        """Test that rejected requests are not returned."""
        req1 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 1",
            user=self.user1,
        )
        req2 = AIDeletionManager.create_deletion_request(
            documents=[self.doc],
            reason="Reason 2",
            user=self.user1,
        )

        # Reject one request
        req1.reject(self.user1, "Rejected")

        pending = AIDeletionManager.get_pending_requests(self.user1)

        self.assertEqual(len(pending), 1)
        self.assertNotIn(req1, pending)
        self.assertIn(req2, pending)

    def test_get_pending_requests_empty(self):
        """Test getting pending requests when none exist."""
        pending = AIDeletionManager.get_pending_requests(self.user1)

        self.assertEqual(len(pending), 0)


class TestAIDeletionManagerSecurityConstraints(TestCase):
    """Test security constraints and AI deletion prevention."""

    def test_can_ai_delete_automatically_always_false(self):
        """Test that AI can never delete automatically."""
        # This is a critical security test
        result = AIDeletionManager.can_ai_delete_automatically()

        self.assertFalse(result)

    def test_deletion_request_requires_pending_status(self):
        """Test that all new deletion requests start as pending."""
        user = User.objects.create_user(username="testuser", password="pass")
        doc = Document.objects.create(
            title="Test",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

        request = AIDeletionManager.create_deletion_request(
            documents=[doc],
            reason="Test",
            user=user,
        )

        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)

    def test_deletion_request_marked_as_ai_initiated(self):
        """Test that deletion requests are marked as AI-initiated."""
        user = User.objects.create_user(username="testuser", password="pass")
        doc = Document.objects.create(
            title="Test",
            content="Content",
            checksum="checksum1",
            mime_type="application/pdf",
        )

        request = AIDeletionManager.create_deletion_request(
            documents=[doc],
            reason="Test",
            user=user,
        )

        self.assertTrue(request.requested_by_ai)


class TestAIDeletionManagerWorkflow(TestCase):
    """Test complete deletion workflow."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.approver = User.objects.create_user(username="approver", password="pass")

        self.doc1 = Document.objects.create(
            title="Document 1",
            content="Content 1",
            checksum="checksum1",
            mime_type="application/pdf",
        )
        self.doc2 = Document.objects.create(
            title="Document 2",
            content="Content 2",
            checksum="checksum2",
            mime_type="application/pdf",
        )

    def test_complete_approval_workflow(self):
        """Test complete workflow from creation to approval."""
        # Step 1: Create deletion request
        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc1, self.doc2],
            reason="Duplicates detected",
            user=self.user,
        )

        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)
        self.assertIsNone(request.reviewed_at)
        self.assertIsNone(request.reviewed_by)

        # Step 2: Approve request
        success = request.approve(self.approver, "Looks good")

        self.assertTrue(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_APPROVED)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertEqual(request.review_comment, "Looks good")

    def test_complete_rejection_workflow(self):
        """Test complete workflow from creation to rejection."""
        # Step 1: Create deletion request
        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc1],
            reason="Should be deleted",
            user=self.user,
        )

        self.assertEqual(request.status, DeletionRequest.STATUS_PENDING)

        # Step 2: Reject request
        success = request.reject(self.approver, "Not a duplicate")

        self.assertTrue(success)
        self.assertEqual(request.status, DeletionRequest.STATUS_REJECTED)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertEqual(request.review_comment, "Not a duplicate")

    def test_workflow_audit_trail(self):
        """Test that workflow maintains complete audit trail."""
        request = AIDeletionManager.create_deletion_request(
            documents=[self.doc1],
            reason="Test deletion",
            user=self.user,
        )

        # Record initial state
        created_at = request.created_at
        self.assertIsNotNone(created_at)

        # Approve
        request.approve(self.approver, "Approved")

        # Verify audit trail
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)
        self.assertIsNotNone(request.reviewed_at)
        self.assertEqual(request.reviewed_by, self.approver)
        self.assertTrue(request.requested_by_ai)
        self.assertEqual(request.user, self.user)
