from __future__ import annotations

import functools
import logging
import unicodedata
from functools import cache
from typing import TYPE_CHECKING
from typing import Final

import regex
import tantivy
import whoosh_compat as wc
from django.conf import settings
from whoosh_compat.emitters.tantivy_ import emit as tantivy_emit
from whoosh_compat.errors import Cause
from whoosh_compat.errors import Diagnostic
from whoosh_compat.errors import DiagnosticKind
from whoosh_compat.errors import QueryError

from documents.search._errors import InvalidDateQuery
from documents.search._errors import InvalidNumberQuery
from documents.search._errors import MultipleSearchQueryErrors
from documents.search._errors import SearchQueryError
from documents.search._registry import get_field_registry
from documents.search._tokenizer import _bigram_analyzer
from documents.search._tokenizer import paperless_text_analyzer
from documents.search._tokenizer import simple_search_tokens

if TYPE_CHECKING:
    from datetime import tzinfo

logger = logging.getLogger("paperless.search")

# Maximum seconds any single regex substitution over user-supplied query text
# may run. The one remaining use is a character class, which cannot backtrack,
# so the bound is an upper limit on that substitution's cost, not the ReDoS
# guard it was originally written as.
_REGEX_TIMEOUT: Final[float] = 1.0

# Matches CJK/Hangul characters so queries can be routed to bigram fields.
# Uses Unicode properties to cover all blocks including Extension B+ planes.
# The marks that sit inside a Japanese word are listed explicitly, because
# their Unicode script is Common and the script classes therefore miss
# them: the katakana prolonged sound mark ー (U+30FC) and its halfwidth form
# ｰ (U+FF70), the closing mark 〆 (U+3006), and the halfwidth voiced and
# semi-voiced sound marks ﾞ (U+FF9E) and ﾟ (U+FF9F). Without them a word
# splits into one-character runs, which have no bigrams: コーヒー becomes
# コ + ヒ, and halfwidth ﾊﾟﾝ becomes ﾊ + ﾝ, leaving nothing to index or
# search at all.
#
# The combining marks U+3099/U+309A are deliberately absent: everything
# entering the index and every query string is put through
# normalize_search_text first, so decomposed kana is composed away before
# this pattern ever sees it. The halfwidth marks are not, and cannot be:
# unlike パ (U+30D1), halfwidth katakana has no precomposed voiced form, so
# NFC leaves ﾊ + ﾟ as two codepoints where it folds か + U+3099 into が.
_CJK_RE: Final = regex.compile(
    r"[\p{Han}\p{Hiragana}\p{Katakana}\p{Hangul}ーｰ〆ﾞﾟ]+",
)


def normalize_search_text(text: str) -> str:
    """Put text into the one Unicode normal form the index is built in.

    Both the indexed text and the query string go through this, because a
    bigram is a pair of codepoints: NFD がっこう is four where NFC is three,
    so an unnormalized document never matches a normalized query.

    NFC, not NFKC: folding ﾊﾟﾝ to パン would be a search-behavior decision
    rather than an encoding one.
    """
    return unicodedata.normalize("NFC", text)


def _user_facing_emit_message(d: Diagnostic) -> str:
    """A user-safe message for an emit-time QueryError's Diagnostic.

    Built from the Diagnostic's structured fields (kind, field), never from
    d.message: whoosh-compat documents that as developer/log output with no
    stability guarantee, and PATTERN_TOO_COMPLEX embeds the raw backend
    error text in it. SCHEMA_FIELD_MISSING never reaches here: _map_emit_error
    re-raises it before calling this function, the same as INTERNAL.
    """
    field = str(d.field) if d.field is not None else None
    if d.kind is DiagnosticKind.EXISTS_REQUIRES_FAST:
        return f"Existence searches (field:*) are not supported for field {field!r}."
    if d.kind is DiagnosticKind.TEXT_RANGE:
        return f"Range searches are not supported for field {field!r}."
    if d.kind is DiagnosticKind.PATTERN_TOO_COMPLEX:
        return f"The wildcard pattern for field {field!r} is too complex."
    logger.warning(
        "Unmapped emit diagnostic %s: %s",
        d.kind,
        d.message,
    )  # pragma: no cover
    return "The search query could not be executed."  # pragma: no cover


