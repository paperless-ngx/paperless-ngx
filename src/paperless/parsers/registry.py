"""
Singleton registry that tracks all document parsers available to
Paperless-ngx — both built-ins shipped with the application and third-party
plugins installed via Python entrypoints.

Public surface
--------------
get_parser_registry
    Lazy-initialise and return the shared ParserRegistry. This is the primary
    entry point for production code.

init_builtin_parsers
    Register built-in parsers only, without entrypoint discovery. Safe to
    call from Celery worker_process_init where importing all entrypoints
    would be wasteful or cause side effects.

reset_parser_registry
    Reset module-level state. For tests only.

Entrypoint group
----------------
Third-party parsers must advertise themselves under the
"paperless_ngx.parsers" entrypoint group in their pyproject.toml::

    [project.entry-points."paperless_ngx.parsers"]
    my_parser = "my_package.parsers:MyParser"

The loaded class must expose the following attributes at the class level
(not just on instances) for the registry to accept it:
name, version, author, url, supported_mime_types (callable), score (callable).
"""

from __future__ import annotations

import logging
import threading
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from paperless.parsers import ParserProtocol

logger = logging.getLogger("paperless.parsers.registry")

# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------

_registry: ParserRegistry | None = None
_discovery_complete: bool = False
_lock = threading.Lock()

# Attribute names that every registered external parser class must expose.
_REQUIRED_ATTRS: tuple[str, ...] = (
    "name",
    "version",
    "author",
    "url",
    "supported_mime_types",
    "score",
)


# ---------------------------------------------------------------------------
# Module-level accessor functions
# ---------------------------------------------------------------------------


def get_parser_registry() -> ParserRegistry:
    """Return the shared ParserRegistry instance.

    On the first call this function:

    1. Creates a new ParserRegistry.
    2. Calls register_defaults to install built-in parsers.
    3. Calls discover to load third-party plugins via importlib.metadata entrypoints.

    Subsequent calls return the same instance immediately.

    Returns
    -------
    ParserRegistry
        The shared registry singleton.
    """
    global _registry, _discovery_complete

    with _lock:
        if _registry is None:
            r = ParserRegistry()
            r.register_defaults()
            _registry = r

        if not _discovery_complete:
            _registry.discover()
            _discovery_complete = True

    return _registry


def init_builtin_parsers() -> None:
    """Register built-in parsers without performing entrypoint discovery.

    Intended for use in Celery worker_process_init handlers where importing
    all installed entrypoints would be wasteful, slow, or could produce
    undesirable side effects. Entrypoint discovery (third-party plugins) is
    deliberately not performed.

    Safe to call multiple times — subsequent calls are no-ops.

    Returns
    -------
    None
    """
    global _registry

    with _lock:
        if _registry is None:
            r = ParserRegistry()
            r.register_defaults()
            _registry = r


def reset_parser_registry() -> None:
    """Reset the module-level registry state to its initial values.

    Resets _registry and _discovery_complete so the next call to
    get_parser_registry will re-initialise everything from scratch.

    FOR TESTS ONLY. Do not call this in production code — resetting the
    registry mid-request causes all subsequent parser lookups to go through
    discovery again, which is expensive and may have unexpected side effects
    in multi-threaded environments.

    Returns
    -------
    None
    """
    global _registry, _discovery_complete

    _registry = None
    _discovery_complete = False


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------


