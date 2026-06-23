from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING
from typing import Final

import regex
import tantivy
from django.conf import settings

from documents.search._dates import (
    _date_only_range,  # noqa: F401 — re-exported for test imports
)
from documents.search._dates import (
    _datetime_range,  # noqa: F401 — re-exported for test imports
)
from documents.search._tokenizer import simple_search_tokens
from documents.search._translate import SearchQueryError
from documents.search._translate import translate_query

if TYPE_CHECKING:
    from datetime import tzinfo

    from django.contrib.auth.base_user import AbstractBaseUser

logger = logging.getLogger("paperless.search")

# Maximum seconds any single regex substitution may run.
# Prevents ReDoS on adversarial user-supplied query strings.
_REGEX_TIMEOUT: Final[float] = 1.0

# Matches CJK/Hangul characters so queries can be routed to bigram fields.
# Uses Unicode properties to cover all blocks including Extension B+ planes.
_CJK_RE: Final = regex.compile(r"[\p{Han}\p{Hiragana}\p{Katakana}\p{Hangul}]+")


def _has_cjk(text: str) -> bool:
    """Return True if text contains any CJK characters."""
    return bool(_CJK_RE.search(text))


def _build_cjk_query(
    index: tantivy.Index,
    raw_query: str,
    fields: list[str],
) -> tantivy.Query | None:
    """Build a bigram-field query from the CJK runs in ``raw_query``.

    Only the CJK character runs are extracted and parsed; ASCII field prefixes,
    boolean operators and date keywords are discarded. This keeps the CJK clause
    plain-text and consistent across query/simple modes (no leaked ``field:``
    semantics, no parse failures from spaced ``-``/``+``), and avoids feeding
    Latin tokens into the character-bigram matcher (which would produce spurious
    matches against unrelated Latin text). Returns None when there is no CJK
    text or the parse fails.
    """
    cjk_text = " ".join(_CJK_RE.findall(raw_query))
    if not cjk_text:
        return None
    try:
        return index.parse_query(cjk_text, fields)
    except Exception:
        return None


def rewrite_natural_date_keywords(query: str, tz: tzinfo) -> str:
    """
    Rewrite natural date syntax to ISO 8601 format for Tantivy compatibility.

    Delegates to ``translate_query`` which handles all date forms, comma
    expansion, field aliasing, relative ranges, and operator normalization.

    Args:
        query: Raw user query string
        tz: Timezone for converting local date boundaries to UTC

    Returns:
        Query with date syntax rewritten to ISO 8601 ranges

    Note:
        Bare keywords without field prefixes pass through unchanged.
    """
    return translate_query(query, tz)


def normalize_query(query: str) -> str:
    """
    Normalize query syntax for better search behavior.

    Delegates to ``translate_query`` which handles comma expansion, whitespace
    collapsing, operator normalization, and field aliasing.

    Args:
        query: Query string after date rewriting

    Returns:
        Normalized query string ready for Tantivy parsing
    """
    return translate_query(query, UTC)


def build_permission_filter(
    schema: tantivy.Schema,
    user: AbstractBaseUser,
) -> tantivy.Query:
    """
    Build a query filter for user document permissions.

    Creates a query that matches only documents visible to the specified user
    according to paperless-ngx permission rules:
    - Public documents (no owner) are visible to all users
    - Private documents are visible to their owner
    - Documents explicitly shared with the user are visible

    Args:
        schema: Tantivy schema for field validation
        user: User to check permissions for

    Returns:
        Tantivy query that filters results to visible documents
    """
    owner_any = tantivy.Query.exists_query("owner_id")
    no_owner = tantivy.Query.boolean_query(
        [
            (tantivy.Occur.Must, tantivy.Query.all_query()),
            (tantivy.Occur.MustNot, owner_any),
        ],
    )
    owned = tantivy.Query.term_query(schema, "owner_id", user.pk)
    shared = tantivy.Query.term_query(schema, "viewer_id", user.pk)
    return tantivy.Query.disjunction_max_query([no_owner, owned, shared])


