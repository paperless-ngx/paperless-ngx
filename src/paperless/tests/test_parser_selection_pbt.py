"""Property-based tests for ParserRegistry.get_parser_for_file.

Suite: PBT-05 Parser selection
Target: paperless.parsers.registry.ParserRegistry.get_parser_for_file
Owner: Phùng Nguyễn Hoài Bo (@HubertPhung)
Reviewer: Vũ Thế Huỳnh (@1convitt)
Issue: #14, #39
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import NamedTuple

from hypothesis import HealthCheck
from hypothesis import example
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

try:
    from paperless.parsers.registry import ParserRegistry
except ImportError:
    _reg_path = Path(__file__).resolve().parents[1] / "parsers" / "registry.py"
    _spec = importlib.util.spec_from_file_location(
        "paperless.parsers.registry",
        _reg_path,
    )
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    ParserRegistry = _mod.ParserRegistry


for _profile_name, _max_examples in [
    ("dev", 50),
    ("ci", 100),
    ("default_pbt05", 200),
    ("recorded", 250),
    ("stress", 500),
]:
    settings.register_profile(
        _profile_name,
        max_examples=_max_examples,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
_pbt05_settings = settings.get_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "default_pbt05"),
)


class MockParserSpec(NamedTuple):
    name: str
    supported_mimes: tuple[str, ...]
    score_val: int | None
    is_external: bool
    uses_remote_service: bool


def create_mock_parser_class(spec: MockParserSpec) -> type:
    """Generate a lightweight mock parser class from specification."""

    class MockParser:
        name = spec.name
        version = "1.0.0"
        author = "PBT-05 Suite"
        url = "https://example.com/pbt-05"
        uses_remote_service = spec.uses_remote_service

        @classmethod
        def supported_mime_types(cls) -> dict[str, str]:
            return {m: f".{m.split('/')[-1]}" for m in spec.supported_mimes}

        @classmethod
        def score(
            cls,
            mime_type: str,
            filename: str,
            path: Path | None = None,
        ) -> int | None:
            return spec.score_val

    MockParser.__name__ = f"MockParser_{spec.name}"
    return MockParser


MIME_POOL = ["application/pdf", "image/png", "text/plain", "application/xml"]


class TestPbtParserSelection:
    """Property-based verification of ParserRegistry.get_parser_for_file."""

    @given(
        specs=st.lists(
            st.builds(
                MockParserSpec,
                name=st.text(alphabet="abcdef", min_size=1, max_size=5),
                supported_mimes=st.lists(
                    st.sampled_from(MIME_POOL),
                    min_size=1,
                    max_size=3,
                    unique=True,
                ).map(tuple),
                score_val=st.one_of(
                    st.none(),
                    st.integers(min_value=-100, max_value=100),
                ),
                is_external=st.booleans(),
                uses_remote_service=st.booleans(),
            ),
            min_size=1,
            max_size=8,
        ),
        target_mime=st.sampled_from(MIME_POOL),
        allow_remote=st.booleans(),
    )
    @example(
        specs=[
            MockParserSpec(
                "low",
                ("application/pdf",),
                10,
                is_external=False,
                uses_remote_service=False,
            ),
            MockParserSpec(
                "high",
                ("application/pdf",),
                95,
                is_external=True,
                uses_remote_service=False,
            ),
        ],
        target_mime="application/pdf",
        allow_remote=True,
    )
    @example(
        specs=[
            MockParserSpec(
                "neg_a",
                ("text/plain",),
                -100,
                is_external=False,
                uses_remote_service=False,
            ),
            MockParserSpec(
                "neg_b",
                ("text/plain",),
                -1,
                is_external=False,
                uses_remote_service=False,
            ),
        ],
        target_mime="text/plain",
        allow_remote=False,
    )
    @_pbt05_settings
    def test_highest_scoring_eligible_parser_wins(
        self,
        specs: list[MockParserSpec],
        target_mime: str,
        allow_remote: bool,  # noqa: FBT001
    ) -> None:
        """PBT05-INV1-MAX-SCORE:

        Among all eligible candidate parsers, the selected parser must be
        eligible and have the highest score.
        """
        registry = ParserRegistry()
        cls_spec_pairs: list[tuple[type, MockParserSpec]] = []

        for spec in specs:
            cls = create_mock_parser_class(spec)
            cls_spec_pairs.append((cls, spec))
            if spec.is_external:
                registry._external.append(cls)
            else:
                registry.register_builtin(cls)

        # Compute eligible candidates according to specification
        eligible = [
            (cls, spec)
            for cls, spec in cls_spec_pairs
            if target_mime in spec.supported_mimes
            and (allow_remote or not spec.uses_remote_service)
            and spec.score_val is not None
        ]

        result = registry.get_parser_for_file(
            mime_type=target_mime,
            filename="document.bin",
            allow_remote=allow_remote,
        )

        if not eligible:
            assert result is None
        else:
            assert result is not None
            max_score = max(spec.score_val for _, spec in eligible)  # type: ignore[type-var]
            # Winner must be in eligible set
            winning_spec = next(spec for cls, spec in cls_spec_pairs if cls is result)
            assert target_mime in winning_spec.supported_mimes
            if not allow_remote:
                assert not winning_spec.uses_remote_service
            assert winning_spec.score_val == max_score

    @given(
        tie_score=st.integers(min_value=-50, max_value=50),
        ext_count=st.integers(min_value=1, max_value=4),
        builtin_count=st.integers(min_value=1, max_value=4),
        target_mime=st.sampled_from(MIME_POOL),
    )
    @example(tie_score=0, ext_count=1, builtin_count=1, target_mime="application/pdf")
    @example(tie_score=50, ext_count=2, builtin_count=3, target_mime="image/png")
    @_pbt05_settings
    def test_external_parser_wins_tie_with_builtin(
        self,
        tie_score: int,
        ext_count: int,
        builtin_count: int,
        target_mime: str,
    ) -> None:
        """PBT05-INV2-TIE-BREAK-EXTERNAL:

        When an external parser and a built-in parser are tied at the highest
        score, the winning parser must always be an external parser.
        """
        registry = ParserRegistry()

        # Build external parsers tied at tie_score
        for i in range(ext_count):
            spec = MockParserSpec(
                name=f"ext_{i}",
                supported_mimes=(target_mime,),
                score_val=tie_score,
                is_external=True,
                uses_remote_service=False,
            )
            registry._external.append(create_mock_parser_class(spec))

        # Build built-in parsers tied at tie_score
        for i in range(builtin_count):
            spec = MockParserSpec(
                name=f"builtin_{i}",
                supported_mimes=(target_mime,),
                score_val=tie_score,
                is_external=False,
                uses_remote_service=False,
            )
            registry.register_builtin(create_mock_parser_class(spec))

        result = registry.get_parser_for_file(
            mime_type=target_mime,
            filename="sample.bin",
        )

        assert result is not None
        # Winner must belong to _external, never _builtins
        assert result in registry._external
        assert result not in registry._builtins
        # Winner must be the first external parser in evaluation order
        assert result is registry._external[0]

    @given(
        remote_scores=st.lists(
            st.integers(min_value=50, max_value=100),
            min_size=1,
            max_size=3,
        ),
        local_scores=st.lists(
            st.one_of(st.none(), st.integers(min_value=-20, max_value=40)),
            min_size=0,
            max_size=3,
        ),
        target_mime=st.sampled_from(MIME_POOL),
    )
    @example(
        remote_scores=[100],
        local_scores=[10],
        target_mime="application/pdf",
    )
    @example(
        remote_scores=[90, 95],
        local_scores=[None],
        target_mime="text/plain",
    )
    @_pbt05_settings
    def test_remote_parsers_excluded_when_not_allowed(
        self,
        remote_scores: list[int],
        local_scores: list[int | None],
        target_mime: str,
    ) -> None:
        """PBT05-INV3-REMOTE-EXCLUSION:

        When allow_remote=False, parsers with uses_remote_service=True must
        be excluded, even if their scores are higher than all local parsers.
        """
        registry = ParserRegistry()

        for i, score in enumerate(remote_scores):
            spec = MockParserSpec(
                name=f"remote_{i}",
                supported_mimes=(target_mime,),
                score_val=score,
                is_external=False,
                uses_remote_service=True,
            )
            registry.register_builtin(create_mock_parser_class(spec))

        local_classes: list[tuple[type, int | None]] = []
        for i, score in enumerate(local_scores):
            spec = MockParserSpec(
                name=f"local_{i}",
                supported_mimes=(target_mime,),
                score_val=score,
                is_external=False,
                uses_remote_service=False,
            )
            cls = create_mock_parser_class(spec)
            local_classes.append((cls, score))
            registry.register_builtin(cls)

        result = registry.get_parser_for_file(
            mime_type=target_mime,
            filename="confidential.bin",
            allow_remote=False,
        )

        # Winner must never be a remote parser
        if result is not None:
            assert getattr(result, "uses_remote_service", False) is False

        # If no local parser had a valid integer score, result must be None
        valid_local = [cls for cls, score in local_classes if score is not None]
        if not valid_local:
            assert result is None
        else:
            assert result is not None
            max_local_score = max(
                score for _, score in local_classes if score is not None
            )
            assert result.score(target_mime, "confidential.bin") == max_local_score

    @given(
        target_mime=st.sampled_from(MIME_POOL),
        filename=st.text(min_size=1, max_size=20),
        allow_remote=st.booleans(),
    )
    @example(target_mime="application/pdf", filename="empty.pdf", allow_remote=True)
    @_pbt05_settings
    def test_none_returned_when_registry_is_empty(
        self,
        target_mime: str,
        filename: str,
        allow_remote: bool,  # noqa: FBT001
    ) -> None:
        """PBT05-INV4A-EMPTY-REGISTRY:

        An empty parser registry must always return None for any input file.
        """
        registry = ParserRegistry()
        result = registry.get_parser_for_file(
            mime_type=target_mime,
            filename=filename,
            allow_remote=allow_remote,
        )
        assert result is None

    @given(
        specs=st.lists(
            st.builds(
                MockParserSpec,
                name=st.text(alphabet="abc", min_size=1, max_size=4),
                supported_mimes=st.just(("other/unsupported-mime",)),
                score_val=st.integers(min_value=1, max_value=100),
                is_external=st.booleans(),
                uses_remote_service=st.just(False),  # noqa: FBT003
            ),
            min_size=1,
            max_size=5,
        ),
        target_mime=st.sampled_from(MIME_POOL),
        allow_remote=st.booleans(),
    )
    @example(
        specs=[
            MockParserSpec(
                "only_other",
                ("other/unsupported-mime",),
                80,
                is_external=False,
                uses_remote_service=False,
            ),
        ],
        target_mime="application/pdf",
        allow_remote=True,
    )
    @_pbt05_settings
    def test_none_returned_when_mime_unsupported_despite_valid_scores(
        self,
        specs: list[MockParserSpec],
        target_mime: str,
        allow_remote: bool,  # noqa: FBT001
    ) -> None:
        """PBT05-INV4B-UNSUPPORTED-MIME:

        When candidate parsers have valid positive scores and local execution,
        but none support target_mime, get_parser_for_file must return None.
        """
        registry = ParserRegistry()
        for spec in specs:
            cls = create_mock_parser_class(spec)
            if spec.is_external:
                registry._external.append(cls)
            else:
                registry.register_builtin(cls)

        result = registry.get_parser_for_file(
            mime_type=target_mime,
            filename="document.bin",
            allow_remote=allow_remote,
        )
        assert result is None

    @given(
        specs=st.lists(
            st.builds(
                MockParserSpec,
                name=st.text(alphabet="def", min_size=1, max_size=4),
                supported_mimes=st.just(("application/pdf",)),
                score_val=st.none(),
                is_external=st.booleans(),
                uses_remote_service=st.just(False),  # noqa: FBT003
            ),
            min_size=1,
            max_size=5,
        ),
        allow_remote=st.booleans(),
    )
    @example(
        specs=[
            MockParserSpec(
                "decliner",
                ("application/pdf",),
                None,
                is_external=False,
                uses_remote_service=False,
            ),
        ],
        allow_remote=True,
    )
    @_pbt05_settings
    def test_none_returned_when_matching_parsers_decline_with_none_score(
        self,
        specs: list[MockParserSpec],
        allow_remote: bool,  # noqa: FBT001
    ) -> None:
        """PBT05-INV4C-DECLINING-SCORE:

        When all matching parsers support target_mime but return score None,
        get_parser_for_file must return None.
        """
        registry = ParserRegistry()
        for spec in specs:
            cls = create_mock_parser_class(spec)
            if spec.is_external:
                registry._external.append(cls)
            else:
                registry.register_builtin(cls)

        result = registry.get_parser_for_file(
            mime_type="application/pdf",
            filename="document.pdf",
            allow_remote=allow_remote,
        )
        assert result is None

    @given(
        specs=st.lists(
            st.builds(
                MockParserSpec,
                name=st.text(alphabet="ghi", min_size=1, max_size=4),
                supported_mimes=st.just(("application/pdf",)),
                score_val=st.integers(min_value=10, max_value=100),
                is_external=st.booleans(),
                uses_remote_service=st.just(True),  # noqa: FBT003
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @example(
        specs=[
            MockParserSpec(
                "cloud_ocr",
                ("application/pdf",),
                100,
                is_external=True,
                uses_remote_service=True,
            ),
        ],
    )
    @_pbt05_settings
    def test_none_returned_when_only_remote_parsers_available_and_not_allowed(
        self,
        specs: list[MockParserSpec],
    ) -> None:
        """PBT05-INV4D-BLOCKED-REMOTE-ONLY:

        When all candidate parsers match MIME and return valid scores but
        declare uses_remote_service=True and allow_remote=False,
        get_parser_for_file must return None.
        """
        registry = ParserRegistry()
        for spec in specs:
            cls = create_mock_parser_class(spec)
            if spec.is_external:
                registry._external.append(cls)
            else:
                registry.register_builtin(cls)

        result = registry.get_parser_for_file(
            mime_type="application/pdf",
            filename="document.pdf",
            allow_remote=False,
        )
        assert result is None
