import pickle
import warnings
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from documents.classifier import ClassifierModelCorruptError
from documents.classifier import DocumentClassifier
from documents.classifier import IncompatibleClassifierVersionError
from documents.classifier import _predict_with_threshold
from documents.classifier import _text_analyzer
from documents.classifier import load_classifier
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.helpers import dummy_preprocess
from paperless.settings import CLASSIFIER_LANGUAGES
from paperless.signed_pickle import HMAC_SIZE
from paperless.signed_pickle import signed_pickle_dumps
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import TagFactory


class TestClassifier(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.classifier = DocumentClassifier()
        self.classifier.preprocess_content = mock.MagicMock(
            side_effect=dummy_preprocess,
        )

    def generate_test_data(self) -> None:
        self.c1 = Correspondent.objects.create(
            name="c1",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        self.c2 = Correspondent.objects.create(name="c2")
        self.c3 = Correspondent.objects.create(
            name="c3",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )

        self.t1 = Tag.objects.create(
            name="t1",
            matching_algorithm=Tag.MATCH_AUTO,
            pk=12,
        )
        self.t2 = Tag.objects.create(
            name="t2",
            matching_algorithm=Tag.MATCH_ANY,
            pk=34,
            is_inbox_tag=True,
        )
        self.t3 = Tag.objects.create(
            name="t3",
            matching_algorithm=Tag.MATCH_AUTO,
            pk=45,
        )
        self.t4 = Tag.objects.create(
            name="t4",
            matching_algorithm=Tag.MATCH_ANY,
            pk=46,
        )

        self.dt = DocumentType.objects.create(
            name="dt",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        self.dt2 = DocumentType.objects.create(
            name="dt2",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )

        self.sp1 = StoragePath.objects.create(
            name="sp1",
            path="path1",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        self.sp2 = StoragePath.objects.create(
            name="sp2",
            path="path2",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        self.store_paths = [self.sp1, self.sp2]

        self.doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            correspondent=self.c1,
            checksum="A",
            document_type=self.dt,
            storage_path=self.sp1,
        )

        self.doc2 = Document.objects.create(
            title="doc1",
            content="this is another document, but from c2",
            correspondent=self.c2,
            checksum="B",
        )

        self.doc_inbox = Document.objects.create(
            title="doc235",
            content="aa",
            checksum="C",
        )

        self.doc1.tags.add(self.t1)
        self.doc2.tags.add(self.t1)
        self.doc2.tags.add(self.t3)
        self.doc_inbox.tags.add(self.t2)

    def generate_train_and_save(self) -> None:
        """
        Generates the training data, trains and saves the updated pickle
        file. This ensures the test is using the same scikit learn version
        and eliminates a warning from the test suite
        """
        self.generate_test_data()
        self.classifier.train()
        self.classifier.save()

    def test_no_training_data(self) -> None:
        """
        GIVEN:
            - No documents exist to train
        WHEN:
            - Classifier training is requested
        THEN:
            - Exception is raised
        """
        with self.assertRaisesMessage(ValueError, "No training data available."):
            self.classifier.train()

    def test_no_non_inbox_tags(self) -> None:
        """
        GIVEN:
            - No documents without an inbox tag exist
        WHEN:
            - Classifier training is requested
        THEN:
            - Exception is raised
        """

        t1 = Tag.objects.create(
            name="t1",
            matching_algorithm=Tag.MATCH_ANY,
            pk=34,
            is_inbox_tag=True,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )
        doc1.tags.add(t1)

        with self.assertRaisesMessage(ValueError, "No training data available."):
            self.classifier.train()

    def testEmpty(self) -> None:
        """
        GIVEN:
            - A document exists
            - No tags/not enough data to predict
        WHEN:
            - Classifier prediction is requested
        THEN:
            - Classifier returns no predictions
        """
        Document.objects.create(title="WOW", checksum="3457", content="ASD")
        self.classifier.train()

        self.assertIsNone(self.classifier.document_type_classifier)
        self.assertIsNone(self.classifier.tags_classifier)
        self.assertIsNone(self.classifier.correspondent_classifier)

        self.assertListEqual(self.classifier.predict_tags(""), [])
        self.assertIsNone(self.classifier.predict_document_type(""))
        self.assertIsNone(self.classifier.predict_correspondent(""))

    def testTrain(self) -> None:
        """
        GIVEN:
            - Test data
        WHEN:
            - Classifier is trained
        THEN:
            - Classifier uses correct values for correspondent learning
            - Classifier uses correct values for tags learning
        """
        self.generate_test_data()
        self.classifier.train()

        self.assertListEqual(
            list(self.classifier.correspondent_classifier.classes_),
            [-1, self.c1.pk],
        )
        self.assertListEqual(
            list(self.classifier.tags_binarizer.classes_),
            [self.t1.pk, self.t3.pk],
        )

    def testPredict(self) -> None:
        """
        GIVEN:
            - Classifier trained against test data
        WHEN:
            - Prediction requested for correspondent, tags, type
        THEN:
            - Expected predictions based on training set
        """
        self.generate_test_data()
        self.classifier.train()

        with (
            mock.patch.object(
                self.classifier.data_vectorizer,
                "transform",
                wraps=self.classifier.data_vectorizer.transform,
            ) as mock_transform,
            mock.patch.object(
                self.classifier,
                "preprocess_content",
                wraps=self.classifier.preprocess_content,
            ) as mock_preprocess_content,
        ):
            self.assertEqual(
                self.classifier.predict_correspondent(self.doc1.content),
                self.c1.pk,
            )
            self.assertEqual(
                self.classifier.predict_correspondent(self.doc2.content),
                None,
            )
            self.assertListEqual(
                self.classifier.predict_tags(self.doc1.content),
                [self.t1.pk],
            )
            self.assertListEqual(
                self.classifier.predict_tags(self.doc2.content),
                [self.t1.pk, self.t3.pk],
            )
            self.assertEqual(
                self.classifier.predict_document_type(self.doc1.content),
                self.dt.pk,
            )
            self.assertEqual(
                self.classifier.predict_document_type(self.doc2.content),
                None,
            )

            # Check that the classifier vectorized content and text preprocessing has been cached
            # It should be called once per document (doc1 and doc2)
            self.assertEqual(mock_preprocess_content.call_count, 2)
            self.assertEqual(mock_transform.call_count, 2)

    def test_vectorize_recomputes_tampered_cache_entry(self) -> None:
        cached = bytearray(signed_pickle_dumps(["cached vector"]))
        cached[HMAC_SIZE] ^= 0xFF
        self.classifier.data_vectorizer = mock.Mock()
        self.classifier.data_vectorizer.transform.return_value = ["fresh vector"]

        with (
            mock.patch(
                "documents.classifier.read_cache.get",
                return_value=bytes(cached),
            ),
            mock.patch("documents.classifier.read_cache.set") as cache_set,
            mock.patch("documents.classifier.read_cache.touch") as cache_touch,
        ):
            result = self.classifier._vectorize("content")

        self.assertEqual(result, ["fresh vector"])
        self.classifier.data_vectorizer.transform.assert_called_once()
        cache_set.assert_called_once()
        cache_touch.assert_not_called()

    def test_no_retrain_if_no_change(self) -> None:
        """
        GIVEN:
            - Classifier trained with current data
        WHEN:
            - Classifier training is requested again
        THEN:
            - Classifier does not redo training
        """

        self.generate_test_data()

        self.assertTrue(self.classifier.train())
        self.assertFalse(self.classifier.train())

    def test_retrain_if_change(self) -> None:
        """
        GIVEN:
            - Classifier trained with current data
        WHEN:
            - Classifier training is requested again
            - Documents have changed
        THEN:
            - Classifier does not redo training
        """

        self.generate_test_data()

        self.assertTrue(self.classifier.train())

        self.doc1.correspondent = self.c2
        self.doc1.save()

        self.assertTrue(self.classifier.train())

    def test_retrain_if_auto_match_set_changed(self) -> None:
        """
        GIVEN:
            - Classifier trained with current data
        WHEN:
            - Classifier training is requested again
            - Some new AUTO match object exists
        THEN:
            - Classifier does redo training
        """
        self.generate_test_data()
        # Add the ANY type
        self.doc1.tags.add(self.t4)

        self.assertTrue(self.classifier.train())

        # Change the matching type
        self.t4.matching_algorithm = MatchingModel.MATCH_AUTO
        self.t4.save()

        self.assertTrue(self.classifier.train())

    def testVersionIncreased(self) -> None:
        """
        GIVEN:
            - Existing classifier model saved at a version
        WHEN:
            - Attempt to load classifier file from newer version
        THEN:
            - Exception is raised
        """
        self.generate_train_and_save()

        classifier2 = DocumentClassifier()

        current_ver = DocumentClassifier.FORMAT_VERSION
        with mock.patch(
            "documents.classifier.DocumentClassifier.FORMAT_VERSION",
            current_ver + 1,
        ):
            # assure that we won't load old classifiers.
            self.assertRaises(IncompatibleClassifierVersionError, classifier2.load)

            self.classifier.save()

            # assure that we can load the classifier after saving it.
            classifier2.load()

    def testSaveClassifier(self) -> None:
        self.generate_train_and_save()

        new_classifier = DocumentClassifier()
        new_classifier.load()
        new_classifier.preprocess_content = mock.MagicMock(side_effect=dummy_preprocess)

        self.assertFalse(new_classifier.train())

    def test_load_and_classify(self) -> None:
        self.generate_train_and_save()

        new_classifier = DocumentClassifier()
        new_classifier.load()
        new_classifier.preprocess_content = mock.MagicMock(side_effect=dummy_preprocess)

        self.assertCountEqual(new_classifier.predict_tags(self.doc2.content), [45, 12])

    def test_load_corrupt_file(self) -> None:
        """
        GIVEN:
            - Corrupted classifier pickle file
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - The ClassifierModelCorruptError is raised
        """
        self.generate_train_and_save()

        # Write garbage data (valid HMAC length but invalid content)
        Path(settings.MODEL_FILE).write_bytes(b"\x00" * 64)

        with self.assertRaises(ClassifierModelCorruptError):
            self.classifier.load()

        self.assertIsNone(load_classifier())

    def test_load_corrupt_pickle_valid_hmac(self) -> None:
        """
        GIVEN:
            - A classifier file with valid HMAC but unparsable pickle data
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - The ClassifierModelCorruptError is raised
        """
        garbage_data = b"this is not valid pickle data"
        signature = DocumentClassifier._compute_hmac(garbage_data)
        Path(settings.MODEL_FILE).write_bytes(signature + garbage_data)

        with self.assertRaises(ClassifierModelCorruptError):
            self.classifier.load()

    def test_load_tampered_file(self) -> None:
        """
        GIVEN:
            - A classifier model file whose data has been modified
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - The ClassifierModelCorruptError is raised due to HMAC mismatch
        """
        self.generate_train_and_save()

        raw = Path(settings.MODEL_FILE).read_bytes()
        # Flip a byte in the data portion (after the 32-byte HMAC)
        tampered = raw[:32] + bytes([raw[32] ^ 0xFF]) + raw[33:]
        Path(settings.MODEL_FILE).write_bytes(tampered)

        with self.assertRaises(ClassifierModelCorruptError):
            self.classifier.load()

    def test_load_wrong_secret_key(self) -> None:
        """
        GIVEN:
            - A classifier model file signed with a different SECRET_KEY
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - The ClassifierModelCorruptError is raised due to HMAC mismatch
        """
        self.generate_train_and_save()

        with override_settings(SECRET_KEY="different-secret-key"):
            with self.assertRaises(ClassifierModelCorruptError):
                self.classifier.load()

    def test_load_truncated_file(self) -> None:
        """
        GIVEN:
            - A classifier model file that is too short to contain an HMAC
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - The ClassifierModelCorruptError is raised
        """
        Path(settings.MODEL_FILE).write_bytes(b"\x00" * 16)

        with self.assertRaises(ClassifierModelCorruptError):
            self.classifier.load()

    def test_load_new_scikit_learn_version(self) -> None:
        """
        GIVEN:
            - classifier pickle file triggers an InconsistentVersionWarning
        WHEN:
            - An attempt is made to load the classifier
        THEN:
            - IncompatibleClassifierVersionError is raised
        """
        from sklearn.exceptions import InconsistentVersionWarning

        self.generate_train_and_save()

        fake_warning = warnings.WarningMessage(
            message=InconsistentVersionWarning(
                estimator_name="MLPClassifier",
                current_sklearn_version="1.0",
                original_sklearn_version="0.9",
            ),
            category=InconsistentVersionWarning,
            filename="",
            lineno=0,
        )

        real_catch_warnings = warnings.catch_warnings

        class PatchedCatchWarnings(real_catch_warnings):
            def __enter__(self):
                w = super().__enter__()
                w.append(fake_warning)
                return w

        with mock.patch(
            "documents.classifier.warnings.catch_warnings",
            PatchedCatchWarnings,
        ):
            with self.assertRaises(IncompatibleClassifierVersionError):
                self.classifier.load()

    def test_one_correspondent_predict(self) -> None:
        c1 = Correspondent.objects.create(
            name="c1",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            correspondent=c1,
            checksum="A",
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_correspondent(doc1.content), c1.pk)

    def test_one_correspondent_predict_manydocs(self) -> None:
        c1 = Correspondent.objects.create(
            name="c1",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            correspondent=c1,
            checksum="A",
        )
        doc2 = Document.objects.create(
            title="doc2",
            content="this is a document from no one",
            checksum="B",
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_correspondent(doc1.content), c1.pk)
        self.assertIsNone(self.classifier.predict_correspondent(doc2.content))

    def test_one_type_predict(self) -> None:
        dt = DocumentType.objects.create(
            name="dt",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
            document_type=dt,
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_document_type(doc1.content), dt.pk)

    def test_one_type_predict_manydocs(self) -> None:
        dt = DocumentType.objects.create(
            name="dt",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
            document_type=dt,
        )

        doc2 = Document.objects.create(
            title="doc1",
            content="this is a document from c2",
            checksum="B",
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_document_type(doc1.content), dt.pk)
        self.assertIsNone(self.classifier.predict_document_type(doc2.content))

    def test_one_path_predict(self) -> None:
        sp = StoragePath.objects.create(
            name="sp",
            matching_algorithm=StoragePath.MATCH_AUTO,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
            storage_path=sp,
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_storage_path(doc1.content), sp.pk)

    def test_one_path_predict_manydocs(self) -> None:
        sp = StoragePath.objects.create(
            name="sp",
            matching_algorithm=StoragePath.MATCH_AUTO,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
            storage_path=sp,
        )

        doc2 = Document.objects.create(
            title="doc1",
            content="this is a document from c2",
            checksum="B",
        )

        self.classifier.train()
        self.assertEqual(self.classifier.predict_storage_path(doc1.content), sp.pk)
        self.assertIsNone(self.classifier.predict_storage_path(doc2.content))

    def test_predict_rejects_prediction_below_match_threshold(self) -> None:
        """
        GIVEN:
            - Classifiers trained against test data with confident predictions
        WHEN:
            - CLASSIFIER_MATCH_THRESHOLD exceeds the model's confidence
        THEN:
            - Every predict_* method discards the match in favor of no match
        """
        c1 = Correspondent.objects.create(
            name="c1",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        dt1 = DocumentType.objects.create(
            name="dt1",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        sp1 = StoragePath.objects.create(
            name="sp1",
            matching_algorithm=StoragePath.MATCH_AUTO,
        )

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            correspondent=c1,
            document_type=dt1,
            storage_path=sp1,
            checksum="A",
        )
        Document.objects.create(
            title="doc2",
            content="this is a document from no one",
            checksum="B",
        )

        self.classifier.train()

        predictors = {
            "correspondent": self.classifier.predict_correspondent,
            "document_type": self.classifier.predict_document_type,
            "storage_path": self.classifier.predict_storage_path,
        }
        # No real prediction can reach a confidence this high, so this
        # isolates the threshold check from the model's actual output.
        with override_settings(CLASSIFIER_MATCH_THRESHOLD=0.999999):
            for name, predict in predictors.items():
                with self.subTest(field=name):
                    self.assertIsNone(predict(doc1.content))

    def test_train_uses_balanced_sample_weight(self) -> None:
        """
        GIVEN:
            - A training set with correspondents, document types and storage paths
        WHEN:
            - The classifier is trained
        THEN:
            - Each MLP classifier is fit with balanced sample weights, so that
              over-represented classes don't dominate predictions
        """
        c1 = Correspondent.objects.create(
            name="c1",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        dt1 = DocumentType.objects.create(
            name="dt1",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        sp1 = StoragePath.objects.create(
            name="sp1",
            matching_algorithm=StoragePath.MATCH_AUTO,
        )

        Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            correspondent=c1,
            document_type=dt1,
            storage_path=sp1,
            checksum="A",
        )
        Document.objects.create(
            title="doc2",
            content="this is a document from no one",
            checksum="B",
        )

        with mock.patch(
            "sklearn.utils.class_weight.compute_sample_weight",
            return_value=None,
        ) as mocked_compute_sample_weight:
            self.classifier.train()

        self.assertEqual(mocked_compute_sample_weight.call_count, 3)
        for call in mocked_compute_sample_weight.call_args_list:
            self.assertEqual(call.args[0], "balanced")

    def test_one_tag_predict(self) -> None:
        t1 = Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )

        doc1.tags.add(t1)
        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc1.content), [t1.pk])

    def test_one_tag_predict_unassigned(self) -> None:
        Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )

        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc1.content), [])

    def test_two_tags_predict_singledoc(self) -> None:
        t1 = Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)
        t2 = Tag.objects.create(name="t2", matching_algorithm=Tag.MATCH_AUTO, pk=121)

        doc4 = Document.objects.create(
            title="doc1",
            content="this is a document from c4",
            checksum="D",
        )

        doc4.tags.add(t1)
        doc4.tags.add(t2)
        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc4.content), [t1.pk, t2.pk])

    def test_two_tags_predict(self) -> None:
        t1 = Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)
        t2 = Tag.objects.create(name="t2", matching_algorithm=Tag.MATCH_AUTO, pk=121)

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )
        doc2 = Document.objects.create(
            title="doc1",
            content="this is a document from c2",
            checksum="B",
        )
        doc3 = Document.objects.create(
            title="doc1",
            content="this is a document from c3",
            checksum="C",
        )
        doc4 = Document.objects.create(
            title="doc1",
            content="this is a document from c4",
            checksum="D",
        )

        doc1.tags.add(t1)
        doc2.tags.add(t2)

        doc4.tags.add(t1)
        doc4.tags.add(t2)
        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc1.content), [t1.pk])
        self.assertListEqual(self.classifier.predict_tags(doc2.content), [t2.pk])
        self.assertListEqual(self.classifier.predict_tags(doc3.content), [])
        self.assertListEqual(self.classifier.predict_tags(doc4.content), [t1.pk, t2.pk])

    def test_one_tag_predict_multi(self) -> None:
        t1 = Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )
        doc2 = Document.objects.create(
            title="doc2",
            content="this is a document from c2",
            checksum="B",
        )

        doc1.tags.add(t1)
        doc2.tags.add(t1)
        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc1.content), [t1.pk])
        self.assertListEqual(self.classifier.predict_tags(doc2.content), [t1.pk])

    def test_one_tag_predict_multi_2(self) -> None:
        t1 = Tag.objects.create(name="t1", matching_algorithm=Tag.MATCH_AUTO, pk=12)

        doc1 = Document.objects.create(
            title="doc1",
            content="this is a document from c1",
            checksum="A",
        )
        doc2 = Document.objects.create(
            title="doc2",
            content="this is a document from c2",
            checksum="B",
        )

        doc1.tags.add(t1)
        self.classifier.train()
        self.assertListEqual(self.classifier.predict_tags(doc1.content), [t1.pk])
        self.assertListEqual(self.classifier.predict_tags(doc2.content), [])

    def test_load_classifier_not_exists(self) -> None:
        self.assertFalse(Path(settings.MODEL_FILE).exists())
        self.assertIsNone(load_classifier())

    @mock.patch("documents.classifier.DocumentClassifier.load")
    def test_load_classifier(self, load) -> None:
        Path(settings.MODEL_FILE).touch()
        self.assertIsNotNone(load_classifier())
        load.assert_called_once()

    @override_settings(
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        },
    )
    @override_settings(
        MODEL_FILE=str(Path(__file__).parent / "data" / "model.pickle"),
    )
    @pytest.mark.skip(
        reason="Disabled caching due to high memory usage - need to investigate.",
    )
    def test_load_classifier_cached(self) -> None:
        classifier = load_classifier()
        self.assertIsNotNone(classifier)

        with mock.patch("documents.classifier.DocumentClassifier.load") as load:
            load_classifier()
            load.assert_not_called()

    @mock.patch("documents.classifier.DocumentClassifier.load")
    def test_load_classifier_incompatible_version(self, load) -> None:
        Path(settings.MODEL_FILE).touch()
        self.assertTrue(Path(settings.MODEL_FILE).exists())

        load.side_effect = IncompatibleClassifierVersionError("Dummy Error")
        self.assertIsNone(load_classifier())
        self.assertFalse(Path(settings.MODEL_FILE).exists())

    @mock.patch("documents.classifier.DocumentClassifier.load")
    def test_load_classifier_os_error(self, load) -> None:
        Path(settings.MODEL_FILE).touch()
        self.assertTrue(Path(settings.MODEL_FILE).exists())

        load.side_effect = OSError()
        self.assertIsNone(load_classifier())
        self.assertTrue(Path(settings.MODEL_FILE).exists())

    @mock.patch("documents.classifier.DocumentClassifier.load")
    def test_load_classifier_raise_exception(self, mock_load) -> None:
        Path(settings.MODEL_FILE).touch()
        mock_load.side_effect = IncompatibleClassifierVersionError("Dummy Error")
        with self.assertRaises(IncompatibleClassifierVersionError):
            load_classifier(raise_exception=True)

        Path(settings.MODEL_FILE).touch()
        mock_load.side_effect = ClassifierModelCorruptError()
        with self.assertRaises(ClassifierModelCorruptError):
            load_classifier(raise_exception=True)

        Path(settings.MODEL_FILE).touch()
        mock_load.side_effect = OSError()
        with self.assertRaises(OSError):
            load_classifier(raise_exception=True)

        Path(settings.MODEL_FILE).touch()
        mock_load.side_effect = Exception()
        with self.assertRaises(Exception):
            load_classifier(raise_exception=True)


