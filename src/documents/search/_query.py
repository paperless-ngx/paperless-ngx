from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Final

import regex
import tantivy
from django.conf import settings

from documents.search._tokenizer import simple_search_tokens
from documents.search._translate import SearchQueryError
from documents.search._translate import translate_query

if TYPE_CHECKING:
    from collections.abc import Iterable
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


def extract_cjk_text(text: str) -> str:
    """Join the CJK runs in ``text`` for indexing into bigram (char-ngram) fields.

    Mirrors the query side (``_build_cjk_query``): only CJK runs are ever searched
    against the bigram fields, so only CJK runs are worth indexing there. Latin
    text fed to a character-bigram field is never matched and only bloats the
    index and slows indexing/merge. Returns "" when there is no CJK text.
    """
    return " ".join(_CJK_RE.findall(text))


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


def build_permission_filter(
    schema: tantivy.Schema,
    user: AbstractBaseUser,
    viewer_group_ids: Iterable[int] = (),
) -> tantivy.Query:
    """
    Build a query filter for user document permissions.

    Creates a query that matches only documents visible to the specified user
    according to paperless-ngx permission rules:
    - Public documents (no owner) are visible to all users
    - Private documents are visible to their owner
    - Documents explicitly shared with the user are visible
    - Documents shared with one of the user's current groups are visible

    Args:
        schema: Tantivy schema for field validation
        user: User to check permissions for
        viewer_group_ids: Current group memberships for the user

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
    group_shared = [
        tantivy.Query.term_query(schema, "viewer_group_id", group_id)
        for group_id in viewer_group_ids
    ]
    return tantivy.Query.disjunction_max_query(
        [no_owner, owned, shared, *group_shared],
    )


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


# Double-quote characters (plus their typographic variants) are search syntax,
# not content. The simple-search analyzer tokenizes on \S+, so it keeps a quote
# glued to the adjacent word ('"digital'), and no indexed token can match that.
# Single quotes are deliberately not included: apostrophes occur inside real
# words ("don't", "O'Brien") and are indexed as part of the token, so stripping
# them here would break matching rather than fix it.
_QUOTE_CHARS: Final[str] = '["“”„″]'


def _strip_quote_syntax(raw_query: str) -> str:
    # Replaced with a space rather than removed, so 'foo"bar' stays two tokens.
    return regex.sub(_QUOTE_CHARS, " ", raw_query, timeout=_REGEX_TIMEOUT)


def _simple_query_tokens(raw_query: str) -> list[str]:
    # Tokenize and fold via the same analyzer used to index simple_title /
    # simple_content, so query terms fold identically to the indexed terms
    # (single source of truth for ASCII folding).
    return simple_search_tokens(raw_query)


def _build_simple_token_query(
    index: tantivy.Index,
    fields: list[str],
    token: str,
    *,
    allow_infix: bool,
) -> tantivy.Query:
    escaped = regex.escape(token)
    # The simple analyzer keeps punctuation inside whitespace-delimited terms.
    # Boundary-constrained query tokens may therefore begin either at the indexed
    # term boundary or after punctuation within a term (for example,
    # ``medical-history``). This avoids matching a numeric token such as ``6``
    # in the middle of ``16``.
    pattern = (
        f".*{escaped}.*"
        if allow_infix
        else (
            f"({escaped}.*|"
            rf".*[\x20-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]{escaped}.*)"
        )
    )
    field_queries: list[tuple[tantivy.Occur, tantivy.Query]] = []
    for field in fields:
        query = tantivy.Query.regex_query(index.schema, field, pattern)
        boost = _SIMPLE_FIELD_BOOSTS.get(field, 1.0)
        if boost > 1.0:
            query = tantivy.Query.boost_query(query, boost)
        field_queries.append((tantivy.Occur.Should, query))

    if len(field_queries) == 1:
        return field_queries[0][1]
    return tantivy.Query.boolean_query(field_queries)


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
    Quote characters are stripped: simple search has no phrase concept, so they
    are meaningless syntax here, and leaving them in makes the query unmatchable.
    When cjk_fields is provided and the query contains CJK characters, an
    additional Should clause searches those bigram-tokenized fields, which match
    CJK substrings the simple analyzer can't (long whitespace-free runs are
    dropped by remove_long).
    """
    tokens = _simple_query_tokens(_strip_quote_syntax(raw_query))

    clauses: list[tuple[tantivy.Occur, tantivy.Query]] = []
    if tokens:
        # Match every query token, regardless of its position in the document.
        # Each token may occur in any of the requested fields, so text mode also
        # finds documents whose matches are split between title and content.
        token_queries = [
            (
                tantivy.Occur.Must,
                _build_simple_token_query(
                    index,
                    fields,
                    token,
                    # Preserve historical infix matching for single-token
                    # searches. In multi-token searches, constrain numeric
                    # tokens to boundaries to avoid partial-number overlap.
                    # This depends on token content, not query order.
                    allow_infix=len(tokens) == 1 or not token.isdecimal(),
                ),
            )
            for token in tokens
        ]
        simple_query = (
            token_queries[0][1]
            if len(token_queries) == 1
            else tantivy.Query.boolean_query(token_queries)
        )
        clauses.append((tantivy.Occur.Should, simple_query))

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
    # Quotes go too, so highlighting stays consistent with what actually matched.
    tokens = _simple_query_tokens(
        regex.sub(r"[-+]", " ", _strip_quote_syntax(raw_query), timeout=_REGEX_TIMEOUT),
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
