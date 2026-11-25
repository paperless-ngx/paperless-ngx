"""Property-based tests for path containment (PBT-03)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck
from hypothesis import example
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from documents.file_handling import UnsafeFilePathError
from documents.file_handling import validate_path_in_root

if TYPE_CHECKING:
    from pathlib import Path


settings.register_profile(
    "dev",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "recorded",
    max_examples=250,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "stress",
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
if "HYPOTHESIS_PROFILE" in os.environ:
    settings.load_profile(os.environ["HYPOTHESIS_PROFILE"])


_SAFE_COMPONENT_STRATEGY = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=20,
).map(lambda value: f"p_{value}")


class TestPathSecurity:
    @given(parts=st.lists(_SAFE_COMPONENT_STRATEGY, min_size=1, max_size=5))
    @example(parts=["p_single_file.pdf"])
    @example(parts=["p_dir", "p_subdir", "p_leaf.txt"])
    @settings(
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_descendants_inside_root_accepted(
        self,
        tmp_path: Path,
        parts: list[str],
    ) -> None:
        """PBT03-INV1: every generated descendant remains valid."""
        root = tmp_path / "storage_root"
        root.mkdir(exist_ok=True)
        target = root.joinpath(*parts)

        validate_path_in_root(target, root)

        assert target.resolve().is_relative_to(root.resolve())

    @given(
        prefix=st.lists(_SAFE_COMPONENT_STRATEGY, min_size=0, max_size=5),
        extra_depth=st.integers(min_value=1, max_value=8),
        filename=_SAFE_COMPONENT_STRATEGY,
    )
    @example(prefix=[], extra_depth=1, filename="p_passwd")
    @example(prefix=["p_sub"], extra_depth=2, filename="p_escape.txt")
    @settings(
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_traversal_outside_root_rejected(
        self,
        tmp_path: Path,
        prefix: list[str],
        extra_depth: int,
        filename: str,
    ) -> None:
        """PBT03-INV2: traversal that resolves outside root is rejected."""
        root = tmp_path / "storage_root"
        root.mkdir(exist_ok=True)
        target = root.joinpath(
            *prefix,
            *([".."] * (len(prefix) + extra_depth)),
            filename,
        )

        assert not target.resolve().is_relative_to(root.resolve())
        with pytest.raises(UnsafeFilePathError):
            validate_path_in_root(target, root)

    @given(
        sibling_suffix=_SAFE_COMPONENT_STRATEGY,
        parts=st.lists(_SAFE_COMPONENT_STRATEGY, min_size=1, max_size=4),
    )
    @example(sibling_suffix="rogue", parts=["p_secret.pdf"])
    @example(sibling_suffix="_backup", parts=["p_sub", "p_file.png"])
    @settings(
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_prefix_confusion_outside_root_rejected(
        self,
        tmp_path: Path,
        sibling_suffix: str,
        parts: list[str],
    ) -> None:
        """PBT03-INV2: a sibling sharing the root prefix is still outside."""
        root = tmp_path / "storage_root"
        root.mkdir(exist_ok=True)
        sibling = tmp_path / f"storage_root_{sibling_suffix}"
        sibling.mkdir(exist_ok=True)

        with pytest.raises(UnsafeFilePathError):
            validate_path_in_root(sibling.joinpath(*parts), root)

    @given(filename=_SAFE_COMPONENT_STRATEGY)
    @example(filename="p_sensitive_outside.txt")
    @settings(
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_symlink_escaping_root_rejected(
        self,
        tmp_path: Path,
        filename: str,
    ) -> None:
        """PBT03-INV3: resolving an in-root symlink may not escape root."""
        root = tmp_path / "storage_root"
        outside = tmp_path / "outside"
        root.mkdir(exist_ok=True)
        outside.mkdir(exist_ok=True)
        secret_file = outside / filename
        secret_file.touch()
        symlink_in_root = root / "link_to_outside"

        try:
            if symlink_in_root.is_symlink() or symlink_in_root.exists():
                symlink_in_root.unlink()
            symlink_in_root.symlink_to(secret_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are unavailable on this platform")

        with pytest.raises(UnsafeFilePathError):
            validate_path_in_root(symlink_in_root, root)

    @given(filename=_SAFE_COMPONENT_STRATEGY)
    @example(filename="p_internal_target.txt")
    @settings(
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_symlink_internal_to_root_accepted(
        self,
        tmp_path: Path,
        filename: str,
    ) -> None:
        """PBT03-INV3: resolving an in-root symlink stays valid."""
        root = tmp_path / "storage_root"
        root.mkdir(exist_ok=True)
        internal_target = root / filename
        internal_target.touch()
        internal_link = root / "link_internal"

        try:
            if internal_link.is_symlink() or internal_link.exists():
                internal_link.unlink()
            internal_link.symlink_to(internal_target)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are unavailable on this platform")

        validate_path_in_root(internal_link, root)

        assert internal_link.resolve().is_relative_to(root.resolve())
