from collections.abc import Iterable

import pytest
from factory.django import DjangoModelFactory

from documents import matching
from documents.models import Document
from documents.models import MatchingModel
from documents.signals import document_consumption_finished
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import DocumentTypeFactory
from documents.tests.factories import TagFactory


@pytest.fixture(
    params=[TagFactory, CorrespondentFactory, DocumentTypeFactory],
    ids=["tag", "correspondent", "document_type"],
)
def matchable_factory(request: pytest.FixtureRequest) -> type[DjangoModelFactory]:
    """
    Parametrized fixture yielding each factory whose model participates in
    content matching: ``TagFactory``, ``CorrespondentFactory``, and
    ``DocumentTypeFactory``.

    Tests that consume this fixture run once per factory, so a single test
    body verifies the matching behavior across all three ``MatchingModel``
    subclasses. The parametrize IDs (``tag`` / ``correspondent`` /
    ``document_type``) appear in test names so a failure points directly at
    the offending model.
    """
    return request.param


@pytest.fixture()
def doc_with_keyword() -> Document:
    return DocumentFactory.create(
        content="I contain the keyword.",
        mime_type="application/pdf",
    )


def _assert_matches(
    factory_cls: type[DjangoModelFactory],
    match_text: str,
    match_algorithm: int,
    should_match: Iterable[str],
    no_match: Iterable[str],
    *,
    case_sensitive: bool = False,
) -> None:
    """
    Build one matchable instance from ``factory_cls`` configured with the
    given ``match_text``, ``match_algorithm``, and case sensitivity, then
    assert that ``matching.matches`` returns ``True`` for every string in
    ``should_match`` and ``False`` for every string in ``no_match``.

    Both the matchable and each candidate ``Document`` are constructed
    unsaved: ``matching.matches`` only reads ``match`` / ``matching_algorithm``
    / ``is_insensitive`` off the matchable, and an unsaved ``Document``
    short-circuits ``get_effective_content`` via the ``pk is None`` branch.
    Skipping the DB keeps the parametrized matrix cheap. ``case_sensitive``
    is inverted into ``is_insensitive`` to match the model field. Assertion
    failures include the pattern and the offending string so a parametrized
    failure is self-describing.
    """
    instance = factory_cls.build(
        match=match_text,
        matching_algorithm=match_algorithm,
        is_insensitive=not case_sensitive,
    )
    for content in should_match:
        doc = Document(content=content)
        assert matching.matches(instance, doc), (
            f'"{match_text}" should match "{content}" but it does not'
        )
    for content in no_match:
        doc = Document(content=content)
        assert not matching.matches(instance, doc), (
            f'"{match_text}" should not match "{content}" but it does'
        )


