import re
import warnings
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from documents.classifier import ClassifierModelCorruptError
from documents.classifier import DocumentClassifier
from documents.classifier import IncompatibleClassifierVersionError
from documents.classifier import load_classifier
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


def dummy_preprocess(content: str, **kwargs):
    """
    Simpler, faster pre-processing for testing purposes
    """
    content = content.lower().strip()
    content = re.sub(r"\s+", " ", content)
    return content


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


def test_preprocess_content() -> None:
    """
    GIVEN:
        - Advanced text processing is enabled (default)
    WHEN:
        - Classifier preprocesses a document's content
    THEN:
        - Processed content matches the expected output (stemmed words)
    """
    with (Path(__file__).parent / "samples" / "content.txt").open("r") as f:
        content = f.read()
    with (Path(__file__).parent / "samples" / "preprocessed_content_advanced.txt").open(
        "r",
    ) as f:
        expected_preprocess_content = f.read().rstrip()
    classifier = DocumentClassifier()
    result = classifier.preprocess_content(content)
    assert result == expected_preprocess_content


def test_preprocess_content_nltk_disabled() -> None:
    """
    GIVEN:
        - Advanced text processing is disabled
    WHEN:
        - Classifier preprocesses a document's content
    THEN:
        - Processed content matches the expected output (unstemmed words)
    """
    with (Path(__file__).parent / "samples" / "content.txt").open("r") as f:
        content = f.read()
    with (Path(__file__).parent / "samples" / "preprocessed_content.txt").open(
        "r",
    ) as f:
        expected_preprocess_content = f.read().rstrip()
    classifier = DocumentClassifier()
    with mock.patch("documents.classifier.ADVANCED_TEXT_PROCESSING_ENABLED", new=False):
        result = classifier.preprocess_content(content)
    assert result == expected_preprocess_content


def test_preprocess_content_nltk_load_fail(mocker) -> None:
    """
    GIVEN:
        - NLTK stop words fail to load
    WHEN:
        - Classifier preprocesses a document's content
    THEN:
        - Processed content matches the expected output (unstemmed words)
    """
    _module = mocker.MagicMock(name="nltk_corpus_mock")
    _module.stopwords.words.side_effect = AttributeError()
    mocker.patch.dict("sys.modules", {"nltk.corpus": _module})
    classifier = DocumentClassifier()
    with (Path(__file__).parent / "samples" / "content.txt").open("r") as f:
        content = f.read()
    with (Path(__file__).parent / "samples" / "preprocessed_content.txt").open(
        "r",
    ) as f:
        expected_preprocess_content = f.read().rstrip()
    result = classifier.preprocess_content(content)
    assert result == expected_preprocess_content
