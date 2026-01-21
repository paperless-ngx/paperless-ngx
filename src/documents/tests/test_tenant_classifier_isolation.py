"""
Security tests for tenant-isolated classifier models.

This test suite verifies that classifier models are properly isolated
between tenants to prevent data leakage.
"""

import uuid
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from documents.classifier import DocumentClassifier
from documents.classifier import get_tenant_model_file
from documents.classifier import load_classifier
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import Tag
from documents.models import Tenant
from documents.tests.utils import DirectoriesMixin
from paperless.middleware import set_current_tenant


class TestTenantClassifierIsolation(DirectoriesMixin, TestCase):
    """
    Test suite to verify tenant isolation for classifier models.

    These tests ensure:
    1. Each tenant has isolated MODEL_FILE path
    2. DocumentClassifier.save() uses tenant-specific path
    3. load_classifier() loads tenant-specific model
    4. Tenant A's classifier doesn't access tenant B's training data
    """

    def setUp(self):
        """Set up test environment with two tenants."""
        super().setUp()

        # Create two tenants for isolation testing
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            subdomain="tenant-a",
            region="us",
        )
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            subdomain="tenant-b",
            region="us",
        )

        # Ensure media directories exist
        self.media_root = self.dirs.scratch_dir / "media"
        self.media_root.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        set_current_tenant(None)
        super().tearDown()

    def test_tenant_specific_model_file_paths(self):
        """
        Acceptance Criteria 1: Each tenant has isolated MODEL_FILE path.

        Verifies that each tenant gets a unique path in the format:
        MEDIA_ROOT/tenant_{id}/classifier.pkl
        """
        with override_settings(MEDIA_ROOT=self.media_root):
            # Get model file path for tenant A
            tenant_a_path = get_tenant_model_file(str(self.tenant_a.id))
            expected_a_path = self.media_root / f"tenant_{self.tenant_a.id}" / "classifier.pkl"

            self.assertEqual(tenant_a_path, expected_a_path)

            # Get model file path for tenant B
            tenant_b_path = get_tenant_model_file(str(self.tenant_b.id))
            expected_b_path = self.media_root / f"tenant_{self.tenant_b.id}" / "classifier.pkl"

            self.assertEqual(tenant_b_path, expected_b_path)

            # Ensure paths are different
            self.assertNotEqual(tenant_a_path, tenant_b_path)

            # Verify directories are created
            self.assertTrue(tenant_a_path.parent.exists())
            self.assertTrue(tenant_b_path.parent.exists())

    def test_tenant_specific_model_file_from_context(self):
        """Test that get_tenant_model_file uses current tenant from context."""
        with override_settings(MEDIA_ROOT=self.media_root):
            # Set tenant A in context
            set_current_tenant(self.tenant_a)

            tenant_a_path_from_context = get_tenant_model_file()
            expected_a_path = self.media_root / f"tenant_{self.tenant_a.id}" / "classifier.pkl"

            self.assertEqual(tenant_a_path_from_context, expected_a_path)

            # Set tenant B in context
            set_current_tenant(self.tenant_b)

            tenant_b_path_from_context = get_tenant_model_file()
            expected_b_path = self.media_root / f"tenant_{self.tenant_b.id}" / "classifier.pkl"

            self.assertEqual(tenant_b_path_from_context, expected_b_path)

    def test_fallback_to_shared_model_file(self):
        """Test that get_tenant_model_file falls back to shared file when no tenant."""
        with override_settings(
            MEDIA_ROOT=self.media_root,
            MODEL_FILE=self.media_root / "shared_classifier.pkl",
        ):
            # No tenant in context
            set_current_tenant(None)

            shared_path = get_tenant_model_file()

            self.assertEqual(shared_path, settings.MODEL_FILE)

    def test_classifier_save_uses_tenant_specific_path(self):
        """
        Acceptance Criteria 2: DocumentClassifier.save() uses tenant-specific path.

        Verifies that saving a classifier model stores it in the tenant's
        isolated directory.
        """
        with override_settings(MEDIA_ROOT=self.media_root):
            # Create a simple classifier
            classifier = DocumentClassifier()
            classifier.last_doc_change_time = None
            classifier.last_auto_type_hash = None

            # Save for tenant A
            classifier.save(tenant_id=str(self.tenant_a.id))

            expected_a_path = self.media_root / f"tenant_{self.tenant_a.id}" / "classifier.pkl"
            self.assertTrue(expected_a_path.exists())

            # Save for tenant B
            classifier.save(tenant_id=str(self.tenant_b.id))

            expected_b_path = self.media_root / f"tenant_{self.tenant_b.id}" / "classifier.pkl"
            self.assertTrue(expected_b_path.exists())

            # Ensure both files exist independently
            self.assertTrue(expected_a_path.exists())
            self.assertTrue(expected_b_path.exists())

    def test_classifier_load_uses_tenant_specific_path(self):
        """
        Acceptance Criteria 3: load_classifier() loads tenant-specific model.

        Verifies that loading a classifier retrieves the correct tenant's model.
        """
        with override_settings(MEDIA_ROOT=self.media_root):
            # Create and save a classifier for tenant A
            classifier_a = DocumentClassifier()
            classifier_a.last_doc_change_time = None
            classifier_a.last_auto_type_hash = b"tenant_a_hash"
            classifier_a.save(tenant_id=str(self.tenant_a.id))

            # Create and save a different classifier for tenant B
            classifier_b = DocumentClassifier()
            classifier_b.last_doc_change_time = None
            classifier_b.last_auto_type_hash = b"tenant_b_hash"
            classifier_b.save(tenant_id=str(self.tenant_b.id))

            # Load tenant A's classifier
            loaded_a = load_classifier(tenant_id=str(self.tenant_a.id))
            self.assertIsNotNone(loaded_a)
            self.assertEqual(loaded_a.last_auto_type_hash, b"tenant_a_hash")

            # Load tenant B's classifier
            loaded_b = load_classifier(tenant_id=str(self.tenant_b.id))
            self.assertIsNotNone(loaded_b)
            self.assertEqual(loaded_b.last_auto_type_hash, b"tenant_b_hash")

    def test_classifier_isolation_prevents_cross_tenant_access(self):
        """
        Acceptance Criteria 5: Security test - Verify tenant A's classifier
        doesn't access tenant B's training data.

        This test ensures complete isolation by:
        1. Creating different training data for each tenant
        2. Training separate classifiers
        3. Verifying predictions are isolated
        """
        with override_settings(MEDIA_ROOT=self.media_root):
            # Create training data for tenant A
            set_current_tenant(self.tenant_a)

            correspondent_a = Correspondent.objects.create(
                name="Correspondent A",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_a.id,
            )

            doc_type_a = DocumentType.objects.create(
                name="Type A",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_a.id,
            )

            tag_a = Tag.objects.create(
                name="Tag A",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_a.id,
            )

            doc_a = Document.objects.create(
                title="Document from Tenant A",
                content="This is confidential data from tenant A with unique keywords alpha beta",
                correspondent=correspondent_a,
                document_type=doc_type_a,
                checksum="CHECKSUM_A",
                tenant_id=self.tenant_a.id,
            )
            doc_a.tags.add(tag_a)

            # Create training data for tenant B
            set_current_tenant(self.tenant_b)

            correspondent_b = Correspondent.objects.create(
                name="Correspondent B",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_b.id,
            )

            doc_type_b = DocumentType.objects.create(
                name="Type B",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_b.id,
            )

            tag_b = Tag.objects.create(
                name="Tag B",
                matching_algorithm=MatchingModel.MATCH_AUTO,
                tenant_id=self.tenant_b.id,
            )

            doc_b = Document.objects.create(
                title="Document from Tenant B",
                content="This is confidential data from tenant B with unique keywords gamma delta",
                correspondent=correspondent_b,
                document_type=doc_type_b,
                checksum="CHECKSUM_B",
                tenant_id=self.tenant_b.id,
            )
            doc_b.tags.add(tag_b)

            # Train classifier for tenant A
            set_current_tenant(self.tenant_a)
            classifier_a = DocumentClassifier()

            # Mock preprocess_content to avoid NLTK dependencies in tests
            with mock.patch.object(classifier_a, 'preprocess_content', side_effect=lambda x, **kwargs: x.lower()):
                trained_a = classifier_a.train()
                self.assertTrue(trained_a)
                classifier_a.save(tenant_id=str(self.tenant_a.id))

            # Train classifier for tenant B
            set_current_tenant(self.tenant_b)
            classifier_b = DocumentClassifier()

            with mock.patch.object(classifier_b, 'preprocess_content', side_effect=lambda x, **kwargs: x.lower()):
                trained_b = classifier_b.train()
                self.assertTrue(trained_b)
                classifier_b.save(tenant_id=str(self.tenant_b.id))

            # Verify isolation: Load tenant A's classifier and ensure it doesn't
            # have tenant B's data
            set_current_tenant(self.tenant_a)
            loaded_classifier_a = load_classifier(tenant_id=str(self.tenant_a.id))
            self.assertIsNotNone(loaded_classifier_a)

            # The classifier for tenant A should only know about tenant A's correspondents
            # Check that correspondent_b.pk is not in the classifier's training
            if loaded_classifier_a.correspondent_classifier:
                # The classes_ attribute contains all possible labels the classifier was trained on
                trained_classes = loaded_classifier_a.correspondent_classifier.classes_
                self.assertIn(correspondent_a.pk, trained_classes)
                self.assertNotIn(correspondent_b.pk, trained_classes)

            # Verify isolation: Load tenant B's classifier
            set_current_tenant(self.tenant_b)
            loaded_classifier_b = load_classifier(tenant_id=str(self.tenant_b.id))
            self.assertIsNotNone(loaded_classifier_b)

            # The classifier for tenant B should only know about tenant B's correspondents
            if loaded_classifier_b.correspondent_classifier:
                trained_classes = loaded_classifier_b.correspondent_classifier.classes_
                self.assertIn(correspondent_b.pk, trained_classes)
                self.assertNotIn(correspondent_a.pk, trained_classes)

    def test_classifier_model_files_are_physically_separate(self):
        """
        Security test: Verify that model files are stored in completely
        separate directories to prevent any potential file-level leakage.
        """
        with override_settings(MEDIA_ROOT=self.media_root):
            # Save classifiers for both tenants
            classifier_a = DocumentClassifier()
            classifier_a.last_doc_change_time = None
            classifier_a.last_auto_type_hash = b"hash_a"
            classifier_a.save(tenant_id=str(self.tenant_a.id))

            classifier_b = DocumentClassifier()
            classifier_b.last_doc_change_time = None
            classifier_b.last_auto_type_hash = b"hash_b"
            classifier_b.save(tenant_id=str(self.tenant_b.id))

            # Get file paths
            path_a = get_tenant_model_file(str(self.tenant_a.id))
            path_b = get_tenant_model_file(str(self.tenant_b.id))

            # Verify files exist
            self.assertTrue(path_a.exists())
            self.assertTrue(path_b.exists())

            # Verify they're in different directories
            self.assertNotEqual(path_a.parent, path_b.parent)

            # Verify directory names include tenant ID
            self.assertIn(str(self.tenant_a.id), str(path_a))
            self.assertIn(str(self.tenant_b.id), str(path_b))

            # Verify tenant A's directory doesn't contain tenant B's files
            tenant_a_files = list(path_a.parent.iterdir())
            tenant_b_files = list(path_b.parent.iterdir())

            # Check no overlap
            self.assertEqual(len(set(tenant_a_files) & set(tenant_b_files)), 0)

    def test_nonexistent_tenant_returns_none(self):
        """Test that loading classifier for nonexistent tenant returns None."""
        with override_settings(MEDIA_ROOT=self.media_root):
            fake_tenant_id = str(uuid.uuid4())

            classifier = load_classifier(tenant_id=fake_tenant_id)

            self.assertIsNone(classifier)

    def test_migration_preserves_data_integrity(self):
        """
        Acceptance Criteria 4: Migration script to move existing shared model
        to per-tenant locations.

        This test simulates the migration scenario.
        """
        with override_settings(
            MEDIA_ROOT=self.media_root,
            MODEL_FILE=self.media_root / "shared_classifier.pkl",
        ):
            # Create a "shared" classifier (pre-migration state)
            shared_classifier = DocumentClassifier()
            shared_classifier.last_doc_change_time = None
            shared_classifier.last_auto_type_hash = b"shared_model"

            # Save to the old shared location
            settings.MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
            with settings.MODEL_FILE.open("wb") as f:
                import pickle
                pickle.dump(DocumentClassifier.FORMAT_VERSION, f)
                pickle.dump(shared_classifier.last_doc_change_time, f)
                pickle.dump(shared_classifier.last_auto_type_hash, f)
                pickle.dump(None, f)  # data_vectorizer
                pickle.dump(None, f)  # tags_binarizer
                pickle.dump(None, f)  # tags_classifier
                pickle.dump(None, f)  # correspondent_classifier
                pickle.dump(None, f)  # document_type_classifier
                pickle.dump(None, f)  # storage_path_classifier

            self.assertTrue(settings.MODEL_FILE.exists())

            # Simulate migration: copy to tenant-specific locations
            import shutil
            for tenant in [self.tenant_a, self.tenant_b]:
                tenant_path = get_tenant_model_file(str(tenant.id))
                shutil.copy2(settings.MODEL_FILE, tenant_path)

            # Verify both tenants can load the migrated model
            classifier_a = load_classifier(tenant_id=str(self.tenant_a.id))
            self.assertIsNotNone(classifier_a)
            self.assertEqual(classifier_a.last_auto_type_hash, b"shared_model")

            classifier_b = load_classifier(tenant_id=str(self.tenant_b.id))
            self.assertIsNotNone(classifier_b)
            self.assertEqual(classifier_b.last_auto_type_hash, b"shared_model")