def _map_emit_error(e: QueryError) -> SearchQueryError:
    """Route an emit-time QueryError by its Diagnostic's Cause.

    INVALID_INPUT/UNSUPPORTED are user-input errors, exactly like a parse
    diagnostic, and map to a 400. INTERNAL means a defect in whoosh-compat
    or in our own AST handling, never the user's query, so the QueryError is
    re-raised rather than converted, reaching the generic 500 handler instead
    of blaming the query. MISCONFIGURED other than EXISTS_REQUIRES_FAST is
    treated the same way as INTERNAL: the registry and the index schema
    disagree, which only an operator can fix, and the exact same query would
    succeed on its own once the index is rebuilt. That makes it a transient
    server-side condition, not a permanently bad request, so it is logged as
    an error and re-raised rather than converted to a 400: telling the
    client their query is invalid would be wrong, it would work once the
    index catches up, and a 400 also hides the condition from monitoring
    that only watches 5xx rates.

    EXISTS_REQUIRES_FAST is the one MISCONFIGURED kind that is not a
    disagreement. whoosh-compat derives it from the registry's own FieldSpec
    (kind plus fast) without ever consulting the index schema, so it fires
    whenever a non-fast field of a kind that cannot answer "exists" is asked
    to: for us that is only the JSON fields, which field_descriptors() builds
    non-fast on purpose. "notes:*" and the five other spellings of it are
    ordinary user error that no operator action can clear, so they get the
    400 without the alert.
    """
    d = e.diagnostic
    if d.cause is Cause.INTERNAL:
        raise e
    if (
        d.cause is Cause.MISCONFIGURED
        and d.kind is not DiagnosticKind.EXISTS_REQUIRES_FAST
    ):
        logger.error(
            "Search index misconfiguration for field %s (%s): %s",
            d.field,
            d.kind.name,
            d.message,
        )
        raise e
    return SearchQueryError(_user_facing_emit_message(d))


def _has_cjk(text: str) -> bool:
    """Return True if text contains any CJK characters."""
    return bool(_CJK_RE.search(text))


def extract_cjk_text(text: str) -> str:
    """Join the CJK runs in ``text`` for indexing into bigram (char-ngram) fields.

    Mirrors the query side, which extracts the CJK runs of whatever it is
    about to search for (the raw string in simple modes, each CJK term's
    own text in query mode): only CJK runs are ever searched against
    the bigram fields, so only CJK runs are worth indexing there. Latin text
    fed to a character-bigram field is never matched and only bloats the
    index and slows indexing/merge. Returns "" when there is no CJK text.
    """
    return " ".join(_CJK_RE.findall(text))


def _parse_cjk_text(
    index: tantivy.Index,
    cjk_text: str,
    fields: list[str],
) -> tantivy.Query | None:
    """Parse a plain CJK run string against ``fields``, or None if it won't parse."""
    try:
        return index.parse_query(cjk_text, fields)
    except Exception:
        # Broad on purpose: cjk_text isn't filtered to a guaranteed-safe
        # token set, so the exact failure mode tantivy could raise here
        # isn't pinned down.
        logger.debug(
            "Skipping CJK search clause: could not parse CJK text: %r",
            cjk_text,
        )
        return None


def _build_cjk_query(
    index: tantivy.Index,
    raw_query: str,
    fields: list[str],
) -> tantivy.Query | None:
    """Build a bigram-field query from the CJK runs in ``raw_query``.

    For the simple (TEXT/TITLE) modes, whose input is plain text and carries
    no query grammar to respect. Only the CJK character runs are extracted, so
    a stray ``field:`` prefix or ``-``/``+`` in the input can neither leak
    field semantics nor fail the parse, and no Latin token reaches the
    character-bigram matcher (where it would produce spurious matches against
    unrelated Latin text). Returns None when there is no CJK text or the parse
    fails.
    """
    cjk_text = extract_cjk_text(raw_query)
    if not cjk_text:
        return None
    return _parse_cjk_text(index, cjk_text, fields)