class ParserRegistry:
    """Registry that maps MIME types to the best available parser class.

    Parsers are partitioned into two lists:

    _builtins
        Parser classes registered via register_builtin (populated by
        register_defaults in Phase 3+).

    _external
        Parser classes loaded from installed Python entrypoints via discover.

    When resolving a parser for a file, external parsers are evaluated
    alongside built-in parsers using a uniform scoring mechanism. Both lists
    are iterated together; the class with the highest score wins. If an
    external parser wins, its attribution details are logged so users can
    identify which third-party package handled their document.
    """

    def __init__(self) -> None:
        self._external: list[type[ParserProtocol]] = []
        self._builtins: list[type[ParserProtocol]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_builtin(self, parser_class: type[ParserProtocol]) -> None:
        """Register a built-in parser class.

        Built-in parsers are shipped with Paperless-ngx and are appended to
        the _builtins list. They are never overridden by external parsers;
        instead, scoring determines which parser wins for any given file.

        Parameters
        ----------
        parser_class:
            The parser class to register. Must satisfy ParserProtocol.
        """
        self._builtins.append(parser_class)

    def register_defaults(self) -> None:
        """Register the built-in parsers that ship with Paperless-ngx.

        Each parser that has been migrated to the new ParserProtocol interface
        is registered here.  Parsers are added in ascending weight order so
        that log output is predictable; scoring determines which parser wins
        at runtime regardless of registration order.
        """
        from paperless.parsers.mail import MailDocumentParser
        from paperless.parsers.remote import RemoteDocumentParser
        from paperless.parsers.tesseract import RasterisedDocumentParser
        from paperless.parsers.text import TextDocumentParser
        from paperless.parsers.tika import TikaDocumentParser

        self.register_builtin(TextDocumentParser)
        self.register_builtin(RemoteDocumentParser)
        self.register_builtin(TikaDocumentParser)
        self.register_builtin(MailDocumentParser)
        self.register_builtin(RasterisedDocumentParser)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> None:
        """Load third-party parsers from the "paperless_ngx.parsers" entrypoint group.

        For each advertised entrypoint the method:

        1. Calls ep.load() to import the class.
        2. Validates that the class exposes all required attributes.
        3. On success, appends the class to _external and logs an info message.
        4. On failure (import error or missing attributes), logs an appropriate
           warning/error and continues to the next entrypoint.

        Errors during discovery of a single parser do not prevent other parsers
        from being loaded.

        Returns
        -------
        None
        """
        eps = entry_points(group="paperless_ngx.parsers")

        for ep in eps:
            try:
                parser_class = ep.load()
            except Exception:
                logger.exception(
                    "Failed to load parser entrypoint '%s' — skipping.",
                    ep.name,
                )
                continue

            missing = [
                attr for attr in _REQUIRED_ATTRS if not hasattr(parser_class, attr)
            ]
            if missing:
                logger.warning(
                    "Parser loaded from entrypoint '%s' is missing required "
                    "attributes %r — skipping.",
                    ep.name,
                    missing,
                )
                continue

            self._external.append(parser_class)
            logger.info(
                "Loaded third-party parser '%s' v%s by %s (entrypoint: '%s').",
                parser_class.name,
                parser_class.version,
                parser_class.author,
                ep.name,
            )

    # ------------------------------------------------------------------
    # Summary logging
    # ------------------------------------------------------------------

    def log_summary(self) -> None:
        """Log a startup summary of all registered parsers.

        Built-in parsers are listed first, followed by any external parsers
        discovered from entrypoints.  If no external parsers were found a
        short informational message is logged instead of an empty list.

        Returns
        -------
        None
        """
        logger.info(
            "Built-in parsers (%d):",
            len(self._builtins),
        )
        for cls in self._builtins:
            logger.info(
                "  [built-in] %s v%s — %s",
                getattr(cls, "name", repr(cls)),
                getattr(cls, "version", "unknown"),
                getattr(cls, "url", "built-in"),
            )

        if not self._external:
            logger.info("No third-party parsers discovered.")
            return

        logger.info(
            "Third-party parsers (%d):",
            len(self._external),
        )
        for cls in self._external:
            logger.info(
                "  [external] %s v%s by %s — report issues at %s",
                getattr(cls, "name", repr(cls)),
                getattr(cls, "version", "unknown"),
                getattr(cls, "author", "unknown"),
                getattr(cls, "url", "unknown"),
            )

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def all_parsers(self) -> list[type[ParserProtocol]]:
        """Return all registered parser classes (external first, then builtins).

        Used by compatibility wrappers that need to iterate every parser to
        compute the full set of supported MIME types and file extensions.

        Returns
        -------
        list[type[ParserProtocol]]
            External parsers followed by built-in parsers.
        """
        return [*self._external, *self._builtins]

    # ------------------------------------------------------------------
    # Parser resolution
    # ------------------------------------------------------------------

    def get_parser_for_file(
        self,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> type[ParserProtocol] | None:
        """Return the best parser class for the given file, or None.

        All registered parsers (external first, then built-ins) are evaluated
        against the file. A parser is eligible if mime_type appears in the dict
        returned by its supported_mime_types classmethod, and its score
        classmethod returns a non-None integer.

        The parser with the highest score wins. When two parsers return the
        same score, the one that appears earlier in the evaluation order wins
        (external parsers are evaluated before built-ins, giving third-party
        packages a chance to override defaults at equal priority).

        When an external parser is selected, its identity is logged at INFO
        level so operators can trace which package handled a document.

        Parameters
        ----------
        mime_type:
            The detected MIME type of the file.
        filename:
            The original filename, including extension.  May be empty in some cases
        path:
            Optional filesystem path to the file. Forwarded to each
            parser's score method.

        Returns
        -------
        type[ParserProtocol] | None
            The winning parser class, or None if no parser can handle the file.
        """
        best_score: int | None = None
        best_parser: type[ParserProtocol] | None = None

        # External parsers are placed first so that, at equal scores, an
        # external parser wins over a built-in (first-seen policy).
        for parser_class in (*self._external, *self._builtins):
            if mime_type not in parser_class.supported_mime_types():
                continue

            score = parser_class.score(mime_type, filename, path)
            if score is None:
                continue

            if best_score is None or score > best_score:
                best_score = score
                best_parser = parser_class

        if best_parser is not None and best_parser in self._external:
            logger.info(
                "Document handled by third-party parser '%s' v%s — %s",
                getattr(best_parser, "name", repr(best_parser)),
                getattr(best_parser, "version", "unknown"),
                getattr(best_parser, "url", "unknown"),
            )

        return best_parser