class TestMatching:
    @pytest.mark.django_db
    def test_root_uses_latest_version_content(self) -> None:
        root = DocumentFactory.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root content without token",
        )
        DocumentFactory.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="latest version contains keyword",
        )
        tag = TagFactory.create(
            match="keyword",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        assert matching.matches(tag, root)

    @pytest.mark.django_db
    def test_root_does_not_fall_back_when_version_exists(self) -> None:
        root = DocumentFactory.create(
            title="root",
            checksum="root",
            mime_type="application/pdf",
            content="root contains keyword",
        )
        DocumentFactory.create(
            title="v1",
            checksum="v1",
            mime_type="application/pdf",
            root_document=root,
            content="latest version without token",
        )
        tag = TagFactory.create(
            match="keyword",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        assert not matching.matches(tag, root)

    def test_match_none(
        self,
        matchable_factory: type[DjangoModelFactory],
    ) -> None:
        _assert_matches(
            matchable_factory,
            "",
            MatchingModel.MATCH_NONE,
            (),
            ("no", "match"),
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                ("I have alpha, charlie, and gamma in me",),
                (
                    "I have alpha in me",
                    "I have charlie in me",
                    "I have gamma in me",
                    "I have alpha and charlie in me",
                    "I have alphas, charlie, and gamma in me",
                    "I have alphas in me",
                    "I have bravo in me",
                ),
                id="words",
            ),
            pytest.param(
                "12 34 56",
                ("I have 12 34, and 56 in me",),
                (
                    "I have 12 in me",
                    "I have 34 in me",
                    "I have 56 in me",
                    "I have 12 and 34 in me",
                    "I have 120, 34, and 56 in me",
                    "I have 123456 in me",
                    "I have 01234567 in me",
                ),
                id="numbers",
            ),
            pytest.param(
                'brown fox "lazy dogs"',
                (
                    "the quick brown fox jumped over the lazy dogs",
                    "the quick brown fox jumped over the lazy  dogs",
                ),
                (
                    "the quick fox jumped over the lazy dogs",
                    "the quick brown wolf jumped over the lazy dogs",
                    "the quick brown fox jumped over the fat dogs",
                    "the quick brown fox jumped over the lazy... dogs",
                ),
                id="quoted-phrase",
            ),
        ],
    )
    def test_match_all(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_ALL,
            should_match,
            no_match,
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                (
                    "I have alpha in me",
                    "I have charlie in me",
                    "I have gamma in me",
                    "I have alpha, charlie, and gamma in me",
                    "I have alpha and charlie in me",
                ),
                (
                    "I have alphas in me",
                    "I have bravo in me",
                ),
                id="words",
            ),
            pytest.param(
                "12 34 56",
                (
                    "I have 12 in me",
                    "I have 34 in me",
                    "I have 56 in me",
                    "I have 12 and 34 in me",
                    "I have 12, 34, and 56 in me",
                    "I have 120, 34, and 56 in me",
                ),
                (
                    "I have 123456 in me",
                    "I have 01234567 in me",
                ),
                id="numbers",
            ),
            pytest.param(
                '"brown fox" " lazy  dogs "',
                (
                    "the quick brown fox",
                    "jumped over the lazy  dogs.",
                ),
                ("the lazy fox jumped over the brown dogs",),
                id="quoted-phrases",
            ),
        ],
    )
    def test_match_any(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_ANY,
            should_match,
            no_match,
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                ("I have 'alpha charlie gamma' in me",),
                (
                    "I have alpha in me",
                    "I have charlie in me",
                    "I have gamma in me",
                    "I have alpha and charlie in me",
                    "I have alpha, charlie, and gamma in me",
                    "I have alphas, charlie, and gamma in me",
                    "I have alphas in me",
                    "I have bravo in me",
                ),
                id="words",
            ),
            pytest.param(
                "12 34 56",
                ("I have 12 34 56 in me",),
                (
                    "I have 12 in me",
                    "I have 34 in me",
                    "I have 56 in me",
                    "I have 12 and 34 in me",
                    "I have 12 34, and 56 in me",
                    "I have 120, 34, and 560 in me",
                    "I have 120, 340, and 560 in me",
                    "I have 123456 in me",
                    "I have 01234567 in me",
                ),
                id="numbers",
            ),
        ],
    )
    def test_match_literal(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_LITERAL,
            should_match,
            no_match,
        )

    def test_match_regex(
        self,
        matchable_factory: type[DjangoModelFactory],
    ) -> None:
        _assert_matches(
            matchable_factory,
            r"alpha\w+gamma",
            MatchingModel.MATCH_REGEX,
            (
                "I have alpha_and_gamma in me",
                "I have alphas_and_gamma in me",
            ),
            (
                "I have alpha in me",
                "I have gamma in me",
                "I have alpha and charlie in me",
                "I have alpha,and,gamma in me",
                "I have alpha and gamma in me",
                "I have alpha, charlie, and gamma in me",
                "I have alphas, charlie, and gamma in me",
                "I have alphas in me",
            ),
        )

    def test_invalid_regex(
        self,
        matchable_factory: type[DjangoModelFactory],
    ) -> None:
        _assert_matches(
            matchable_factory,
            "[",
            MatchingModel.MATCH_REGEX,
            (),
            ("Don't match this",),
        )

    def test_match_regex_timeout_returns_false(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        tag = TagFactory.build(
            match=r"(a+)+$",
            matching_algorithm=MatchingModel.MATCH_REGEX,
        )
        document = Document(content=("a" * 5000) + "X")

        with caplog.at_level("WARNING", logger="paperless.regex"):
            assert not matching.matches(tag, document)

        assert "timed out" in caplog.text

    def test_match_fuzzy(
        self,
        matchable_factory: type[DjangoModelFactory],
    ) -> None:
        _assert_matches(
            matchable_factory,
            "Springfield, Miss.",
            MatchingModel.MATCH_FUZZY,
            (
                "1220 Main Street, Springf eld, Miss.",
                "1220 Main Street, Spring field, Miss.",
                "1220 Main Street, Springfeld, Miss.",
                "1220 Main Street Springfield Miss",
            ),
            ("1220 Main Street, Springfield, Mich.",),
        )


class TestCaseSensitiveMatching:
    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                (
                    "I have alpha, charlie, and gamma in me",
                    "I have gamma, charlie, and alpha in me",
                ),
                (
                    "I have Alpha, charlie, and gamma in me",
                    "I have gamma, Charlie, and alpha in me",
                    "I have alpha, charlie, and Gamma in me",
                    "I have gamma, charlie, and ALPHA in me",
                ),
                id="lowercase-pattern",
            ),
            pytest.param(
                "Alpha charlie Gamma",
                (
                    "I have Alpha, charlie, and Gamma in me",
                    "I have Gamma, charlie, and Alpha in me",
                ),
                (
                    "I have Alpha, charlie, and gamma in me",
                    "I have gamma, charlie, and alpha in me",
                    "I have alpha, charlie, and Gamma in me",
                    "I have Gamma, Charlie, and ALPHA in me",
                ),
                id="mixed-case-pattern",
            ),
            pytest.param(
                'brown fox "lazy dogs"',
                (
                    "the quick brown fox jumped over the lazy dogs",
                    "the quick brown fox jumped over the lazy  dogs",
                ),
                (
                    "the quick Brown fox jumped over the lazy dogs",
                    "the quick brown Fox jumped over the lazy  dogs",
                    "the quick brown fox jumped over the Lazy dogs",
                    "the quick brown fox jumped over the lazy  Dogs",
                ),
                id="quoted-phrase",
            ),
        ],
    )
    def test_match_all(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_ALL,
            should_match,
            no_match,
            case_sensitive=True,
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                (
                    "I have alpha in me",
                    "I have charlie in me",
                    "I have gamma in me",
                    "I have alpha, charlie, and gamma in me",
                    "I have alpha and charlie in me",
                ),
                (
                    "I have Alpha in me",
                    "I have chaRLie in me",
                    "I have gamMA in me",
                    "I have aLPha, cHArlie, and gAMma in me",
                    "I have AlphA and CharlIe in me",
                ),
                id="lowercase-pattern",
            ),
            pytest.param(
                "Alpha Charlie Gamma",
                (
                    "I have Alpha in me",
                    "I have Charlie in me",
                    "I have Gamma in me",
                    "I have Alpha, Charlie, and Gamma in me",
                    "I have Alpha and Charlie in me",
                ),
                (
                    "I have alpha in me",
                    "I have ChaRLie in me",
                    "I have GamMA in me",
                    "I have ALPha, CHArlie, and GAMma in me",
                    "I have AlphA and CharlIe in me",
                ),
                id="capitalized-pattern",
            ),
            pytest.param(
                '"brown fox" " lazy  dogs "',
                (
                    "the quick brown fox",
                    "jumped over the lazy  dogs.",
                ),
                (
                    "the quick Brown fox",
                    "jumped over the lazy  Dogs.",
                ),
                id="quoted-phrases",
            ),
        ],
    )
    def test_match_any(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_ANY,
            should_match,
            no_match,
            case_sensitive=True,
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                "alpha charlie gamma",
                ("I have 'alpha charlie gamma' in me",),
                (
                    "I have 'Alpha charlie gamma' in me",
                    "I have 'alpha Charlie gamma' in me",
                    "I have 'alpha charlie Gamma' in me",
                    "I have 'Alpha Charlie Gamma' in me",
                ),
                id="lowercase-pattern",
            ),
            pytest.param(
                "Alpha Charlie Gamma",
                ("I have 'Alpha Charlie Gamma' in me",),
                (
                    "I have 'Alpha charlie gamma' in me",
                    "I have 'alpha Charlie gamma' in me",
                    "I have 'alpha charlie Gamma' in me",
                    "I have 'alpha charlie gamma' in me",
                ),
                id="capitalized-pattern",
            ),
        ],
    )
    def test_match_literal(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_LITERAL,
            should_match,
            no_match,
            case_sensitive=True,
        )

    @pytest.mark.parametrize(
        ("match_text", "should_match", "no_match"),
        [
            pytest.param(
                r"alpha\w+gamma",
                (
                    "I have alpha_and_gamma in me",
                    "I have alphas_and_gamma in me",
                ),
                (
                    "I have Alpha_and_Gamma in me",
                    "I have alpHAs_and_gaMMa in me",
                ),
                id="lowercase-pattern",
            ),
            pytest.param(
                r"Alpha\w+gamma",
                (
                    "I have Alpha_and_gamma in me",
                    "I have Alphas_and_gamma in me",
                ),
                (
                    "I have Alpha_and_Gamma in me",
                    "I have alphas_and_gamma in me",
                ),
                id="capitalized-pattern",
            ),
        ],
    )
    def test_match_regex(
        self,
        matchable_factory: type[DjangoModelFactory],
        match_text: str,
        should_match: tuple[str, ...],
        no_match: tuple[str, ...],
    ) -> None:
        _assert_matches(
            matchable_factory,
            match_text,
            MatchingModel.MATCH_REGEX,
            should_match,
            no_match,
            case_sensitive=True,
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
class TestDocumentConsumptionFinishedSignal:
    """
    document_consumption_finished should drive tag & correspondent matching.
    """

    def test_tag_applied_any(self, doc_with_keyword: Document) -> None:
        tag = TagFactory.create(
            match="keyword",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc_with_keyword,
        )

        assert list(doc_with_keyword.tags.all()) == [tag]

    def test_tag_not_applied(self, doc_with_keyword: Document) -> None:
        TagFactory.create(
            match="no-match",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc_with_keyword,
        )

        assert list(doc_with_keyword.tags.all()) == []

    def test_correspondent_applied(self, doc_with_keyword: Document) -> None:
        correspondent = CorrespondentFactory.create(
            match="keyword",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc_with_keyword,
        )

        assert doc_with_keyword.correspondent == correspondent

    def test_correspondent_not_applied(self, doc_with_keyword: Document) -> None:
        CorrespondentFactory.create(
            match="no-match",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )

        document_consumption_finished.send(
            sender=self.__class__,
            document=doc_with_keyword,
        )

        assert doc_with_keyword.correspondent is None
