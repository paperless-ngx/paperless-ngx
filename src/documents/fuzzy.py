"""Native fuzzy scoring boundary; never fall back to Python scoring."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

INSTALL_HINT = (
    "Install Rust 1.89.0 (rustup), then run `uv sync --frozen` from the "
    "repository root. If already installed, rebuild with "
    "`uv sync --frozen --reinstall-package paperless-fuzzy-native`. "
    "See docs/fuzzy_matching.md."
)


class NativeFuzzyError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def native_backend() -> ModuleType:
    try:
        import paperless_fuzzy_native

        if paperless_fuzzy_native.API_VERSION != 1:
            raise ImportError("incompatible native fuzzy API")
        if not callable(paperless_fuzzy_native.process_and_ratio):
            raise ImportError("missing native scoring function")
    except (ImportError, OSError, AttributeError) as error:
        raise NativeFuzzyError(
            f"Rust fuzzy matching is unavailable: {error}. {INSTALL_HINT}",
        ) from error
    return paperless_fuzzy_native


def process_and_ratio(first: str, second: str, score_cutoff: float) -> float:
    backend = native_backend()
    try:
        return backend.process_and_ratio(first, second, score_cutoff)
    except Exception as error:
        raise NativeFuzzyError(f"Rust fuzzy matching failed: {error}") from error
