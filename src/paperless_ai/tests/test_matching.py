import difflib
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_mock
from django.test import TestCase

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name


class TestAIMatching(TestCase):
    def setUp(self) -> None:
        # Create test data for Tag
        self.tag1 = Tag.objects.create(name="Test Tag 1")
        self.tag2 = Tag.objects.create(name="Test Tag 2")

        # Create test data for Correspondent
        self.correspondent1 = Correspondent.objects.create(name="Test Correspondent 1")
        self.correspondent2 = Correspondent.objects.create(name="Test Correspondent 2")

        # Create test data for DocumentType
        self.document_type1 = DocumentType.objects.create(name="Test Document Type 1")
        self.document_type2 = DocumentType.objects.create(name="Test Document Type 2")

        # Create test data for StoragePath
        self.storage_path1 = StoragePath.objects.create(name="Test Storage Path 1")
        self.storage_path2 = StoragePath.objects.create(name="Test Storage Path 2")

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_tags_by_name(self, mock_get_objects) -> None:
        mock_get_objects.return_value = Tag.objects.all()
        names = ["Test Tag 1", "Nonexistent Tag"]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Tag 1")

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_correspondents_by_name(self, mock_get_objects) -> None:
        mock_get_objects.return_value = Correspondent.objects.all()
        names = ["Test Correspondent 1", "Nonexistent Correspondent"]
        result = match_correspondents_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Correspondent 1")

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_document_types_by_name(self, mock_get_objects) -> None:
        mock_get_objects.return_value = DocumentType.objects.all()
        names = ["Test Document Type 1", "Nonexistent Document Type"]
        result = match_document_types_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Document Type 1")

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_storage_paths_by_name(self, mock_get_objects) -> None:
        mock_get_objects.return_value = StoragePath.objects.all()
        names = ["Test Storage Path 1", "Nonexistent Storage Path"]
        result = match_storage_paths_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Storage Path 1")

    def test_extract_unmatched_names(self) -> None:
        llm_names = ["Test Tag 1", "Nonexistent Tag"]
        matched_objects = [self.tag1]
        unmatched_names = extract_unmatched_names(llm_names, matched_objects)
        self.assertEqual(unmatched_names, ["Nonexistent Tag"])

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_tags_by_name_with_empty_names(self, mock_get_objects) -> None:
        mock_get_objects.return_value = Tag.objects.all()
        names = [None, "", "   "]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(result, [])

    @patch("paperless_ai.matching.get_objects_for_user_owner_aware")
    def test_match_tags_with_fuzzy_matching(self, mock_get_objects) -> None:
        mock_get_objects.return_value = Tag.objects.all()
        names = ["Test Taag 1", "Teest Tag 2"]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "Test Tag 1")
        self.assertEqual(result[1].name, "Test Tag 2")


class TestHintedMatching:
    def test_hinted_verbatim_skips_fuzzy(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "paperless_ai.matching.get_objects_for_user_owner_aware",
            return_value=[SimpleNamespace(name="Bloodwork")],
        )
        spy = mocker.spy(difflib, "get_close_matches")

        result = match_tags_by_name(
            ["Bloodwork"],
            user=None,
            hinted_names={"Bloodwork"},
        )

        assert [t.name for t in result] == ["Bloodwork"]
        spy.assert_not_called()

    def test_unhinted_name_still_fuzzy_matches(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "paperless_ai.matching.get_objects_for_user_owner_aware",
            return_value=[SimpleNamespace(name="Bloodwork")],
        )

        # "Bloodwrok" is a typo not in hints -> fuzzy still maps it to Bloodwork.
        result = match_tags_by_name(
            ["Bloodwrok"],
            user=None,
            hinted_names={"Taxes"},
        )

        assert [t.name for t in result] == ["Bloodwork"]

    def test_hinted_name_with_whitespace_exact_matches(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "paperless_ai.matching.get_objects_for_user_owner_aware",
            return_value=[SimpleNamespace(name="Bloodwork")],
        )
        spy = mocker.spy(difflib, "get_close_matches")

        result = match_tags_by_name(
            ["Bloodwork "],
            user=None,
            hinted_names={"Bloodwork"},
        )

        assert [t.name for t in result] == ["Bloodwork"]
        spy.assert_not_called()

    def test_hinted_name_absent_from_queryset_is_skipped_not_fuzzed(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        # A hint with no exact object must not fall through to fuzzy.
        mocker.patch(
            "paperless_ai.matching.get_objects_for_user_owner_aware",
            return_value=[SimpleNamespace(name="Bloodwork")],
        )

        result = match_tags_by_name(
            ["Bloodwrok"],
            user=None,
            hinted_names={"Bloodwrok"},
        )

        assert result == []

    def test_backward_compatible_without_kwarg(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "paperless_ai.matching.get_objects_for_user_owner_aware",
            return_value=[SimpleNamespace(name="Test Tag 1")],
        )

        result = match_tags_by_name(["Test Tag 1", "Nonexistent"], user=None)

        assert [t.name for t in result] == ["Test Tag 1"]


@pytest.mark.django_db
class TestExtractUnmatchedNamesNormalization:
    def test_punctuated_name_already_matched_is_not_returned_as_unmatched(
        self,
    ) -> None:
        correspondent = Correspondent.objects.create(name="J Smith")
        llm_names = ["J. Smith"]
        matched_objects: list[Correspondent] = [correspondent]

        unmatched = extract_unmatched_names(llm_names, matched_objects)

        assert "J. Smith" not in unmatched
