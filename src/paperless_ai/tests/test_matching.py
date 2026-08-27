from collections.abc import Callable

import pytest
import pytest_mock
from django.contrib.auth.models import User
from django.test import TestCase
from factory.django import DjangoModelFactory

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import StoragePathFactory
from documents.tests.factories import TagFactory
from documents.tests.factories import UserFactory
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name
from paperless_ai.matching import resolve_correspondent_ids
from paperless_ai.matching import resolve_document_type_ids
from paperless_ai.matching import resolve_storage_path_ids
from paperless_ai.matching import resolve_tag_ids


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

    def test_match_tags_by_name(self) -> None:
        names = ["Test Tag 1", "Nonexistent Tag"]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Tag 1")

    def test_match_correspondents_by_name(self) -> None:
        names = ["Test Correspondent 1", "Nonexistent Correspondent"]
        result = match_correspondents_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Correspondent 1")

    def test_match_document_types_by_name(self) -> None:
        names = ["Test Document Type 1", "Nonexistent Document Type"]
        result = match_document_types_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Document Type 1")

    def test_match_storage_paths_by_name(self) -> None:
        names = ["Test Storage Path 1", "Nonexistent Storage Path"]
        result = match_storage_paths_by_name(names, user=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Test Storage Path 1")

    def test_extract_unmatched_names(self) -> None:
        llm_names = ["Test Tag 1", "Nonexistent Tag"]
        matched_objects = [self.tag1]
        unmatched_names = extract_unmatched_names(llm_names, matched_objects)
        self.assertEqual(unmatched_names, ["Nonexistent Tag"])

    def test_match_tags_by_name_with_empty_names(self) -> None:
        names = [None, "", "   "]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(result, [])

    def test_match_tags_with_fuzzy_matching(self) -> None:
        names = ["Test Taag 1", "Teest Tag 2"]
        result = match_tags_by_name(names, user=None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "Test Tag 1")
        self.assertEqual(result[1].name, "Test Tag 2")


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


@pytest.mark.django_db
class TestResolveTagIds:
    def test_resolves_valid_visible_id(self) -> None:
        """GIVEN a tag and a user with no restrictions
        WHEN resolving the tag's id
        THEN the tag is returned.
        """
        tag = TagFactory.create(name="Bloodwork")
        user = UserFactory.create()

        result = resolve_tag_ids([tag.pk], user)

        assert result == [tag]

    def test_drops_nonexistent_id(self) -> None:
        """GIVEN an id that does not correspond to any tag
        WHEN resolving that id
        THEN an empty list is returned.
        """
        user = UserFactory.create()

        result = resolve_tag_ids([999999], user)

        assert result == []

    def test_drops_id_not_visible_to_user(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """GIVEN a valid tag id that permitted_object_ids reports as not
            visible to the user
        WHEN resolving that id
        THEN the tag is dropped from the result.
        """
        tag = TagFactory.create(name="Restricted")
        user = UserFactory.create()
        mocker.patch(
            "documents.permissions.permitted_object_ids",
            return_value=[],
        )

        result = resolve_tag_ids([tag.pk], user)

        assert result == []

    def test_empty_input_returns_empty(self) -> None:
        """GIVEN an empty list of ids
        WHEN resolving tag ids
        THEN an empty list is returned.
        """
        user = UserFactory.create()
        assert resolve_tag_ids([], user) == []

    def test_user_none_means_unrestricted_not_owner_isnull(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """GIVEN a tag owned by another user and user=None
        WHEN resolving the tag's id
        THEN the tag is returned unfiltered and permitted_object_ids is never
            called - user=None means "no restriction", not the narrower
            "only unowned rows" meaning permitted_object_ids(None, ...) has.
            Same convention as build_taxonomy_candidates's own call site.
        """
        tag = TagFactory.create(name="Owned")
        owner = UserFactory.create()
        tag.owner = owner
        tag.save()
        spy = mocker.patch("documents.permissions.permitted_object_ids")

        result = resolve_tag_ids([tag.pk], None)

        assert result == [tag]
        spy.assert_not_called()


@pytest.mark.django_db
class TestResolveOtherTaxonomyIds:
    """The non-tag resolvers share resolve_tag_ids' implementation, so they
    only need the happy path covered here."""

    @pytest.mark.parametrize(
        ("factory", "name", "resolve"),
        [
            (CorrespondentFactory, "IRS", resolve_correspondent_ids),
            (DocumentTypeFactory, "Invoice", resolve_document_type_ids),
            (StoragePathFactory, "Financial", resolve_storage_path_ids),
        ],
    )
    def test_resolves_valid_id(
        self,
        factory: type[DjangoModelFactory],
        name: str,
        resolve: Callable[[list[int], User], list],
    ) -> None:
        """GIVEN a taxonomy object and a user with no restrictions
        WHEN resolving that object's id
        THEN the object is returned.
        """
        obj = factory.create(name=name)
        user = UserFactory.create()

        assert resolve([obj.pk], user) == [obj]