class TestClassifierSave:
    @pytest.fixture
    def model_file(self, tmp_path: Path, settings: Settings) -> Path:
        settings.MODEL_FILE = tmp_path / "classifier.pickle"
        return settings.MODEL_FILE

    @pytest.fixture
    def classifier(self) -> DocumentClassifier:
        classifier = DocumentClassifier()
        classifier.last_doc_change_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        classifier.last_auto_type_hash = b"\x01" * 32
        return classifier

    def test_save_writes_signed_pickle(
        self,
        model_file: Path,
        classifier: DocumentClassifier,
    ) -> None:
        """
        GIVEN:
            - A classifier with training state
        WHEN:
            - The classifier is saved
        THEN:
            - The file is the HMAC of the pickled state followed by that pickle
            - The pickle uses the highest protocol
            - The saved state loads back into a new classifier
            - No temporary file is left behind
        """
        classifier.save()

        raw = model_file.read_bytes()
        signature = raw[: DocumentClassifier.HMAC_SIZE]
        data = raw[DocumentClassifier.HMAC_SIZE :]
        assert signature == DocumentClassifier._compute_hmac(data)
        # A pickle opens with the PROTO opcode followed by the protocol number
        assert data[:2] == bytes([pickle.PROTO[0], pickle.HIGHEST_PROTOCOL])
        assert pickle.loads(data)[:3] == (
            DocumentClassifier.FORMAT_VERSION,
            classifier.last_doc_change_time,
            classifier.last_auto_type_hash,
        )

        loaded = DocumentClassifier()
        loaded.load()
        assert loaded.last_doc_change_time == classifier.last_doc_change_time
        assert loaded.last_auto_type_hash == classifier.last_auto_type_hash

        assert not model_file.with_name(f"{model_file.name}.part").exists()

    def test_save_failure_removes_partial_file(
        self,
        model_file: Path,
        classifier: DocumentClassifier,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An existing classifier model file
        WHEN:
            - Saving a new classifier fails part way through writing
        THEN:
            - The error is raised
            - The partially written temporary file is removed
            - The existing model file is left untouched
        """
        model_file.write_bytes(b"existing model")
        mocker.patch(
            "documents.classifier.pickle.dump",
            side_effect=RuntimeError("disk full"),
        )

        with pytest.raises(RuntimeError, match="disk full"):
            classifier.save()

        assert not model_file.with_name(f"{model_file.name}.part").exists()
        assert model_file.read_bytes() == b"existing model"


class _StubProbaClassifier:
    """
    A fake scikit-learn classifier exposing just enough of the API for
    `_predict_with_threshold`: `classes_` and `predict_proba`.
    """

    def __init__(self, classes: list[int], probabilities: list[float]) -> None:
        self.classes_ = np.array(classes)
        self._probabilities = np.array([probabilities])

    def predict_proba(self, X) -> np.ndarray:
        return self._probabilities


@pytest.mark.parametrize(
    ("classes", "probabilities", "threshold", "expected"),
    [
        # confident prediction above the threshold is returned
        ([-1, 3], [0.1, 0.9], 0.6, 3),
        # prediction below the threshold is discarded
        ([-1, 3], [0.45, 0.55], 0.6, None),
        # boundary: exactly at the threshold is accepted, not discarded
        ([-1, 3], [0.4, 0.6], 0.6, 3),
        # the winning class is the "no match" pseudo-class, regardless of its
        # own confidence
        ([-1, 3], [0.99, 0.01], 0.0, None),
        # threshold of 0.0 disables the confidence check entirely
        ([-1, 3], [0.45, 0.55], 0.0, 3),
    ],
)
def test_predict_with_threshold(classes, probabilities, threshold, expected) -> None:
    classifier = _StubProbaClassifier(classes, probabilities)
    result = _predict_with_threshold(classifier, X=None, threshold=threshold)
    assert result == expected


def test_classifier_match_threshold_default() -> None:
    """
    GIVEN:
        - No PAPERLESS_CLASSIFIER_MATCH_THRESHOLD environment variable is set
    THEN:
        - The classifier match threshold defaults to 0.3
    """
    assert settings.CLASSIFIER_MATCH_THRESHOLD == 0.3


class TestPreprocessContent:
    @pytest.fixture
    def samples(self) -> Path:
        return Path(__file__).parent / "samples"

    @pytest.fixture
    def content(self, samples: Path) -> str:
        return (samples / "content.txt").read_text()

    def test_supported_language(
        self,
        settings: Settings,
        samples: Path,
        content: str,
    ) -> None:
        """
        GIVEN:
            - The classifier language is English, the default
        WHEN:
            - Document content is preprocessed
        THEN:
            - Stop words are removed and the remaining words are stemmed
        """
        settings.CLASSIFIER_LANGUAGE = "english"
        expected = (samples / "preprocessed_content_advanced.txt").read_text()

        assert DocumentClassifier().preprocess_content(content) == expected.rstrip()

    def test_unsupported_language(
        self,
        settings: Settings,
        samples: Path,
        content: str,
    ) -> None:
        """
        GIVEN:
            - No classifier language (the OCR language has no stemming support)
        WHEN:
            - Document content is preprocessed
        THEN:
            - The content is only lowercased and split into words
        """
        settings.CLASSIFIER_LANGUAGE = None
        expected = (samples / "preprocessed_content.txt").read_text()

        assert DocumentClassifier().preprocess_content(content) == expected.rstrip()

    @pytest.mark.parametrize(
        "language",
        [pytest.param("english", id="supported"), pytest.param(None, id="unsupported")],
    )
    def test_empty_content(self, settings: Settings, language: str | None) -> None:
        """
        GIVEN:
            - Empty document content
        WHEN:
            - The content is preprocessed
        THEN:
            - The result is empty
        """
        settings.CLASSIFIER_LANGUAGE = language

        assert DocumentClassifier().preprocess_content("") == ""


@pytest.mark.django_db
class TestClassifierTrainTagLabels:
    @pytest.fixture(autouse=True)
    def _simple_preprocess(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            DocumentClassifier,
            "preprocess_content",
            side_effect=dummy_preprocess,
        )

    @pytest.fixture
    def auto_tags(self) -> list[Tag]:
        return TagFactory.create_batch(2, matching_algorithm=MatchingModel.MATCH_AUTO)

    def test_train_query_count_does_not_scale_with_documents(
        self,
        auto_tags: list[Tag],
    ) -> None:
        """
        GIVEN:
            - Documents with auto matching tags
        WHEN:
            - The classifier is trained, then more documents are added and it is
              trained again
        THEN:
            - Both trainings run the same number of queries
        """
        for doc in DocumentFactory.create_batch(2):
            doc.tags.set(auto_tags)

        with CaptureQueriesContext(connection) as few_documents:
            DocumentClassifier().train()

        for doc in DocumentFactory.create_batch(6):
            doc.tags.set(auto_tags)

        with CaptureQueriesContext(connection) as more_documents:
            DocumentClassifier().train()

        assert len(more_documents) == len(few_documents)

    def test_train_uses_only_auto_tags_as_labels(
        self,
        auto_tags: list[Tag],
    ) -> None:
        """
        GIVEN:
            - Documents with both auto matching and non auto matching tags
        WHEN:
            - The classifier is trained
        THEN:
            - Only the auto matching tags are used as tag labels
        """
        manual_tag = TagFactory(matching_algorithm=MatchingModel.MATCH_ANY)
        first, second, third = DocumentFactory.create_batch(3)
        first.tags.set([auto_tags[0], manual_tag])
        second.tags.set([auto_tags[1], manual_tag])
        third.tags.set([*auto_tags, manual_tag])

        classifier = DocumentClassifier()
        classifier.train()

        assert list(classifier.tags_binarizer.classes_) == sorted(
            tag.pk for tag in auto_tags
        )


@pytest.mark.django_db
class TestClassifierTrainContent:
    def test_train_content_follows_label_order_across_chunks(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - More documents than fit in one content chunk
        WHEN:
            - The classifier is trained
        THEN:
            - Every document's content is preprocessed once, in document order
        """
        mocker.patch("documents.classifier._CONTENT_CHUNK_SIZE", 2)
        docs = DocumentFactory.create_batch(5)
        preprocess = mocker.patch.object(
            DocumentClassifier,
            "preprocess_content",
            side_effect=dummy_preprocess,
        )

        DocumentClassifier().train()

        assert [call.args[0] for call in preprocess.call_args_list] == [
            doc.content for doc in sorted(docs, key=lambda doc: doc.pk)
        ]

    def test_train_document_deleted_while_training(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Two documents
        WHEN:
            - The second document is deleted after its labels were gathered, but
              before its content is fetched
        THEN:
            - Training completes
            - The deleted document is trained with empty content, keeping labels
              and content aligned
        """
        mocker.patch("documents.classifier._CONTENT_CHUNK_SIZE", 1)
        first, second = DocumentFactory.create_batch(2)

        def delete_second_then_preprocess(content: str, **kwargs) -> str:
            if content == first.content:
                second.delete()
            return dummy_preprocess(content)

        preprocess = mocker.patch.object(
            DocumentClassifier,
            "preprocess_content",
            side_effect=delete_second_then_preprocess,
        )

        assert DocumentClassifier().train()

        assert [call.args[0] for call in preprocess.call_args_list] == [
            first.content,
            "",
        ]


class TestTextAnalyzer:
    @pytest.mark.parametrize(
        "language",
        [
            pytest.param(language, id=language)
            for language in sorted(set(CLASSIFIER_LANGUAGES.values()))
        ],
    )
    def test_builds_for_every_classifier_language(self, language: str) -> None:
        """
        GIVEN:
            - A language the classifier supports
        WHEN:
            - Text is analyzed with its classifier language
        THEN:
            - Tokens are produced
        """
        assert _text_analyzer(language).analyze("Paperless invoice 2026")

    def test_english_removes_snowball_stop_words(self) -> None:
        """
        GIVEN:
            - English text with a contraction and stop words missing from
              Tantivy's own English list
        WHEN:
            - The text is analyzed
        THEN:
            - All stop words are removed, including the contraction
            - The remaining words are stemmed
        """
        tokens = _text_analyzer("english").analyze(
            "They were about to pay the invoices, don't worry",
        )

        assert tokens == ["pay", "invoic", "worri"]

    def test_keeps_underscores_within_tokens(self) -> None:
        """
        GIVEN:
            - Text with a word joined by an underscore
        WHEN:
            - The text is analyzed
        THEN:
            - The word stays one token
        """
        tokens = _text_analyzer("english").analyze("tax_id")

        assert tokens == ["tax_id"]