_DEFAULT_SEARCH_FIELDS: Final[list[str]] = [
    "title",
    "content",
    "correspondent",
    "document_type",
    "tag",
]
_SIMPLE_SEARCH_FIELDS: Final[list[str]] = ["simple_title", "simple_content"]
_TITLE_SEARCH_FIELDS: Final[list[str]] = ["simple_title"]
# The bigram (character-ngram) companion of each default search field.
_CJK_BIGRAM_FIELDS: Final[dict[str, str]] = {
    field: f"bigram_{field}" for field in _DEFAULT_SEARCH_FIELDS
}
_CJK_CONTENT_FIELDS: Final[list[str]] = ["bigram_content"]
_CJK_TITLE_FIELDS: Final[list[str]] = ["bigram_title"]
_FIELD_BOOSTS = {"title": 2.0}
_SIMPLE_FIELD_BOOSTS = {"simple_title": 2.0}


@cache
def _get_emit_field_registry(language: str | None) -> wc.FieldRegistry:
    """The parse registry plus the CJK bigram fields, for analyzing and
    emitting a query whose leaves _widen_leaf has widened. Cached per
    language, on the same trigger get_field_registry() rebuilds on.

    Never used to parse: the bigram fields are internal (absent from
    PUBLIC_FIELDS), and queries are still parsed against
    get_field_registry(), so ``bigram_content:...`` never becomes query
    syntax.

    The bigram specs set ``multitoken=Multitoken.AND`` explicitly. A
    widened leaf's bigram side always sits inside the widening Or, so under
    Multitoken.DEFAULT a run's bigrams would inherit that Or, and 東京都
    would match a document containing only 京都.
    """
    bigram_analyze = _bigram_analyzer().analyze
    return wc.FieldRegistry(
        [
            *get_field_registry(language),
            *(
                wc.FieldSpec(
                    bigram_field,
                    wc.FieldKind.TEXT,
                    analyzer=bigram_analyze,
                    multitoken=wc.Multitoken.AND,
                )
                for bigram_field in _CJK_BIGRAM_FIELDS.values()
            ),
        ],
    )


# Splits text exactly where the content analyzer's simple tokenizer does,
# with none of its filters, so each piece is the raw text of one token the
# index could hold. No remove_long either: a long CJK run must still reach
# the bigram side.
_TOKEN_SPLITTER: Final = tantivy.TextAnalyzerBuilder(tantivy.Tokenizer.simple()).build()


def _collapse(
    node_cls: type[wc.ast.Node],
    children: list[wc.ast.Node],
    span: dict[str, int | None],
) -> wc.ast.Node:
    """Return the single child as it is, or wrap several in node_cls."""
    if len(children) == 1:
        return children[0]
    return node_cls(children=tuple(children), **span)


def _leaf_span(leaf: wc.ast.Term | wc.ast.Phrase) -> dict[str, int | None]:
    """The startchar/endchar kwargs a leaf's alternatives are built with,
    so a rewritten leaf still points at the same span of the original
    query text."""
    return {"startchar": leaf.startchar, "endchar": leaf.endchar}


