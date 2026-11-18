from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING
from typing import TypeVar

import regex
from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("paperless.regex")

T = TypeVar("T")

REGEX_TIMEOUT_SECONDS: float = getattr(settings, "MATCH_REGEX_TIMEOUT_SECONDS", 0.1)


def validate_regex_pattern(pattern: str) -> None:
    """
    Validate user provided regex for basic compile errors.
    Raises ValueError on validation failure.
    """

    try:
        regex.compile(pattern)
    except regex.error as exc:
        raise ValueError(exc.msg) from exc


def _shorten(pattern: str) -> str:
    return textwrap.shorten(pattern, width=80, placeholder="…")


def _compile_or_none(
    pattern: str,
    flags: int,
    *,
    log: Callable[..., None],
) -> regex.Pattern | None:
    """Validate and compile a pattern, logging and returning None on failure."""
    try:
        validate_regex_pattern(pattern)
        return regex.compile(pattern, flags=flags)
    except (regex.error, ValueError) as exc:
        log(
            "Error while processing regular expression %s: %s",
            _shorten(pattern),
            exc,
        )
        return None


def _run_with_timeout(
    pattern: str,
    operation: str,
    func: Callable[..., T],
    *args: object,
) -> T | None:
    """Call a compiled pattern method with the timeout, logging a timeout."""
    try:
        return func(*args, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "Regular expression %s timed out for pattern %s",
            operation,
            _shorten(pattern),
        )
        return None


def safe_regex_search(pattern: str, text: str, *, flags: int = 0):
    """
    Run a regex search with a timeout. Returns a match object or None.
    Validation errors and timeouts are logged and treated as no match.
    """
    compiled = _compile_or_none(pattern, flags, log=logger.error)
    if compiled is None:
        return None
    return _run_with_timeout(pattern, "matching", compiled.search, text)


def safe_regex_match(pattern: str, text: str, *, flags: int = 0):
    """
    Run a regex match with a timeout. Returns a match object or None.
    Validation errors and timeouts are logged and treated as no match.
    """
    compiled = _compile_or_none(pattern, flags, log=logger.exception)
    if compiled is None:
        return None
    return _run_with_timeout(pattern, "matching", compiled.match, text)


def safe_regex_fullmatch(pattern: str, text: str, *, flags: int = 0):
    """
    Run a regex full match with a timeout. Returns a match object or None.
    Validation errors and timeouts are logged and treated as no match.
    """
    compiled = _compile_or_none(pattern, flags, log=logger.exception)
    if compiled is None:
        return None
    return _run_with_timeout(pattern, "matching", compiled.fullmatch, text)


def safe_regex_sub(pattern: str, repl: str, text: str, *, flags: int = 0) -> str | None:
    """
    Run a regex substitution with a timeout. Returns the substituted string,
    or None on error/timeout.
    """
    compiled = _compile_or_none(pattern, flags, log=logger.exception)
    if compiled is None:
        return None
    return _run_with_timeout(pattern, "substitution", compiled.sub, repl, text)


def safe_regex_finditer(compiled_pattern: regex.Pattern, text: str):
    """
    Run regex finditer with a timeout. Yields match objects.
    Stops iteration on timeout.
    """

    try:
        yield from compiled_pattern.finditer(text, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "Regular expression finditer timed out for pattern %s",
            _shorten(compiled_pattern.pattern),
        )
        return
