"""
Tests for AI Suggestions API endpoints.
"""

from unittest import mock

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from documents.ai_scanner import AIScanResult
from documents.models import (
    AISuggestionFeedback,
    Correspondent,
    Document,
    DocumentType,
    StoragePath,
    Tag,
)
from documents.tests.utils import DirectoriesMixin


class TestAISuggestionsAPI(DirectoriesMixin, APITestCase):
    """Test cases for AI suggestions API endpoints."""

    def setUp(self):
        super().setUp()
        
        # Create test user
        self.user = User.objects.create_superuser(username="test_admin")
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.correspondent = Correspondent.objects.create(
            name="Test Corp",
            pk=1,
        )
        self.doc_type = DocumentType.objects.create(
            name="Invoice",
            pk=1,
        )
        self.tag1 = Tag.objects.create(
            name="Important",
            pk=1,
        )
        self.tag2 = Tag.objects.create(
            name="Urgent",
            pk=2,
        )
        self.storage_path = StoragePath.objects.create(
            name="Archive",
            path="/archive/",
            pk=1,
        )
        
        # Create test document
        self.document = Document.objects.create(
            title="Test Document",
            content="This is a test document with some content for AI analysis.",
            checksum="abc123",
            mime_type="application/pdf",
        )

    def test_ai_suggestions_endpoint_exists(self):
        """Test that the ai-suggestions endpoint is accessible."""
        response = self.client.get(
            f"/api/documents/{self.document.pk}/ai-suggestions/"
        )
        # Should not be 404
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('documents.ai_scanner.get_ai_scanner')
    def test_get_ai_suggestions_success(self, mock_get_scanner):
        """Test successfully getting AI suggestions for a document."""
        # Create mock scan result
        scan_result = AIScanResult()
        scan_result.tags = [(self.tag1.id, 0.85), (self.tag2.id, 0.75)]
        scan_result.correspondent = (self.correspondent.id, 0.90)
        scan_result.document_type = (self.doc_type.id, 0.88)
        scan_result.storage_path = (self.storage_path.id, 0.80)
        scan_result.title_suggestion = "Suggested Title"
        
        # Mock scanner
        mock_scanner = mock.Mock()
        mock_scanner.scan_document.return_value = scan_result
        mock_get_scanner.return_value = mock_scanner
        
        # Make request
        response = self.client.get(
            f"/api/documents/{self.document.pk}/ai-suggestions/"
        )
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Check tags
        self.assertIn('tags', data)
        self.assertEqual(len(data['tags']), 2)
        self.assertEqual(data['tags'][0]['id'], self.tag1.id)
        self.assertEqual(data['tags'][0]['confidence'], 0.85)
        
        # Check correspondent
        self.assertIn('correspondent', data)
        self.assertEqual(data['correspondent']['id'], self.correspondent.id)
        self.assertEqual(data['correspondent']['confidence'], 0.90)
        
        # Check document type
        self.assertIn('document_type', data)
        self.assertEqual(data['document_type']['id'], self.doc_type.id)
        
        # Check title suggestion
        self.assertIn('title_suggestion', data)
        self.assertEqual(data['title_suggestion']['title'], "Suggested Title")

    def test_get_ai_suggestions_no_content(self):
        """Test getting AI suggestions for document without content."""
        # Create document without content
        doc = Document.objects.create(
            title="Empty Document",
            content="",
            checksum="empty123",
            mime_type="application/pdf",
        )
        
        response = self.client.get(f"/api/documents/{doc.pk}/ai-suggestions/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no content", response.json()['detail'].lower())

    def test_get_ai_suggestions_document_not_found(self):
        """Test getting AI suggestions for non-existent document."""
        response = self.client.get("/api/documents/99999/ai-suggestions/")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_apply_suggestion_tag(self):
        """Test applying a tag suggestion."""
        request_data = {
            'suggestion_type': 'tag',
            'value_id': self.tag1.id,
            'confidence': 0.85,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'success')
        
        # Verify tag was applied
        self.document.refresh_from_db()
        self.assertIn(self.tag1, self.document.tags.all())
        
        # Verify feedback was recorded
        feedback = AISuggestionFeedback.objects.filter(
            document=self.document,
            suggestion_type='tag',
        ).first()
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback.status, AISuggestionFeedback.STATUS_APPLIED)
        self.assertEqual(feedback.suggested_value_id, self.tag1.id)
        self.assertEqual(feedback.confidence, 0.85)
        self.assertEqual(feedback.user, self.user)

    def test_apply_suggestion_correspondent(self):
        """Test applying a correspondent suggestion."""
        request_data = {
            'suggestion_type': 'correspondent',
            'value_id': self.correspondent.id,
            'confidence': 0.90,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify correspondent was applied
        self.document.refresh_from_db()
        self.assertEqual(self.document.correspondent, self.correspondent)
        
        # Verify feedback was recorded
        feedback = AISuggestionFeedback.objects.filter(
            document=self.document,
            suggestion_type='correspondent',
        ).first()
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback.status, AISuggestionFeedback.STATUS_APPLIED)

    def test_apply_suggestion_document_type(self):
        """Test applying a document type suggestion."""
        request_data = {
            'suggestion_type': 'document_type',
            'value_id': self.doc_type.id,
            'confidence': 0.88,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify document type was applied
        self.document.refresh_from_db()
        self.assertEqual(self.document.document_type, self.doc_type)

    def test_apply_suggestion_title(self):
        """Test applying a title suggestion."""
        request_data = {
            'suggestion_type': 'title',
            'value_text': 'New Suggested Title',
            'confidence': 0.80,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify title was applied
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, 'New Suggested Title')

    def test_apply_suggestion_invalid_type(self):
        """Test applying suggestion with invalid type."""
        request_data = {
            'suggestion_type': 'invalid_type',
            'value_id': 1,
            'confidence': 0.85,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_suggestion_missing_value(self):
        """Test applying suggestion without value_id or value_text."""
        request_data = {
            'suggestion_type': 'tag',
            'confidence': 0.85,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_suggestion_nonexistent_object(self):
        """Test applying suggestion with non-existent object ID."""
        request_data = {
            'suggestion_type': 'tag',
            'value_id': 99999,
            'confidence': 0.85,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reject_suggestion(self):
        """Test rejecting an AI suggestion."""
        request_data = {
            'suggestion_type': 'tag',
            'value_id': self.tag1.id,
            'confidence': 0.65,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/reject-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'success')
        
        # Verify feedback was recorded
        feedback = AISuggestionFeedback.objects.filter(
            document=self.document,
            suggestion_type='tag',
        ).first()
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback.status, AISuggestionFeedback.STATUS_REJECTED)
        self.assertEqual(feedback.suggested_value_id, self.tag1.id)
        self.assertEqual(feedback.confidence, 0.65)
        self.assertEqual(feedback.user, self.user)

    def test_reject_suggestion_with_text(self):
        """Test rejecting a suggestion with text value."""
        request_data = {
            'suggestion_type': 'title',
            'value_text': 'Bad Title Suggestion',
            'confidence': 0.50,
        }
        
        response = self.client.post(
            f"/api/documents/{self.document.pk}/reject-suggestion/",
            data=request_data,
            format='json',
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify feedback was recorded
        feedback = AISuggestionFeedback.objects.filter(
            document=self.document,
            suggestion_type='title',
        ).first()
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback.status, AISuggestionFeedback.STATUS_REJECTED)
        self.assertEqual(feedback.suggested_value_text, 'Bad Title Suggestion')

    def test_ai_suggestion_stats_empty(self):
        """Test getting statistics when no feedback exists."""
        response = self.client.get("/api/documents/ai-suggestion-stats/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['total_suggestions'], 0)
        self.assertEqual(data['total_applied'], 0)
        self.assertEqual(data['total_rejected'], 0)
        self.assertEqual(data['accuracy_rate'], 0)

    def test_ai_suggestion_stats_with_data(self):
        """Test getting statistics with feedback data."""
        # Create some feedback entries
        AISuggestionFeedback.objects.create(
            document=self.document,
            suggestion_type='tag',
            suggested_value_id=self.tag1.id,
            confidence=0.85,
            status=AISuggestionFeedback.STATUS_APPLIED,
            user=self.user,
        )
        AISuggestionFeedback.objects.create(
            document=self.document,
            suggestion_type='tag',
            suggested_value_id=self.tag2.id,
            confidence=0.70,
            status=AISuggestionFeedback.STATUS_APPLIED,
            user=self.user,
        )
        AISuggestionFeedback.objects.create(
            document=self.document,
            suggestion_type='correspondent',
            suggested_value_id=self.correspondent.id,
            confidence=0.60,
            status=AISuggestionFeedback.STATUS_REJECTED,
            user=self.user,
        )
        
        response = self.client.get("/api/documents/ai-suggestion-stats/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Check overall stats
        self.assertEqual(data['total_suggestions'], 3)
        self.assertEqual(data['total_applied'], 2)
        self.assertEqual(data['total_rejected'], 1)
        self.assertAlmostEqual(data['accuracy_rate'], 66.67, places=1)
        
        # Check by_type stats
        self.assertIn('by_type', data)
        self.assertIn('tag', data['by_type'])
        self.assertEqual(data['by_type']['tag']['total'], 2)
        self.assertEqual(data['by_type']['tag']['applied'], 2)
        self.assertEqual(data['by_type']['tag']['rejected'], 0)
        
        # Check confidence averages
        self.assertGreater(data['average_confidence_applied'], 0)
        self.assertGreater(data['average_confidence_rejected'], 0)
        
        # Check recent suggestions
        self.assertIn('recent_suggestions', data)
        self.assertEqual(len(data['recent_suggestions']), 3)

    def test_ai_suggestion_stats_accuracy_calculation(self):
        """Test that accuracy rate is calculated correctly."""
        # Create 7 applied and 3 rejected = 70% accuracy
        for i in range(7):
            AISuggestionFeedback.objects.create(
                document=self.document,
                suggestion_type='tag',
                suggested_value_id=self.tag1.id,
                confidence=0.80,
                status=AISuggestionFeedback.STATUS_APPLIED,
                user=self.user,
            )
        
        for i in range(3):
            AISuggestionFeedback.objects.create(
                document=self.document,
                suggestion_type='tag',
                suggested_value_id=self.tag2.id,
                confidence=0.60,
                status=AISuggestionFeedback.STATUS_REJECTED,
                user=self.user,
            )
        
        response = self.client.get("/api/documents/ai-suggestion-stats/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data['total_suggestions'], 10)
        self.assertEqual(data['total_applied'], 7)
        self.assertEqual(data['total_rejected'], 3)
        self.assertEqual(data['accuracy_rate'], 70.0)

    def test_authentication_required(self):
        """Test that authentication is required for all endpoints."""
        self.client.force_authenticate(user=None)
        
        # Test ai-suggestions endpoint
        response = self.client.get(
            f"/api/documents/{self.document.pk}/ai-suggestions/"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test apply-suggestion endpoint
        response = self.client.post(
            f"/api/documents/{self.document.pk}/apply-suggestion/",
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test reject-suggestion endpoint
        response = self.client.post(
            f"/api/documents/{self.document.pk}/reject-suggestion/",
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test stats endpoint
        response = self.client.get("/api/documents/ai-suggestion-stats/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