def _cjk_alternative(leaf: wc.ast.Term | wc.ast.Phrase) -> wc.ast.Node | None:
    """Build the bigram alternative for a CJK leaf, or None if it gets none.

    The content analyzer keeps an unspaced CJK run as one token, so only
    the bigram fields can find a CJK term inside running text.

    The alternative is built from the leaf's own text, split where the
    content analyzer would split it. What each kind of piece contributes,
    and how the pieces combine, is commented at the step that decides it.
    None means there was nothing to build one from.
    """
    if leaf.field is None or leaf.field.name not in _CJK_BIGRAM_FIELDS:
        return None
    text = str(leaf.text)
    if not _has_cjk(text):
        return None
    span = _leaf_span(leaf)
    bigram_field = wc.FieldRef(_CJK_BIGRAM_FIELDS[leaf.field.name])
    cjk_terms: list[wc.ast.Node] = []
    latin_terms: list[wc.ast.Node] = []
    for token in _TOKEN_SPLITTER.analyze(text):
        runs = _CJK_RE.findall(token)
        if runs:
            # One bigram Term per run, never a joined string, which would
            # produce bigrams spanning the join. A run's own bigrams stay
            # jointly required through multitoken=AND on the bigram
            # FieldSpec (see _get_emit_field_registry), which no enclosing
            # group can loosen. A one-character run has no bigram at all
            # and analyzes away to nothing.
            cjk_terms.extend(
                wc.ast.Term(field=bigram_field, text=run, **span) for run in runs
            )
        else:
            # Latin the analyzer split off on its own. Latin glued to CJK
            # inside one token (東京report) never reaches here, and must
            # not: the index holds it only inside that whole unspaced
            # token, so requiring it would lose documents the run finds.
            latin_terms.append(wc.ast.Term(field=leaf.field, text=token, **span))
    # A Term's runs are alternatives to each other, the way the separate
    # bigram clause treated them. A Phrase's are required together: quoting
    # asks for more than the bare words, and the parser's default group is
    # And, so an Or here would make "東京都 大阪府" match strictly more
    # than 東京都 大阪府 does. And is also the tightest thing available,
    # since the bigram analyzer puts every token at position 0 and no
    # alternative built from it can enforce adjacency.
    cjk_group = wc.ast.And if isinstance(leaf, wc.ast.Phrase) else wc.ast.Or
    pieces: list[wc.ast.Node] = []
    if cjk_terms:
        pieces.append(_collapse(cjk_group, cjk_terms, span))
    pieces.extend(latin_terms)
    if not pieces:
        # A few hundred codepoints match _CJK_RE but yield no token at all
        # from the simple tokenizer (CJK radicals, circled and squared
        # forms), leaving nothing to widen with. The caller then leaves the
        # leaf as it is, and it analyzes to the same nothing it does today.
        return None
    # Separated latin is required alongside the CJK side, which is what
    # stops "invoice NOT 東京-report" from excluding every 東京 document.
    return _collapse(wc.ast.And, pieces, span)


# The index analyzer minus stemming: the same word boundaries and the same
# drops (remove_long, characters the simple tokenizer discards). The field's
# pattern_normalizer does the one stemming step.
_FUZZY_WORD_SPLITTER: Final = paperless_text_analyzer(None)


def _fuzzy_alternative(leaf: wc.ast.Term | wc.ast.Phrase) -> wc.ast.Node | None:
    """Build the near-match alternative for a leaf, or None if it gets none.

    Each of the leaf's words becomes a Fuzzy leaf on the leaf's own field.
    A Term's words are OR'd, which is the per-word recall the old clause
    had and what lets ``COVID-19`` match on one half. A Phrase's are
    AND-ed: quoting asks for more than the bare words, so an Or there
    would make a quoted phrase match strictly more than the same words
    unquoted. Adjacency is out of reach either way, so requiring every
    word is the floor.

    Words come from the index analyzer minus its stemmer, so a leaf gets a
    fuzzy side exactly when its exact side has tokens. A regex split would
    keep words the index never holds (``__``, or a word past remove_long),
    whose exact side analyzes to nothing, leaving a required fuzzy clause
    that can never match.

    Words of one character are skipped: with prefix matching, a
    one-character fuzzy term matches every term in the field.

    CJK words are skipped entirely. The content analyzer keeps an unspaced
    CJK run as one token, so a prefix Fuzzy over it matches any run within
    one edit of its start: ``東京`` would match a document holding only
    ``京都の観光案内``, the very thing the bigram fields' multitoken=AND
    exists to prevent (see _get_emit_field_registry). A two-character CJK
    word is as broad here as the one-character word the length guard
    already rejects, and _cjk_alternative supplies the in-run recall
    anyway, so there is nothing to gain and precision to lose.

    Fuzzy text goes through the field's pattern_normalizer rather than its
    analyzer, and the splitter's output is already lowercased and folded,
    so the word is stemmed exactly once.
    """
    words = [
        word
        for word in _FUZZY_WORD_SPLITTER.analyze(str(leaf.text))
        if len(word) > 1 and not _has_cjk(word)
    ]
    if not words:
        return None
    span = _leaf_span(leaf)
    group = wc.ast.And if isinstance(leaf, wc.ast.Phrase) else wc.ast.Or
    leaves: list[wc.ast.Node] = [
        wc.ast.Fuzzy(field=leaf.field, text=word, distance=1, prefix=True, **span)
        for word in words
    ]
    return _collapse(group, leaves, span)


