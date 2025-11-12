"""
Integration tests for AI API endpoints.

Tests cover:
- AI suggestions endpoint (POST /api/ai/suggestions/)
- Apply AI suggestions endpoint (POST /api/ai/suggestions/apply/)
- AI configuration endpoint (GET/POST /api/ai/config/)
- Deletion approval endpoint (POST /api/ai/deletions/approve/)
- Permission checks for all endpoints
- Request/response validation
"""

from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import (
    Correspondent,
    DeletionRequest,
    Document,
    DocumentType,
    StoragePath,
    Tag,
)
from documents.tests.utils import DirectoriesMixin


class TestAISuggestionsEndpoint(DirectoriesMixin, APITestCase):
    """Test the AI suggestions endpoint."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123"
        )
        self.user_with_permission = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123"
        )
        self.user_without_permission = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123"
        )
        
        # Assign view permission
        content_type = ContentType.objects.get_for_model(Document)
        view_permission, _ = Permission.objects.get_or_create(
            codename="can_view_ai_suggestions",
            name="Can view AI suggestions",
            content_type=content_type,
        )
        self.user_with_permission.user_permissions.add(view_permission)
        
        # Create test document
        self.document = Document.objects.create(
            title="Test Document",
            content="This is a test invoice from ACME Corporation"
        )
        
        # Create test metadata objects
        self.tag = Tag.objects.create(name="Invoice")
        self.correspondent = Correspondent.objects.create(name="ACME Corp")
        self.doc_type = DocumentType.objects.create(name="Invoice")

    def test_unauthorized_access_denied(self):
        """Test that unauthenticated users are denied."""
        response = self.client.post(
            "/api/ai/suggestions/",
            {"document_id": self.document.id},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_permission_denied(self):
        """Test that users without permission are denied."""
        self.client.force_authenticate(user=self.user_without_permission)
        
        response = self.client.post(
            "/api/ai/suggestions/",
            {"document_id": self.document.id},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_allowed(self):
        """Test that superusers can access the endpoint."""
        self.client.force_authenticate(user=self.superuser)
        
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            # Mock the scanner response
            mock_scan_result = mock.MagicMock()
            mock_scan_result.tags = [(self.tag.id, 0.85)]
            mock_scan_result.correspondent = (self.correspondent.id, 0.90)
            mock_scan_result.document_type = (self.doc_type.id, 0.80)
            mock_scan_result.storage_path = None
            mock_scan_result.title_suggestion = "Invoice - ACME Corp"
            mock_scan_result.custom_fields = {}
            
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.scan_document.return_value = mock_scan_result
            mock_scanner.return_value = mock_scanner_instance
            
            response = self.client.post(
                "/api/ai/suggestions/",
                {"document_id": self.document.id},
                format="json"
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("document_id", response.data)
        self.assertEqual(response.data["document_id"], self.document.id)

    def test_user_with_permission_allowed(self):
        """Test that users with permission can access the endpoint."""
        self.client.force_authenticate(user=self.user_with_permission)
        
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            # Mock the scanner response
            mock_scan_result = mock.MagicMock()
            mock_scan_result.tags = []
            mock_scan_result.correspondent = None
            mock_scan_result.document_type = None
            mock_scan_result.storage_path = None
            mock_scan_result.title_suggestion = None
            mock_scan_result.custom_fields = {}
            
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.scan_document.return_value = mock_scan_result
            mock_scanner.return_value = mock_scanner_instance
            
            response = self.client.post(
                "/api/ai/suggestions/",
                {"document_id": self.document.id},
                format="json"
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_document_id(self):
        """Test handling of invalid document ID."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/suggestions/",
            {"document_id": 99999},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_document_id(self):
        """Test handling of missing document ID."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/suggestions/",
            {},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestApplyAISuggestionsEndpoint(DirectoriesMixin, APITestCase):
    """Test the apply AI suggestions endpoint."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123"
        )
        self.user_with_permission = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123"
        )
        
        # Assign apply permission
        content_type = ContentType.objects.get_for_model(Document)
        apply_permission, _ = Permission.objects.get_or_create(
            codename="can_apply_ai_suggestions",
            name="Can apply AI suggestions",
            content_type=content_type,
        )
        self.user_with_permission.user_permissions.add(apply_permission)
        
        # Create test document
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content"
        )
        
        # Create test metadata
        self.tag = Tag.objects.create(name="Test Tag")
        self.correspondent = Correspondent.objects.create(name="Test Corp")

    def test_unauthorized_access_denied(self):
        """Test that unauthenticated users are denied."""
        response = self.client.post(
            "/api/ai/suggestions/apply/",
            {"document_id": self.document.id},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_apply_tags_success(self):
        """Test successfully applying tag suggestions."""
        self.client.force_authenticate(user=self.superuser)
        
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            # Mock the scanner response
            mock_scan_result = mock.MagicMock()
            mock_scan_result.tags = [(self.tag.id, 0.85)]
            mock_scan_result.correspondent = None
            mock_scan_result.document_type = None
            mock_scan_result.storage_path = None
            mock_scan_result.title_suggestion = None
            mock_scan_result.custom_fields = {}
            
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.scan_document.return_value = mock_scan_result
            mock_scanner_instance.auto_apply_threshold = 0.80
            mock_scanner.return_value = mock_scanner_instance
            
            response = self.client.post(
                "/api/ai/suggestions/apply/",
                {
                    "document_id": self.document.id,
                    "apply_tags": True
                },
                format="json"
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

    def test_apply_correspondent_success(self):
        """Test successfully applying correspondent suggestion."""
        self.client.force_authenticate(user=self.superuser)
        
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            # Mock the scanner response
            mock_scan_result = mock.MagicMock()
            mock_scan_result.tags = []
            mock_scan_result.correspondent = (self.correspondent.id, 0.90)
            mock_scan_result.document_type = None
            mock_scan_result.storage_path = None
            mock_scan_result.title_suggestion = None
            mock_scan_result.custom_fields = {}
            
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.scan_document.return_value = mock_scan_result
            mock_scanner_instance.auto_apply_threshold = 0.80
            mock_scanner.return_value = mock_scanner_instance
            
            response = self.client.post(
                "/api/ai/suggestions/apply/",
                {
                    "document_id": self.document.id,
                    "apply_correspondent": True
                },
                format="json"
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify correspondent was applied
        self.document.refresh_from_db()
        self.assertEqual(self.document.correspondent, self.correspondent)


class TestAIConfigurationEndpoint(DirectoriesMixin, APITestCase):
    """Test the AI configuration endpoint."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123"
        )
        self.user_without_permission = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123"
        )

    def test_unauthorized_access_denied(self):
        """Test that unauthenticated users are denied."""
        response = self.client.get("/api/ai/config/")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_permission_denied(self):
        """Test that users without permission are denied."""
        self.client.force_authenticate(user=self.user_without_permission)
        
        response = self.client.get("/api/ai/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_config_success(self):
        """Test getting AI configuration."""
        self.client.force_authenticate(user=self.superuser)
        
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.auto_apply_threshold = 0.80
            mock_scanner_instance.suggest_threshold = 0.60
            mock_scanner_instance.ml_enabled = True
            mock_scanner_instance.advanced_ocr_enabled = True
            mock_scanner.return_value = mock_scanner_instance
            
            response = self.client.get("/api/ai/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auto_apply_threshold", response.data)
        self.assertEqual(response.data["auto_apply_threshold"], 0.80)

    def test_update_config_success(self):
        """Test updating AI configuration."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/config/",
            {
                "auto_apply_threshold": 0.90,
                "suggest_threshold": 0.70
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

    def test_update_config_invalid_threshold(self):
        """Test updating with invalid threshold value."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/config/",
            {
                "auto_apply_threshold": 1.5  # Invalid: > 1.0
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDeletionApprovalEndpoint(DirectoriesMixin, APITestCase):
    """Test the deletion approval endpoint."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123"
        )
        self.user_with_permission = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123"
        )
        self.user_without_permission = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123"
        )
        
        # Assign approval permission
        content_type = ContentType.objects.get_for_model(Document)
        approval_permission, _ = Permission.objects.get_or_create(
            codename="can_approve_deletions",
            name="Can approve AI-recommended deletions",
            content_type=content_type,
        )
        self.user_with_permission.user_permissions.add(approval_permission)
        
        # Create test deletion request
        self.deletion_request = DeletionRequest.objects.create(
            user=self.user_with_permission,
            requested_by_ai=True,
            ai_reason="Document appears to be a duplicate"
        )

    def test_unauthorized_access_denied(self):
        """Test that unauthenticated users are denied."""
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": self.deletion_request.id,
                "action": "approve"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_permission_denied(self):
        """Test that users without permission are denied."""
        self.client.force_authenticate(user=self.user_without_permission)
        
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": self.deletion_request.id,
                "action": "approve"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approve_deletion_success(self):
        """Test successfully approving a deletion request."""
        self.client.force_authenticate(user=self.user_with_permission)
        
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": self.deletion_request.id,
                "action": "approve"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        
        # Verify status was updated
        self.deletion_request.refresh_from_db()
        self.assertEqual(
            self.deletion_request.status,
            DeletionRequest.STATUS_APPROVED
        )

    def test_reject_deletion_success(self):
        """Test successfully rejecting a deletion request."""
        self.client.force_authenticate(user=self.user_with_permission)
        
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": self.deletion_request.id,
                "action": "reject",
                "reason": "Document is still needed"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status was updated
        self.deletion_request.refresh_from_db()
        self.assertEqual(
            self.deletion_request.status,
            DeletionRequest.STATUS_REJECTED
        )

    def test_invalid_request_id(self):
        """Test handling of invalid deletion request ID."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": 99999,
                "action": "approve"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_superuser_can_approve_any_request(self):
        """Test that superusers can approve any deletion request."""
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(
            "/api/ai/deletions/approve/",
            {
                "request_id": self.deletion_request.id,
                "action": "approve"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestEndpointPermissionIntegration(DirectoriesMixin, APITestCase):
    """Test permission integration across all AI endpoints."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create user with all AI permissions
        self.power_user = User.objects.create_user(
            username="power_user", email="power@test.com", password="power123"
        )
        
        content_type = ContentType.objects.get_for_model(Document)
        
        # Assign all AI permissions
        permissions = [
            "can_view_ai_suggestions",
            "can_apply_ai_suggestions",
            "can_approve_deletions",
            "can_configure_ai",
        ]
        
        for codename in permissions:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                name=f"Can {codename.replace('_', ' ')}",
                content_type=content_type,
            )
            self.power_user.user_permissions.add(perm)
        
        self.document = Document.objects.create(
            title="Test Doc",
            content="Test"
        )

    def test_power_user_can_access_all_endpoints(self):
        """Test that user with all permissions can access all endpoints."""
        self.client.force_authenticate(user=self.power_user)
        
        # Test suggestions endpoint
        with mock.patch('documents.views.get_ai_scanner') as mock_scanner:
            mock_scan_result = mock.MagicMock()
            mock_scan_result.tags = []
            mock_scan_result.correspondent = None
            mock_scan_result.document_type = None
            mock_scan_result.storage_path = None
            mock_scan_result.title_suggestion = None
            mock_scan_result.custom_fields = {}
            
            mock_scanner_instance = mock.MagicMock()
            mock_scanner_instance.scan_document.return_value = mock_scan_result
            mock_scanner_instance.auto_apply_threshold = 0.80
            mock_scanner_instance.suggest_threshold = 0.60
            mock_scanner_instance.ml_enabled = True
            mock_scanner_instance.advanced_ocr_enabled = True
            mock_scanner.return_value = mock_scanner_instance
            
            response1 = self.client.post(
                "/api/ai/suggestions/",
                {"document_id": self.document.id},
                format="json"
            )
            self.assertEqual(response1.status_code, status.HTTP_200_OK)
            
            # Test apply endpoint
            response2 = self.client.post(
                "/api/ai/suggestions/apply/",
                {
                    "document_id": self.document.id,
                    "apply_tags": False
                },
                format="json"
            )
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            
            # Test config endpoint
            response3 = self.client.get("/api/ai/config/")
            self.assertEqual(response3.status_code, status.HTTP_200_OK)
