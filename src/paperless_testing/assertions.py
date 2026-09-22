"""Filesystem assertions for unittest-style tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from os import PathLike


class FileSystemAssertsMixin:
    def assertIsFile(self, path: PathLike[str] | str) -> None:
        if not Path(path).resolve().is_file():
            raise AssertionError(f"File does not exist: {path}")

    def assertIsNotFile(self, path: PathLike[str] | str) -> None:
        if Path(path).resolve().is_file():
            raise AssertionError(f"File does exist: {path}")

    def assertIsDir(self, path: PathLike[str] | str) -> None:
        if not Path(path).resolve().is_dir():
            raise AssertionError(f"Dir does not exist: {path}")

    def assertIsNotDir(self, path: PathLike[str] | str) -> None:
        if Path(path).resolve().is_dir():
            raise AssertionError(f"Dir does exist: {path}")

    def assertFileCountInDir(self, path: PathLike[str] | str, count: int) -> None:
        path = Path(path).resolve()
        if not path.is_dir():
            raise AssertionError(f"Path {path} is not a directory")
        found = len([x for x in path.iterdir() if x.is_file()])
        if found != count:
            raise AssertionError(
                f"Path {path} contains {found} files instead of {count} files",
            )
