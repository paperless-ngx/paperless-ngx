from pytest_mock import MockerFixture

from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import StoragePathFactory
from documents.tests.factories import TagFactory
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name

_PATCH_TARGET = "paperless_ai.matching.get_objects_for_user_owner_aware"


class TestAIMatching:
    def test_match_tags_by_name(self, mocker: MockerFixture) -> None:
        tags = [
            TagFactory.build(name="Test Tag 1"),
            TagFactory.build(name="Test Tag 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=tags)
        result = match_tags_by_name(["Test Tag 1", "Nonexistent Tag"], user=None)
        assert len(result) == 1
        assert result[0].name == "Test Tag 1"

    def test_match_correspondents_by_name(self, mocker: MockerFixture) -> None:
        correspondents = [
            CorrespondentFactory.build(name="Test Correspondent 1"),
            CorrespondentFactory.build(name="Test Correspondent 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=correspondents)
        result = match_correspondents_by_name(
            ["Test Correspondent 1", "Nonexistent Correspondent"],
            user=None,
        )
        assert len(result) == 1
        assert result[0].name == "Test Correspondent 1"

    def test_match_document_types_by_name(self, mocker: MockerFixture) -> None:
        document_types = [
            DocumentTypeFactory.build(name="Test Document Type 1"),
            DocumentTypeFactory.build(name="Test Document Type 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=document_types)
        result = match_document_types_by_name(
            ["Test Document Type 1", "Nonexistent Document Type"],
            user=None,
        )
        assert len(result) == 1
        assert result[0].name == "Test Document Type 1"

    def test_match_storage_paths_by_name(self, mocker: MockerFixture) -> None:
        storage_paths = [
            StoragePathFactory.build(name="Test Storage Path 1"),
            StoragePathFactory.build(name="Test Storage Path 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=storage_paths)
        result = match_storage_paths_by_name(
            ["Test Storage Path 1", "Nonexistent Storage Path"],
            user=None,
        )
        assert len(result) == 1
        assert result[0].name == "Test Storage Path 1"

    def test_extract_unmatched_names(self) -> None:
        tag = TagFactory.build(name="Test Tag 1")
        unmatched = extract_unmatched_names(["Test Tag 1", "Nonexistent Tag"], [tag])
        assert unmatched == ["Nonexistent Tag"]

    def test_match_tags_by_name_with_empty_names(self, mocker: MockerFixture) -> None:
        tags = [
            TagFactory.build(name="Test Tag 1"),
            TagFactory.build(name="Test Tag 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=tags)
        result = match_tags_by_name([None, "", "   "], user=None)
        assert result == []

    def test_match_tags_with_fuzzy_matching(self, mocker: MockerFixture) -> None:
        tags = [
            TagFactory.build(name="Test Tag 1"),
            TagFactory.build(name="Test Tag 2"),
        ]
        mocker.patch(_PATCH_TARGET, return_value=tags)
        result = match_tags_by_name(["Test Taag 1", "Teest Tag 2"], user=None)
        assert len(result) == 2
        assert result[0].name == "Test Tag 1"
        assert result[1].name == "Test Tag 2"
