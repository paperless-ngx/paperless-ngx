"""
Tests for the document_retagger management command.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import StoragePathFactory
from documents.tests.factories import TagFactory
from documents.tests.utils import DirectoriesMixin

# ---------------------------------------------------------------------------
# Module-level type aliases
# ---------------------------------------------------------------------------

StoragePathTuple = tuple[StoragePath, StoragePath, StoragePath]
TagTuple = tuple[Tag, Tag, Tag, Tag, Tag]
CorrespondentTuple = tuple[Correspondent, Correspondent]
DocumentTypeTuple = tuple[DocumentType, DocumentType]
DocumentTuple = tuple[Document, Document, Document, Document]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage_paths(db) -> StoragePathTuple:
    """Three storage paths with varying match rules."""
    sp1 = StoragePathFactory(
        path="{created_data}/{title}",
        match="auto document",
        matching_algorithm=MatchingModel.MATCH_LITERAL,
    )
    sp2 = StoragePathFactory(
        path="{title}",
        match="^first|^unrelated",
        matching_algorithm=MatchingModel.MATCH_REGEX,
    )
    sp3 = StoragePathFactory(
        path="{title}",
        match="^blah",
        matching_algorithm=MatchingModel.MATCH_REGEX,
    )
    return sp1, sp2, sp3


@pytest.fixture()
def tags(db) -> TagTuple:
    """Tags covering the common matching scenarios."""
    tag_first = TagFactory(match="first", matching_algorithm=Tag.MATCH_ANY)
    tag_second = TagFactory(match="second", matching_algorithm=Tag.MATCH_ANY)
    tag_inbox = TagFactory(is_inbox_tag=True)
    tag_no_match = TagFactory()
    tag_auto = TagFactory(matching_algorithm=Tag.MATCH_AUTO)
    return tag_first, tag_second, tag_inbox, tag_no_match, tag_auto


@pytest.fixture()
def correspondents(db) -> CorrespondentTuple:
    """Two correspondents matching 'first' and 'second' content."""
    c_first = CorrespondentFactory(
        match="first",
        matching_algorithm=MatchingModel.MATCH_ANY,
    )
    c_second = CorrespondentFactory(
        match="second",
        matching_algorithm=MatchingModel.MATCH_ANY,
    )
    return c_first, c_second


@pytest.fixture()
def document_types(db) -> DocumentTypeTuple:
    """Two document types matching 'first' and 'second' content."""
    dt_first = DocumentTypeFactory(
        match="first",
        matching_algorithm=MatchingModel.MATCH_ANY,
    )
    dt_second = DocumentTypeFactory(
        match="second",
        matching_algorithm=MatchingModel.MATCH_ANY,
    )
    return dt_first, dt_second


@pytest.fixture()
def documents(storage_paths: StoragePathTuple, tags: TagTuple) -> DocumentTuple:
    """Four documents with varied content used across most retagger tests."""
    _, _, sp3 = storage_paths
    _, _, tag_inbox, tag_no_match, tag_auto = tags

    d1 = DocumentFactory(checksum="A", title="A", content="first document")
    d2 = DocumentFactory(checksum="B", title="B", content="second document")
    d3 = DocumentFactory(
        checksum="C",
        title="C",
        content="unrelated document",
        storage_path=sp3,
    )
    d4 = DocumentFactory(checksum="D", title="D", content="auto document")

    d3.tags.add(tag_inbox, tag_no_match)
    d4.tags.add(tag_auto)

    return d1, d2, d3, d4


def _get_docs() -> DocumentTuple:
    return (
        Document.objects.get(title="A"),
        Document.objects.get(title="B"),
        Document.objects.get(title="C"),
        Document.objects.get(title="D"),
    )


# ---------------------------------------------------------------------------
# Tag assignment
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerTags(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    def test_add_tags(self, tags: TagTuple) -> None:
        tag_first, tag_second, *_ = tags
        call_command("document_retagger", "--tags")
        d_first, d_second, d_unrelated, d_auto = _get_docs()

        assert d_first.tags.count() == 1
        assert d_second.tags.count() == 1
        assert d_unrelated.tags.count() == 2
        assert d_auto.tags.count() == 1
        assert d_first.tags.first() == tag_first
        assert d_second.tags.first() == tag_second

    def test_overwrite_removes_stale_tags_and_preserves_inbox(
        self,
        documents: DocumentTuple,
        tags: TagTuple,
    ) -> None:
        d1, *_ = documents
        tag_first, tag_second, tag_inbox, tag_no_match, _ = tags
        d1.tags.add(tag_second)

        call_command("document_retagger", "--tags", "--overwrite")

        d_first, d_second, d_unrelated, d_auto = _get_docs()

        assert Tag.objects.filter(id=tag_second.id).exists()
        assert list(d_first.tags.values_list("id", flat=True)) == [tag_first.id]
        assert list(d_second.tags.values_list("id", flat=True)) == [tag_second.id]
        assert set(d_unrelated.tags.values_list("id", flat=True)) == {
            tag_inbox.id,
            tag_no_match.id,
        }
        assert d_auto.tags.count() == 0

    @pytest.mark.usefixtures("documents")
    @pytest.mark.parametrize(
        "extra_args",
        [
            pytest.param([], id="no_base_url"),
            pytest.param(["--base-url=http://localhost"], id="with_base_url"),
        ],
    )
    def test_suggest_does_not_apply_tags(self, extra_args: list[str]) -> None:
        call_command("document_retagger", "--tags", "--suggest", *extra_args)
        d_first, d_second, _, d_auto = _get_docs()

        assert d_first.tags.count() == 0
        assert d_second.tags.count() == 0
        assert d_auto.tags.count() == 1


# ---------------------------------------------------------------------------
# Document type assignment
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerDocumentType(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    def test_add_type(self, document_types: DocumentTypeTuple) -> None:
        dt_first, dt_second = document_types
        call_command("document_retagger", "--document_type")
        d_first, d_second, _, _ = _get_docs()

        assert d_first.document_type == dt_first
        assert d_second.document_type == dt_second

    @pytest.mark.usefixtures("documents", "document_types")
    @pytest.mark.parametrize(
        "extra_args",
        [
            pytest.param([], id="no_base_url"),
            pytest.param(["--base-url=http://localhost"], id="with_base_url"),
        ],
    )
    def test_suggest_does_not_apply_document_type(self, extra_args: list[str]) -> None:
        call_command("document_retagger", "--document_type", "--suggest", *extra_args)
        d_first, d_second, _, _ = _get_docs()

        assert d_first.document_type is None
        assert d_second.document_type is None


# ---------------------------------------------------------------------------
# Correspondent assignment
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerCorrespondent(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    def test_add_correspondent(self, correspondents: CorrespondentTuple) -> None:
        c_first, c_second = correspondents
        call_command("document_retagger", "--correspondent")
        d_first, d_second, _, _ = _get_docs()

        assert d_first.correspondent == c_first
        assert d_second.correspondent == c_second

    @pytest.mark.usefixtures("documents", "correspondents")
    @pytest.mark.parametrize(
        "extra_args",
        [
            pytest.param([], id="no_base_url"),
            pytest.param(["--base-url=http://localhost"], id="with_base_url"),
        ],
    )
    def test_suggest_does_not_apply_correspondent(self, extra_args: list[str]) -> None:
        call_command("document_retagger", "--correspondent", "--suggest", *extra_args)
        d_first, d_second, _, _ = _get_docs()

        assert d_first.correspondent is None
        assert d_second.correspondent is None


# ---------------------------------------------------------------------------
# Storage path assignment
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerStoragePath(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    def test_add_storage_path(self, storage_paths: StoragePathTuple) -> None:
        """
        GIVEN documents matching various storage path rules
        WHEN document_retagger --storage_path is called
        THEN matching documents get the correct path; existing path is unchanged
        """
        sp1, sp2, sp3 = storage_paths
        call_command("document_retagger", "--storage_path")
        d_first, d_second, d_unrelated, d_auto = _get_docs()

        assert d_first.storage_path == sp2
        assert d_auto.storage_path == sp1
        assert d_second.storage_path is None
        assert d_unrelated.storage_path == sp3

    @pytest.mark.usefixtures("documents")
    def test_overwrite_storage_path(self, storage_paths: StoragePathTuple) -> None:
        """
        GIVEN a document with an existing storage path that matches a different rule
        WHEN document_retagger --storage_path --overwrite is called
        THEN the existing path is replaced by the newly matched path
        """
        sp1, sp2, _ = storage_paths
        call_command("document_retagger", "--storage_path", "--overwrite")
        d_first, d_second, d_unrelated, d_auto = _get_docs()

        assert d_first.storage_path == sp2
        assert d_auto.storage_path == sp1
        assert d_second.storage_path is None
        assert d_unrelated.storage_path == sp2


# ---------------------------------------------------------------------------
# ID range filtering
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerIdRange(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    @pytest.mark.parametrize(
        ("id_range_args", "expected_count"),
        [
            pytest.param(["1", "2"], 1, id="narrow_range_limits_scope"),
            pytest.param(["1", "9999"], 2, id="wide_range_tags_all_matches"),
        ],
    )
    def test_id_range_limits_scope(
        self,
        tags: TagTuple,
        id_range_args: list[str],
        expected_count: int,
    ) -> None:
        DocumentFactory(content="NOT the first document")
        call_command("document_retagger", "--tags", "--id-range", *id_range_args)
        tag_first, *_ = tags
        assert Document.objects.filter(tags__id=tag_first.id).count() == expected_count

    @pytest.mark.usefixtures("documents")
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(["--tags", "--id-range"], id="missing_both_values"),
            pytest.param(["--tags", "--id-range", "a", "b"], id="non_integer_values"),
        ],
    )
    def test_id_range_invalid_arguments_raise(self, args: list[str]) -> None:
        with pytest.raises((CommandError, SystemExit)):
            call_command("document_retagger", *args)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.management
@pytest.mark.django_db
class TestRetaggerEdgeCases(DirectoriesMixin):
    @pytest.mark.usefixtures("documents")
    def test_no_targets_exits_cleanly(self) -> None:
        """Calling the retagger with no classifier targets should not raise."""
        call_command("document_retagger")

    @pytest.mark.usefixtures("documents")
    def test_inbox_only_skips_non_inbox_documents(self) -> None:
        """--inbox-only must restrict processing to documents with an inbox tag."""
        call_command("document_retagger", "--tags", "--inbox-only")
        d_first, _, d_unrelated, _ = _get_docs()

        assert d_first.tags.count() == 0
        assert d_unrelated.tags.count() == 2