def _widen_leaf(
    leaf: wc.ast.Term | wc.ast.Phrase,
    *,
    fuzzy: bool,
    negated: frozenset[int],
) -> wc.ast.Node:
    """``rewrite_leaf`` hook for emit(): widen a leaf on a default search
    field to ``Or(leaf, alternatives...)`` where it sits, and leave every
    other leaf as it is.

    Widening in place, rather than OR-ing a separate clause in at the top,
    keeps every AND, NOT, REQUIRE, boost, field restriction and positive
    filter around the leaf applying to its widened match too.

    A leaf can gain a CJK alternative, a fuzzy one, or both. A negated
    leaf keeps its CJK alternative, because NOT X should exclude exactly
    what X matches, but gets no fuzzy one: with prefix matching, NOT tax
    would otherwise exclude "taxi" and "taxonomy". Negated leaves are
    identified by identity through the pre-scan, since the hook cannot see
    a leaf's context.

    analyze() only offers Term and Phrase leaves, so Prefix and Wildcard
    patterns are never widened.
    """
    if leaf.field is None or leaf.field.name not in _DEFAULT_SEARCH_FIELDS:
        return leaf
    span = _leaf_span(leaf)
    alternatives: list[wc.ast.Node] = []
    cjk = _cjk_alternative(leaf)
    if cjk is not None:
        alternatives.append(cjk)
    if fuzzy and id(leaf) not in negated:
        near = _fuzzy_alternative(leaf)
        if near is not None:
            alternatives.append(wc.ast.Boosted(child=near, boost=0.1, **span))
    if not alternatives:
        return leaf
    # The leaf itself, not a copy: analyze() then keeps it combined the way
    # its enclosing group says rather than the way this Or would, and a long
    # run its analyzer drops to nothing leaves just the alternative.
    return wc.ast.Or(children=(leaf, *alternatives), **span)


def _negated_leaf_ids(node: wc.ast.Node) -> frozenset[int]:
    """Return the id() of every Term and Phrase under a negation.

    A negated leaf keeps its CJK alternative but gets no fuzzy one, and
    the hook cannot see a leaf's context, so the tree is walked once here
    and the hook compares by identity. analyze() guarantees it is handed
    the input tree's own leaf objects, which is what makes identity work.

    Negative positions are Not.child and AndNot.negative, and nothing
    else in the node set. Leaves are collected at any depth and under any
    number of negations: over-collecting costs a widening, while missing
    a negated leaf would let NOT tax exclude "taxi".

    Iterative, and total over node types: this runs outside emit()'s
    error conversion, so an exception here would reach the generic 500
    handler.
    """
    negated: set[int] = set()
    stack: list[tuple[wc.ast.Node, bool]] = [(node, False)]
    while stack:
        current, under_negation = stack.pop()
        if isinstance(current, (wc.ast.Term, wc.ast.Phrase)):
            if under_negation:
                negated.add(id(current))
        elif isinstance(current, wc.ast.Not):
            stack.append((current.child, True))
        elif isinstance(current, wc.ast.AndNot):
            stack.append((current.positive, under_negation))
            stack.append((current.negative, True))
        elif isinstance(current, wc.ast.AndMaybe):
            stack.append((current.required, under_negation))
            stack.append((current.optional, under_negation))
        elif isinstance(current, wc.ast.Require):
            stack.append((current.scored, under_negation))
            stack.append((current.filter_only, under_negation))
        elif isinstance(current, wc.ast.Boosted):
            stack.append((current.child, under_negation))
        elif isinstance(current, (wc.ast.And, wc.ast.Or)):
            stack.extend((child, under_negation) for child in current.children)
    return frozenset(negated)


