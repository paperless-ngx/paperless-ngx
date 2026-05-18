from __future__ import annotations

import logging
import textwrap

import regex
from django.conf import settings

logger = logging.getLogger("paperless.regex")

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


def safe_regex_search(pattern: str, text: str, *, flags: int = 0):
    """
    Run a regex search with a timeout. Returns a match object or None.
    Validation errors and timeouts are logged and treated as no match.
    """

    try:
        validate_regex_pattern(pattern)
        compiled = regex.compile(pattern, flags=flags)
    except (regex.error, ValueError) as exc:
        logger.error(
            "Error while processing regular expression %s: %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
            exc,
        )
        return None

    try:
        return compiled.search(text, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "Regular expression matching timed out for pattern %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
        )
        return None


def safe_regex_match(pattern: str, text: str, *, flags: int = 0):
    """
    Run a regex match with a timeout. Returns a match object or None.
    Validation errors and timeouts are logged and treated as no match.
    """

    try:
        validate_regex_pattern(pattern)
        compiled = regex.compile(pattern, flags=flags)
    except (regex.error, ValueError) as exc:
        logger.error(
            "Error while processing regular expression %s: %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
            exc,
        )
        return None

    try:
        return compiled.match(text, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "Regular expression matching timed out for pattern %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
        )
        return None


def safe_regex_sub(pattern: str, repl: str, text: str, *, flags: int = 0) -> str | None:
    """
    Run a regex substitution with a timeout. Returns the substituted string,
    or None on error/timeout.
    """

    try:
        validate_regex_pattern(pattern)
        compiled = regex.compile(pattern, flags=flags)
    except (regex.error, ValueError) as exc:
        logger.error(
            "Error while processing regular expression %s: %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
            exc,
        )
        return None

    try:
        return compiled.sub(repl, text, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "Regular expression substitution timed out for pattern %s",
            textwrap.shorten(pattern, width=80, placeholder="…"),
        )
        return None


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
            textwrap.shorten(compiled_pattern.pattern, width=80, placeholder="…"),
        )
        return
