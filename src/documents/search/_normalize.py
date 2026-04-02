from __future__ import annotations

import unicodedata


def ascii_fold(text: str) -> str:
    """Normalize unicode text to ASCII equivalents for search consistency."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()