# Weight of the tiebreak clause that restores relevance ordering among
# near-miss results. The widened tree is const-scored so the threshold
# cannot cut a near-miss by the BM25 spread of the query's correctly
# spelled words; this small share of its real score orders them again.
# A BM25 spread above 0.1/_FUZZY_TIEBREAK can still cut one.
_FUZZY_TIEBREAK: Final[float] = 0.01


def _any_of(clauses: list[tuple[tantivy.Occur, tantivy.Query]]) -> tantivy.Query:
    """Collapse a clause list: none -> empty, one -> itself (no wasted
    single-clause boolean_query wrapping), many -> boolean_query(clauses)."""
    if not clauses:
        return tantivy.Query.empty_query()
    if len(clauses) == 1:
        return clauses[0][1]
    return tantivy.Query.boolean_query(clauses)


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

    return _any_of(field_queries)


def parse_user_query(
    index: tantivy.Index,
    raw_query: str,
    tz: tzinfo,
) -> tantivy.Query:
    """
    Parse user query through whoosh-compat, then widen its leaves and emit,
    once or twice depending on whether fuzzy matching is on.

    1. wc.parse() against the shared FieldRegistry (whoosh grammar -> AST).
       Bare notes:/custom_fields: prefixes resolve to their default subpath
       (notes.note:/custom_fields.value:) directly in the registry, via
       each JSON field's SubpathSpec(default=True).
    2. Any diagnostics (bad dates/numbers) map to SearchQueryError subclasses
       and raise, the view returns HTTP 400 with every offending field
       listed, not just the first.
    3. With fuzzy off, the AST is emitted once. If the query has CJK text,
       emit()'s rewrite_leaf hook (_widen_leaf) rewrites each CJK term in
       the AST to also match its bigram field, in place, so the rest of
       the query constrains the bigram match too. With fuzzy on, the AST
       is emitted twice through the same hook: once with fuzzy=True for
       the widened tree used as a filter, and once with fuzzy=False for a
       normally scored tree, and the two are blended into a boolean query
       (see the comment above the blend for why). Either way the tree is
       analyzed and emitted against _get_emit_field_registry() whenever
       CJK or fuzzy widening applies, which adds the bigram fields; the
       query itself was parsed without them.
       emit() turns the AST into a tantivy.Query directly (no string
       round-trip). A QueryError is routed by its Diagnostic's Cause
       (_map_emit_error): a construct that parses but can't execute against
       tantivy (e.g. a text-field range) is a 400, a registry/schema
       mismatch is logged and re-raised, and an INTERNAL defect is
       re-raised.
    """
    registry = get_field_registry(settings.SEARCH_LANGUAGE)
    result = wc.parse(
        raw_query,
        registry=registry,
        default_fields=_DEFAULT_SEARCH_FIELDS,
        field_boosts=_FIELD_BOOSTS,
        tz=tz,
    )
    if result.diagnostics:
        raise _diagnostics_to_error(result.diagnostics)

    fuzzy_on = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD is not None
    cjk = _has_cjk(raw_query)
    emit_registry = (
        _get_emit_field_registry(settings.SEARCH_LANGUAGE)
        if cjk or fuzzy_on
        else registry
    )
    negated = _negated_leaf_ids(result.ast) if fuzzy_on else frozenset()

    def emit_widened(*, fuzzy: bool) -> tantivy.Query:
        hook = (
            functools.partial(_widen_leaf, fuzzy=fuzzy, negated=negated)
            if cjk or fuzzy
            else None
        )
        return tantivy_emit(
            result.ast,
            index=index,
            registry=emit_registry,
            rewrite_leaf=hook,
        )

    try:
        if not fuzzy_on:
            return emit_widened(fuzzy=False)
        widened = emit_widened(fuzzy=True)
        scored = emit_widened(fuzzy=False)
    except QueryError as e:
        raise _map_emit_error(e) from e

    # The widened tree supplies the matched set at a flat score, so a
    # near-miss is not ranked by how well the query's correctly spelled
    # words matched. The CJK-only tree adds real scoring back for what
    # matched exactly, and the last clause reintroduces the widened tree's
    # own scoring at a small weight so near-misses still rank among
    # themselves. const_score_query discards every boost inside it, the
    # title field's 2.0 included, so a title match earns its boost through
    # the second and third clauses rather than the first.
    return tantivy.Query.boolean_query(
        [
            (tantivy.Occur.Must, tantivy.Query.const_score_query(widened, 0.1)),
            (tantivy.Occur.Should, scored),
            (
                tantivy.Occur.Should,
                tantivy.Query.boost_query(widened, _FUZZY_TIEBREAK),
            ),
        ],
    )


