"""Property-based tests for path containment security (PBT-03).

Target: documents.file_handling.validate_path_in_root
Scope: K01 Property-Based Testing
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from documents.file_handling import UnsafeFilePathError
from documents.file_handling import validate_path_in_root

if TYPE_CHECKING:
    from pathlib import Path

_SAFE_COMPONENT_STRATEGY = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="._-",
    ),
    min_size=1,
    max_size=25,
).filter(lambda x: x not in {".", ".."})


class TestPathSecurity:
    """Hypothesis properties covering path containment invariants."""

    @given(st.lists(_SAFE_COMPONENT_STRATEGY, min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_descendants_inside_root_accepted(
        self,
        tmp_path: Path,
        parts: list[str],
    ) -> None:
        """Invariant 1: Any path resolving inside root is accepted."""
        root = tmp_path / "storage_root"
        root.mkdir(parents=True, exist_ok=True)

        target = root.joinpath(*parts)
        validate_path_in_root(target, root)

    @given(st.integers(min_value=1, max_value=8))
    @settings(max_examples=100, deadline=None)
    def test_traversal_outside_root_rejected(
        self,
        tmp_path: Path,
        depth: int,
    ) -> None:
        """Invariant 2: Path traversal escaping root raises UnsafeFilePathError."""
        root = tmp_path / "sub" / "storage_root"
        root.mkdir(parents=True, exist_ok=True)

        traversal_parts = [".."] * (depth + 2) + ["escaped.pdf"]
        target = root.joinpath(*traversal_parts)

        with pytest.raises(UnsafeFilePathError):
            validate_path_in_root(target, root)

    @given(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_symlink_escaping_root_rejected(
        self,
        tmp_path: Path,
        name_suffix: str,
    ) -> None:
        """Invariant 3: Symlink resolving outside root raises UnsafeFilePathError."""
        root = tmp_path / f"root_{name_suffix}"
        outside = tmp_path / f"outside_{name_suffix}"
        root.mkdir(parents=True, exist_ok=True)
        outside.mkdir(parents=True, exist_ok=True)

        secret_file = outside / "secret.pdf"
        secret_file.touch()

        symlink_in_root = root / "link_to_outside.pdf"
        try:
            symlink_in_root.symlink_to(secret_file)
        except (OSError, NotImplementedError):
            pytest.skip(
                "Symlink creation not permitted or supported in this environment",
            )

        with pytest.raises(UnsafeFilePathError):
            validate_path_in_root(symlink_in_root, root)

    def test_symlink_internal_to_root_accepted(self, tmp_path: Path) -> None:
        """Invariant 3b: Symlink resolving inside root is accepted."""
        root = tmp_path / "root_internal"
        root.mkdir(parents=True, exist_ok=True)

        internal_target = root / "original.pdf"
        internal_target.touch()

        internal_link = root / "link_internal.pdf"
        try:
            internal_link.symlink_to(internal_target)
        except (OSError, NotImplementedError):
            pytest.skip(
                "Symlink creation not permitted or supported in this environment",
            )

        validate_path_in_root(internal_link, root)