DEFAULT_SEARCH_FIELDS = [
    "title",
    "content",
    "correspondent",
    "document_type",
    "tag",
]
SIMPLE_SEARCH_FIELDS = ["simple_title", "simple_content"]
TITLE_SEARCH_FIELDS = ["simple_title"]
_CJK_ALL_FIELDS: Final[list[str]] = [
    "bigram_content",
    "bigram_title",
    "bigram_correspondent",
    "bigram_document_type",
    "bigram_tag",
]
_CJK_CONTENT_FIELDS: Final[list[str]] = ["bigram_content"]
_CJK_TITLE_FIELDS: Final[list[str]] = ["bigram_title"]
_FIELD_BOOSTS = {"title": 2.0}
_SIMPLE_FIELD_BOOSTS = {"simple_title": 2.0}


def _simple_query_tokens(raw_query: str) -> list[str]:
    # Tokenize and fold via the same analyzer used to index simple_title /
    # simple_content, so query terms fold identically to the indexed terms
    # (single source of truth for ASCII folding).
    return simple_search_tokens(raw_query)


def _build_simple_field_query(
    index: tantivy.Index,
    field: str,
    tokens: list[str],
) -> tantivy.Query:
    patterns = []
    for idx, token in enumerate(tokens):
        escaped = regex.escape(token)
        # For multi-token substring search, only the first token can begin mid-word.
        # Later tokens follow a whitespace boundary in the original query, so anchor
        # them to the start of the next indexed token to reduce false positives like
        # matching "Z-Berichte 16" for the query "Z-Berichte 6".
        if idx == 0:
            patterns.append(f".*{escaped}.*")
        else:
            patterns.append(f"{escaped}.*")
    if len(patterns) == 1:
        query = tantivy.Query.regex_query(index.schema, field, patterns[0])
    else:
        query = tantivy.Query.regex_phrase_query(index.schema, field, patterns)

    boost = _SIMPLE_FIELD_BOOSTS.get(field, 1.0)
    if boost > 1.0:
        return tantivy.Query.boost_query(query, boost)
    return query


def parse_user_query(
    index: tantivy.Index,
    raw_query: str,
    tz: tzinfo,
) -> tantivy.Query:
    """
    Parse user query through the complete preprocessing pipeline.

    Transforms the raw user query through multiple stages:
    1. Date keyword rewriting (today → ISO 8601 ranges)
    2. Query normalization (comma expansion, whitespace cleanup)
    3. Tantivy parsing with field boosts
    4. Optional fuzzy query blending (if ADVANCED_FUZZY_SEARCH_THRESHOLD set)

    Args:
        index: Tantivy index with registered tokenizers
        raw_query: Original user query string
        tz: Timezone for date boundary calculations

    Returns:
        Parsed Tantivy query ready for execution

    Note:
        When ADVANCED_FUZZY_SEARCH_THRESHOLD is configured, adds a low-priority
        fuzzy query as a Should clause (0.1 boost) to catch approximate matches
        while keeping exact matches ranked higher. The threshold value is applied
        as a post-search score filter, not during query construction.
    """

    try:
        query_str = translate_query(raw_query, tz)
    except SearchQueryError:
        # Intentional, user-fixable error (e.g. an unparsable date). Propagate so
        # the view can return a 400 with a helpful message rather than falling
        # back to the raw (still-invalid) query.
        raise
    except Exception:  # pragma: no cover - defensive
        logger.warning("Query translation failed; using raw query", exc_info=True)
        query_str = raw_query

    exact = index.parse_query(
        query_str,
        DEFAULT_SEARCH_FIELDS,
        field_boosts=_FIELD_BOOSTS,
    )

    # The standard analyzer keeps a whitespace-free CJK run as a single token,
    # so substring queries can't match content/title (and long runs are dropped
    # by remove_long). Route CJK queries to the bigram fields, whose ngram
    # tokenizer indexes overlapping 2-grams for substring matching.
    cjk_query = (
        _build_cjk_query(index, raw_query, _CJK_ALL_FIELDS)
        if _has_cjk(raw_query)
        else None
    )

    clauses: list[tuple[tantivy.Occur, tantivy.Query]] = [
        (tantivy.Occur.Should, exact),
    ]

    threshold = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD
    if threshold is not None:
        fuzzy = index.parse_query(
            query_str,
            DEFAULT_SEARCH_FIELDS,
            field_boosts=_FIELD_BOOSTS,
            # (prefix=True, distance=1, transposition_cost_one=True) — edit-distance fuzziness
            fuzzy_fields={f: (True, 1, True) for f in DEFAULT_SEARCH_FIELDS},
        )
        # 0.1 boost keeps fuzzy hits ranked below exact matches (intentional)
        clauses.append((tantivy.Occur.Should, tantivy.Query.boost_query(fuzzy, 0.1)))

    if cjk_query is not None:
        clauses.append((tantivy.Occur.Should, cjk_query))

    if len(clauses) == 1:
        return exact
    return tantivy.Query.boolean_query(clauses)