# The three whoosh-compat kinds for a wildcard on a field that cannot
# carry one. d.field_kind supplies the discriminator, so naming the field's
# type needs no second trip through the registry.
_PATTERN_ON_KINDS: Final = frozenset(
    {
        DiagnosticKind.PATTERN_ON_NUMERIC,
        DiagnosticKind.PATTERN_ON_BOOLEAN_EXISTS,
        DiagnosticKind.PATTERN_ON_SUBPATH,
    },
)


def _diagnostics_to_error(diagnostics: tuple[Diagnostic, ...]) -> SearchQueryError:
    errors = [_single_diagnostic_to_error(d) for d in diagnostics]
    return errors[0] if len(errors) == 1 else MultipleSearchQueryErrors(errors)


def _single_diagnostic_to_error(d: Diagnostic) -> SearchQueryError:
    # d.field is a FieldRef, not a str: str(d.field) gives the canonical
    # dotted name (an aliased query, e.g. type:, reports document_type).
    field_name = str(d.field) if d.field is not None else None
    if d.kind is DiagnosticKind.BAD_DATE:
        return InvalidDateQuery(field_name, d.raw_value)
    if d.kind is DiagnosticKind.BAD_NUMBER:
        return InvalidNumberQuery(field_name, d.raw_value)
    if d.kind is DiagnosticKind.TOO_DEEP:
        return SearchQueryError("The search query is nested too deeply.")
    if d.kind in _PATTERN_ON_KINDS:
        kind_label = f" ({d.field_kind.name.lower()})" if d.field_kind else ""
        return SearchQueryError(
            f"Wildcard patterns are not supported for field "
            f"{field_name!r}{kind_label}.",
        )
    if d.kind is DiagnosticKind.SINGLE_CHAR_BRACKET_RANGE:
        field_label = f" for field {field_name!r}" if field_name else ""
        return SearchQueryError(
            f"{d.raw_value!r} looks like a bracket range{field_label}, but "
            "'[' is not a wildcard character on its own. Combine it with a "
            "wildcard, e.g. a trailing '*', or double-quote the value to "
            "search it as literal text.",
        )
    logger.warning(
        "Unmapped parse diagnostic %s: %s",
        d.kind,
        d.message,
    )  # pragma: no cover
    return SearchQueryError(
        "The search query could not be executed.",
    )  # pragma: no cover


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
    tokens = simple_search_tokens(raw_query)

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
        clauses.append((tantivy.Occur.Should, _any_of(token_queries)))

    if cjk_fields and _has_cjk(raw_query):
        cjk_q = _build_cjk_query(index, raw_query, cjk_fields)
        if cjk_q is not None:
            clauses.append((tantivy.Occur.Should, cjk_q))

    return _any_of(clauses)


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
    tokens = simple_search_tokens(
        regex.sub(r"[-+]", " ", raw_query, timeout=_REGEX_TIMEOUT),
    )
    if not tokens:
        return tantivy.Query.empty_query()

    # Quote each token as its own phrase, escaping backslashes and embedded
    # quotes. simple search tokens can carry arbitrary Tantivy syntax
    # characters (`"`, `:`, `(`, `[`, `/`, ...) that the query-string parser
    # would otherwise interpret as query grammar rather than literal text.
    quoted_tokens = [
        '"' + token.replace("\\", "\\\\").replace('"', '\\"') + '"' for token in tokens
    ]

    return index.parse_query(" ".join(quoted_tokens), ["content"])


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
        _SIMPLE_SEARCH_FIELDS,
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
        _TITLE_SEARCH_FIELDS,
        cjk_fields=_CJK_TITLE_FIELDS,
    )
