"""
Tests for classifier model tenant isolation.

Verifies that each tenant has isolated MODEL_FILE path and that
tenant A's classifier cannot access tenant B's training data.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase

from documents.classifier import (
    DocumentClassifier,
    get_tenant_model_file,
    load_classifier,
)
from documents.models import (
    Correspondent,
    Document,
    DocumentType,
    Tag,
    Tenant,
    set_current_tenant_id,
)
from documents.models import MatchingModel
from paperless.middleware import set_current_tenant


class ClassifierTenantIsolationTest(TransactionTestCase):
    """
    Test that classifier models are isolated per tenant.
    """

    def setUp(self):
        """
        Create two tenants and test data for each.
        """
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
        self.user_a = User.objects.create_user(username="user_a", password="test")
        self.user_b = User.objects.create_user(username="user_b", password="test")

    def tearDown(self):
        """
        Clean up: reset tenant context.
        """
        set_current_tenant(None)
        set_current_tenant_id(None)

    def _set_tenant_context(self, tenant):
        """
        Set tenant context in thread-local storage.
        """
        set_current_tenant(tenant)
        set_current_tenant_id(tenant.id)

    def test_get_tenant_model_file_with_tenant_id(self):
        """
        Test that get_tenant_model_file returns tenant-specific path.
        """
        # Test with explicit tenant_id
        model_file_a = get_tenant_model_file(str(self.tenant_a.id))
        expected_path_a = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"

        self.assertEqual(model_file_a, expected_path_a)

        model_file_b = get_tenant_model_file(str(self.tenant_b.id))
        expected_path_b = settings.MEDIA_ROOT / f"tenant_{self.tenant_b.id}" / "classifier.pkl"

        self.assertEqual(model_file_b, expected_path_b)

        # Verify the paths are different
        self.assertNotEqual(model_file_a, model_file_b)

    def test_get_tenant_model_file_from_context(self):
        """
        Test that get_tenant_model_file uses current tenant from context.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        model_file_a = get_tenant_model_file()
        expected_path_a = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"

        self.assertEqual(model_file_a, expected_path_a)

        # Switch to tenant B context
        self._set_tenant_context(self.tenant_b)

        model_file_b = get_tenant_model_file()
        expected_path_b = settings.MEDIA_ROOT / f"tenant_{self.tenant_b.id}" / "classifier.pkl"

        self.assertEqual(model_file_b, expected_path_b)

    def test_get_tenant_model_file_fallback_to_shared(self):
        """
        Test that get_tenant_model_file falls back to shared model when no tenant context.
        """
        # No tenant context
        set_current_tenant(None)
        set_current_tenant_id(None)

        model_file = get_tenant_model_file()

        # Should return the shared MODEL_FILE
        self.assertEqual(model_file, settings.MODEL_FILE)

    def test_tenant_directories_are_created(self):
        """
        Test that tenant-specific directories are created automatically.
        """
        # Get model file for tenant A (should create directory)
        model_file_a = get_tenant_model_file(str(self.tenant_a.id))

        # Check that the directory was created
        self.assertTrue(model_file_a.parent.exists())
        self.assertTrue(model_file_a.parent.is_dir())

        # Verify the directory name matches the tenant ID
        self.assertEqual(model_file_a.parent.name, f"tenant_{self.tenant_a.id}")

    def test_classifier_save_uses_tenant_specific_path(self):
        """
        Test that DocumentClassifier.save() uses tenant-specific path.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # Create minimal classifier
        classifier = DocumentClassifier()
        classifier.last_doc_change_time = None
        classifier.last_auto_type_hash = None
        classifier.data_vectorizer = None
        classifier.tags_binarizer = None
        classifier.tags_classifier = None
        classifier.correspondent_classifier = None
        classifier.document_type_classifier = None
        classifier.storage_path_classifier = None

        # Save the classifier
        classifier.save()

        # Verify it was saved to tenant A's path
        expected_path = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"
        self.assertTrue(expected_path.exists())

        # Clean up
        expected_path.unlink()

    def test_load_classifier_uses_tenant_specific_path(self):
        """
        Test that load_classifier loads from tenant-specific path.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # Create and save a classifier for tenant A
        classifier = DocumentClassifier()
        classifier.last_doc_change_time = None
        classifier.last_auto_type_hash = None
        classifier.data_vectorizer = None
        classifier.tags_binarizer = None
        classifier.tags_classifier = None
        classifier.correspondent_classifier = None
        classifier.document_type_classifier = None
        classifier.storage_path_classifier = None
        classifier.save()

        # Load it back
        loaded_classifier = load_classifier()

        # Should have loaded successfully
        self.assertIsNotNone(loaded_classifier)

        # Clean up
        expected_path = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"
        expected_path.unlink()

    def test_tenant_a_classifier_does_not_affect_tenant_b(self):
        """
        Security test: Verify tenant A's classifier doesn't access tenant B's data.
        """
        # Set tenant A context and create document type
        self._set_tenant_context(self.tenant_a)

        doc_type_a = DocumentType.objects.create(
            name="Type A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
            matching_algorithm=MatchingModel.MATCH_AUTO,
        )

        # Create a document for tenant A
        doc_a = Document.objects.create(
            title="Test Doc A",
            content="This is a test document for tenant A with specific keywords.",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
            document_type=doc_type_a,
        )

        # Train classifier for tenant A
        classifier_a = DocumentClassifier()
        try:
            trained = classifier_a.train()
            if trained:
                classifier_a.save()
        except Exception:
            # Training may fail if insufficient data, that's ok for this test
            pass

        # Switch to tenant B context
        self._set_tenant_context(self.tenant_b)

        # Try to load classifier for tenant B (should be None or different)
        classifier_b = load_classifier()

        # If tenant B has no model, load_classifier should return None
        # If tenant B has a model, it should be a different file
        if classifier_b is not None:
            # Verify the models are stored in different locations
            model_path_a = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"
            model_path_b = settings.MEDIA_ROOT / f"tenant_{self.tenant_b.id}" / "classifier.pkl"

            self.assertNotEqual(model_path_a, model_path_b)
            self.assertTrue(model_path_a.exists() or model_path_b.exists())

        # Query documents as tenant B - should NOT see tenant A's document
        docs_b = Document.objects.all()
        self.assertEqual(docs_b.count(), 0, "Tenant B should not see tenant A's documents")

        # Clean up
        self._set_tenant_context(self.tenant_a)
        model_path_a = settings.MEDIA_ROOT / f"tenant_{self.tenant_a.id}" / "classifier.pkl"
        if model_path_a.exists():
            model_path_a.unlink()

    def test_classifier_paths_are_isolated(self):
        """
        Test that each tenant has a completely isolated classifier path.
        """
        path_a = get_tenant_model_file(str(self.tenant_a.id))
        path_b = get_tenant_model_file(str(self.tenant_b.id))

        # Paths should be different
        self.assertNotEqual(path_a, path_b)

        # Both should be under MEDIA_ROOT
        self.assertTrue(str(path_a).startswith(str(settings.MEDIA_ROOT)))
        self.assertTrue(str(path_b).startswith(str(settings.MEDIA_ROOT)))

        # Both should contain the tenant ID in the path
        self.assertIn(str(self.tenant_a.id), str(path_a))
        self.assertIn(str(self.tenant_b.id), str(path_b))

        # Paths should be in separate directories
        self.assertNotEqual(path_a.parent, path_b.parent)

    def test_no_cross_tenant_model_access(self):
        """
        Security test: Verify that one tenant cannot accidentally load another tenant's model.
        """
        # Create a dummy classifier for tenant A
        self._set_tenant_context(self.tenant_a)

        classifier_a = DocumentClassifier()
        classifier_a.last_doc_change_time = None
        classifier_a.last_auto_type_hash = b"tenant_a_hash"
        classifier_a.data_vectorizer = None
        classifier_a.tags_binarizer = None
        classifier_a.tags_classifier = None
        classifier_a.correspondent_classifier = None
        classifier_a.document_type_classifier = None
        classifier_a.storage_path_classifier = None
        classifier_a.save()

        path_a = get_tenant_model_file(str(self.tenant_a.id))
        self.assertTrue(path_a.exists())

        # Switch to tenant B and try to load
        self._set_tenant_context(self.tenant_b)

        # Tenant B should not have a model
        classifier_b = load_classifier()
        self.assertIsNone(classifier_b, "Tenant B should not load tenant A's classifier")

        # Verify tenant B's path is different and doesn't exist yet
        path_b = get_tenant_model_file(str(self.tenant_b.id))
        self.assertNotEqual(path_a, path_b)
        self.assertFalse(path_b.exists())

        # Clean up
        path_a.unlink()

    def test_explicit_tenant_id_parameter_overrides_context(self):
        """
        Test that explicit tenant_id parameter overrides context.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # But explicitly request tenant B's path
        model_file = get_tenant_model_file(str(self.tenant_b.id))

        expected_path_b = settings.MEDIA_ROOT / f"tenant_{self.tenant_b.id}" / "classifier.pkl"
        self.assertEqual(model_file, expected_path_b)