def parse_simple_query(
    index: tantivy.Index,
    raw_query: str,
    fields: list[str],
    cjk_fields: list[str] | None = None,
) -> tantivy.Query:
    """
    Parse a plain-text query using Tantivy over a restricted field set.

    Query string is escaped and normalized to be treated as "simple" text query.
    When cjk_fields is provided and the query contains CJK characters, an
    additional Should clause searches those bigram-tokenized fields, which match
    CJK substrings the simple analyzer can't (long whitespace-free runs are
    dropped by remove_long).
    """
    tokens = _simple_query_tokens(raw_query)

    clauses: list[tuple[tantivy.Occur, tantivy.Query]] = []
    if tokens:
        clauses = [
            (tantivy.Occur.Should, _build_simple_field_query(index, field, tokens))
            for field in fields
        ]

    if cjk_fields and _has_cjk(raw_query):
        cjk_q = _build_cjk_query(index, raw_query, cjk_fields)
        if cjk_q is not None:
            clauses.append((tantivy.Occur.Should, cjk_q))

    if not clauses:
        return tantivy.Query.empty_query()
    if len(clauses) == 1:
        return clauses[0][1]
    return tantivy.Query.boolean_query(clauses)


def parse_simple_text_highlight_query(
    index: tantivy.Index,
    raw_query: str,
) -> tantivy.Query:
    """Build a snippet-friendly query for simple text searches.

    Simple search matching uses regex queries but for compatibility with Tantivy
    SnippetGenerator we build a plain term query over the content field instead.
    """

    # Strip Tantivy operator chars before tokenizing: this is a plain-text
    # highlight query, not a structured boolean query, so +/- are separators.
    tokens = _simple_query_tokens(
        regex.sub(r"[-+]", " ", raw_query, timeout=_REGEX_TIMEOUT),
    )
    if not tokens:
        return tantivy.Query.empty_query()

    return index.parse_query(" ".join(tokens), ["content"])


def parse_simple_text_query(
    index: tantivy.Index,
    raw_query: str,
) -> tantivy.Query:
    """
    Parse a plain-text query over title/content for simple search inputs.
    """

    return parse_simple_query(
        index,
        raw_query,
        SIMPLE_SEARCH_FIELDS,
        cjk_fields=_CJK_CONTENT_FIELDS,
    )


def parse_simple_title_query(
    index: tantivy.Index,
    raw_query: str,
) -> tantivy.Query:
    """
    Parse a plain-text query over the title field only.
    """

    return parse_simple_query(
        index,
        raw_query,
        TITLE_SEARCH_FIELDS,
        cjk_fields=_CJK_TITLE_FIELDS,
    )
