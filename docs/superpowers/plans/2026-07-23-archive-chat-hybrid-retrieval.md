# Archive AI Chat: Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix [#13234](https://github.com/paperless-ngx/paperless-ngx/issues/13234) — the archive-wide AI chat retrieves unrelated documents for exact keyword/number queries — by supplementing dense-vector retrieval with a lexical (Tantivy) fallback.

**Architecture:** A new `HybridRetriever` (a llama-index `BaseRetriever`) wraps the existing `VectorIndexRetriever`. It runs vector retrieval unchanged, then looks up the same query in the Tantivy full-text index; for any lexically-matched document the vector step missed, it pulls that document's single best-matching chunk from the vector store using the query embedding the vector step already computed. Results are unioned (vector nodes always kept, lexical additions capped) and handed to the existing `RetrieverQueryEngine` unchanged.

**Tech Stack:** Django backend, llama-index (`BaseRetriever`, `VectorIndexRetriever`, `QueryBundle`, `NodeWithScore`), the project's Tantivy full-text backend (`documents.search`), the sqlite-vec vector store (`paperless_ai.vector_store`).

## Global Constraints

- Tests are **pytest-style**, not `unittest.TestCase` — use fixtures and `@pytest.mark.django_db`, never Django's `TestCase`.
- **Group tests in classes**, with the `@pytest.mark.django_db` mark on the class, not scattered as flat free functions.
- Use **pytest-mock's `mocker` fixture** for all mocking — no bare `unittest.mock.patch` decorators/context managers in new code.
- Build model instances with **factory-boy factories** (`DocumentFactory` etc. from `documents/tests/factories.py`), not hand-rolled `Model.objects.create(...)`.
- **Annotate** every fixture param, fixture return type, and test signature.
- Tests run **on the VM only** (see project `CLAUDE.md`) via:
  ```bash
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<pytest targets/args>"
  ```
- Lint with the globally-installed `ruff` (not `uv run ruff`): `ruff check` / `ruff format`.
- **Deviation from the local design spec, discovered during API investigation:** the spec proposed threading a `user` parameter from `ChatStreamingView` down to `HybridRetriever` so the Tantivy lookup respects the same permission model as normal search. This turned out to be unnecessary: the retriever already intersects every lexical hit against the caller-supplied, already-permission-scoped `document_ids` set before using it for anything — so a lexical hit outside that set can never surface regardless of what `user` value is passed to `search_ids`. Passing `user=None` (an unrestricted lexical lookup, safely narrowed by the intersection afterward) is simpler and touches one less file (`views.py` is unchanged). This plan implements that simplification; flag it in the PR description as a deviation from the spec.

---

## File Structure

- **Create** `src/paperless_ai/retrieval.py` — the `HybridRetriever` class and its two tuning constants (`CHAT_LEXICAL_TOP_K`, `CHAT_MAX_NODES`). New file because it has one clear responsibility (merge two retrieval sources) distinct from `chat.py`'s job (drive the streaming LLM response) and `indexing.py`'s job (build/maintain the index).
- **Create** `src/paperless_ai/tests/test_retrieval.py` — unit tests for `HybridRetriever` (mocked dependencies) plus one real end-to-end integration test reproducing the bug report's shape.
- **Modify** `src/paperless_ai/chat.py` — `_stream_chat_with_documents` constructs a `HybridRetriever` wrapping the vector retriever instead of handing `VectorIndexRetriever` straight to `RetrieverQueryEngine.from_args`.
- **Modify** `src/paperless_ai/tests/test_chat.py` — add one regression test confirming `HybridRetriever` (not the raw vector retriever) is what gets used.

`views.py` is **not modified** — see the deviation note above.

---

## Task 1: `HybridRetriever`

**Files:**

- Create: `src/paperless_ai/retrieval.py`
- Test: `src/paperless_ai/tests/test_retrieval.py`

**Interfaces:**

- Produces: `paperless_ai.retrieval.HybridRetriever(vector_retriever: BaseRetriever, store: PaperlessSqliteVecVectorStore, document_ids: Iterable[int | str])` — a llama-index `BaseRetriever`. `.retrieve(query_str_or_bundle)` returns `list[NodeWithScore]`.
- Produces: `paperless_ai.retrieval.CHAT_LEXICAL_TOP_K` (int, default 5), `paperless_ai.retrieval.CHAT_MAX_NODES` (int, default 8).
- Consumes: `documents.search.get_backend()` / `documents.search.SearchMode`, `paperless_ai.indexing._document_id_filters(doc_ids) -> MetadataFilters`.

- [ ] **Step 1: Write the failing unit tests**

Create `src/paperless_ai/tests/test_retrieval.py`:

```python
from typing import Any

import pytest
import pytest_mock
from llama_index.core.schema import NodeWithScore
from llama_index.core.schema import QueryBundle
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import VectorStoreQueryResult

from paperless_ai.retrieval import CHAT_MAX_NODES
from paperless_ai.retrieval import HybridRetriever


def _node(doc_id: str, node_id: str, score: float = 0.5) -> NodeWithScore:
    text_node = TextNode(
        id_=node_id,
        text=f"content for {doc_id}",
        metadata={"document_id": doc_id},
    )
    return NodeWithScore(node=text_node, score=score)


def _store_query_result(doc_id: str, node_id: str, score: float = 0.9) -> VectorStoreQueryResult:
    text_node = TextNode(
        id_=node_id,
        text=f"lexical chunk for {doc_id}",
        metadata={"document_id": doc_id},
    )
    return VectorStoreQueryResult(nodes=[text_node], similarities=[score], ids=[node_id])


class TestHybridRetriever:
    def test_includes_lexical_only_hit(self, mocker: pytest_mock.MockerFixture) -> None:
        vector_node = _node("1", "vec-1")

        def fake_vector_retrieve(query_bundle: QueryBundle) -> list[NodeWithScore]:
            query_bundle.embedding = [0.1, 0.2]
            return [vector_node]

        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.side_effect = fake_vector_retrieve

        mock_backend = mocker.MagicMock()
        mock_backend.search_ids.return_value = [2]
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        store = mocker.MagicMock()
        store.query.return_value = _store_query_result("2", "lex-2")

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=store,
            document_ids=["1", "2"],
        )

        result = retriever.retrieve("Herdwaechter")

        result_doc_ids = [n.node.metadata["document_id"] for n in result]
        assert result_doc_ids == ["1", "2"]
        store.query.assert_called_once()

    def test_dedup_when_lexical_hit_already_in_vector_results(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        vector_node = _node("1", "vec-1")

        def fake_vector_retrieve(query_bundle: QueryBundle) -> list[NodeWithScore]:
            query_bundle.embedding = [0.1, 0.2]
            return [vector_node]

        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.side_effect = fake_vector_retrieve

        mock_backend = mocker.MagicMock()
        mock_backend.search_ids.return_value = [1]
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        store = mocker.MagicMock()

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=store,
            document_ids=["1"],
        )

        result = retriever.retrieve("query")

        assert len(result) == 1
        assert result[0] is vector_node
        store.query.assert_not_called()

    def test_cap_preserves_all_vector_nodes(self, mocker: pytest_mock.MockerFixture) -> None:
        vector_nodes = [_node(str(i), f"vec-{i}") for i in range(1, 6)]  # docs 1-5

        def fake_vector_retrieve(query_bundle: QueryBundle) -> list[NodeWithScore]:
            query_bundle.embedding = [0.1, 0.2]
            return vector_nodes

        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.side_effect = fake_vector_retrieve

        mock_backend = mocker.MagicMock()
        mock_backend.search_ids.return_value = [6, 7, 8, 9, 10]
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        store = mocker.MagicMock()
        store.query.side_effect = [
            _store_query_result(str(doc_id), f"lex-{doc_id}")
            for doc_id in (6, 7, 8, 9, 10)
        ]

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=store,
            document_ids=[str(i) for i in range(1, 11)],
        )

        result = retriever.retrieve("query")

        assert len(result) == CHAT_MAX_NODES
        result_doc_ids = [n.node.metadata["document_id"] for n in result]
        # All 5 vector hits survive; only the first 3 lexical additions fit.
        assert result_doc_ids == ["1", "2", "3", "4", "5", "6", "7", "8"]

    def test_excludes_lexical_hits_outside_permitted_documents(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        vector_node = _node("1", "vec-1")

        def fake_vector_retrieve(query_bundle: QueryBundle) -> list[NodeWithScore]:
            query_bundle.embedding = [0.1, 0.2]
            return [vector_node]

        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.side_effect = fake_vector_retrieve

        mock_backend = mocker.MagicMock()
        mock_backend.search_ids.return_value = [2, 99]
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        store = mocker.MagicMock()
        store.query.return_value = _store_query_result("2", "lex-2")

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=store,
            document_ids=["1", "2"],  # 99 is not permitted
        )

        result = retriever.retrieve("query")

        result_doc_ids = {n.node.metadata["document_id"] for n in result}
        assert result_doc_ids == {"1", "2"}
        store.query.assert_called_once()
        filters = store.query.call_args.args[0].filters
        assert filters.filters[0].value == ["2"]

    def test_lexical_backend_error_falls_back_to_vector_only(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        vector_node = _node("1", "vec-1")

        def fake_vector_retrieve(query_bundle: QueryBundle) -> list[NodeWithScore]:
            query_bundle.embedding = [0.1, 0.2]
            return [vector_node]

        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.side_effect = fake_vector_retrieve

        mock_backend = mocker.MagicMock()
        mock_backend.search_ids.side_effect = RuntimeError("index unavailable")
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=mocker.MagicMock(),
            document_ids=["1"],
        )

        result = retriever.retrieve("query")

        assert result == [vector_node]

    def test_no_embedding_skips_lexical_lookup(self, mocker: pytest_mock.MockerFixture) -> None:
        """Guards the case exercised by test_chat.py's fully-mocked
        VectorIndexRetriever, which never sets query_bundle.embedding."""
        vector_node = _node("1", "vec-1")
        vector_retriever = mocker.MagicMock()
        vector_retriever.retrieve.return_value = [vector_node]

        mock_backend = mocker.MagicMock()
        mocker.patch("paperless_ai.retrieval.get_backend", return_value=mock_backend)

        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=mocker.MagicMock(),
            document_ids=["1"],
        )

        result = retriever.retrieve("query")

        assert result == [vector_node]
        mock_backend.search_ids.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_retrieval.py -v"`
Expected: FAIL / collection error — `paperless_ai.retrieval` does not exist yet.

- [ ] **Step 3: Implement `HybridRetriever`**

Create `src/paperless_ai/retrieval.py`:

```python
import logging

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore
from llama_index.core.schema import QueryBundle
from llama_index.core.vector_stores.types import VectorStoreQuery

from documents.search import SearchMode
from documents.search import get_backend
from paperless_ai.indexing import _document_id_filters

logger = logging.getLogger("paperless_ai.retrieval")

CHAT_LEXICAL_TOP_K = 5
CHAT_MAX_NODES = 8


class HybridRetriever(BaseRetriever):
    """Supplements vector similarity search with Tantivy full-text hits.

    Dense embeddings retrieve poorly on exact keywords, numbers, and rare
    words (paperless-ngx#13234). This retriever runs the wrapped vector
    retriever unchanged, then looks the same query up in the Tantivy
    full-text index; for any matched document the vector step missed, it
    pulls that document's single best-matching chunk from the vector store,
    reusing the query embedding the vector step already computed.
    """

    def __init__(
        self,
        vector_retriever: BaseRetriever,
        store,
        document_ids,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._store = store
        self._document_ids = {str(doc_id) for doc_id in document_ids}
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        vector_nodes = self._vector_retriever.retrieve(query_bundle)

        if query_bundle.embedding is None:
            # Nothing to reuse for the lexical fallback (e.g. a retriever
            # stub in tests that never embeds); vector-only result.
            return vector_nodes

        try:
            lexical_ids = get_backend().search_ids(
                query_bundle.query_str,
                user=None,
                search_mode=SearchMode.TEXT,
                limit=CHAT_LEXICAL_TOP_K,
            )
        except Exception:
            logger.exception(
                "Lexical lookup failed for chat retrieval; "
                "falling back to vector-only results.",
            )
            return vector_nodes

        existing_ids = {
            str(node.node.metadata.get("document_id")) for node in vector_nodes
        }
        missing_ids = [
            str(doc_id)
            for doc_id in lexical_ids
            if str(doc_id) in self._document_ids and str(doc_id) not in existing_ids
        ]

        merged = list(vector_nodes)
        seen_node_ids = {node.node.node_id for node in merged}
        for doc_id in missing_ids:
            if len(merged) >= CHAT_MAX_NODES:
                break
            result = self._store.query(
                VectorStoreQuery(
                    query_embedding=query_bundle.embedding,
                    similarity_top_k=1,
                    filters=_document_id_filters([doc_id]),
                ),
            )
            for node, similarity in zip(
                result.nodes,
                result.similarities,
                strict=True,
            ):
                if node.node_id in seen_node_ids:
                    continue
                merged.append(NodeWithScore(node=node, score=similarity))
                seen_node_ids.add(node.node_id)

        return merged[:CHAT_MAX_NODES]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_retrieval.py -v"`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint**

Run: `ruff check src/paperless_ai/retrieval.py src/paperless_ai/tests/test_retrieval.py` and `ruff format src/paperless_ai/retrieval.py src/paperless_ai/tests/test_retrieval.py`
Expected: no errors; format is a no-op if the code above is already formatted correctly (fix any diffs it reports).

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/retrieval.py src/paperless_ai/tests/test_retrieval.py
git commit -m "Add HybridRetriever: lexical fallback for archive AI chat retrieval"
```

---

## Task 2: Wire `HybridRetriever` into `chat.py`

**Files:**

- Modify: `src/paperless_ai/chat.py:95-112`
- Modify: `src/paperless_ai/tests/test_chat.py`

**Interfaces:**

- Consumes: `paperless_ai.retrieval.HybridRetriever(vector_retriever, store, document_ids)` from Task 1.

- [ ] **Step 1: Write the failing regression test**

Add to the `TestStreamChatRetrieval` class in `src/paperless_ai/tests/test_chat.py` (it already has `temp_llm_index_dir` / `mock_embed_model` fixtures wired up via `conftest.py`):

```python
    def test_uses_hybrid_retriever(
        self,
        temp_llm_index_dir,
        mock_embed_model,
        mocker,
    ) -> None:
        """The retriever driving both reference-building and query-engine
        synthesis must be HybridRetriever, not the raw vector retriever,
        so the lexical fallback (#13234) is available.
        """
        doc = DocumentFactory.create(content="included document content")
        indexing.llm_index_add_or_update_document(doc)

        mock_hybrid_instance = mocker.MagicMock()
        mock_hybrid_instance.retrieve.return_value = []
        mock_hybrid_cls = mocker.patch(
            "paperless_ai.retrieval.HybridRetriever",
            return_value=mock_hybrid_instance,
        )
        mocker.patch("paperless_ai.chat.AIClient")

        list(chat.stream_chat_with_documents("question?", [doc]))

        mock_hybrid_cls.assert_called_once()
        _, kwargs = mock_hybrid_cls.call_args
        assert kwargs["document_ids"] == [doc.pk]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_chat.py::TestStreamChatRetrieval::test_uses_hybrid_retriever -v"`
Expected: FAIL — `HybridRetriever` is never constructed yet (`chat.py` still builds a bare `VectorIndexRetriever`).

- [ ] **Step 3: Wire `HybridRetriever` into `_stream_chat_with_documents`**

In `src/paperless_ai/chat.py`, inside `_stream_chat_with_documents` (currently lines 95-112), add the `HybridRetriever` import alongside the other lazy llama-index imports and replace the retriever construction:

```python
    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.response_synthesizers import get_response_synthesizer
    from llama_index.core.retrievers import VectorIndexRetriever

    from paperless_ai.retrieval import HybridRetriever

    config = AIConfig()
    filters = _document_id_filters(str(doc.pk) for doc in documents)

    # Hold the shared read lock for the whole operation: the query engine
    # retrieves from the vector store again during synthesis, so the connection
    # must stay open (and the swap must not run) until the stream finishes.
    with read_store() as store:
        index = load_or_build_index(config, store)
        vector_retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=CHAT_RETRIEVER_TOP_K,
            filters=filters,
        )
        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            store=store,
            document_ids=[doc.pk for doc in documents],
        )
```

(Everything after this — the `db_connection_released()` block, `retriever.retrieve(query_str)`, `RetrieverQueryEngine.from_args(retriever=retriever, ...)`, streaming — is unchanged; it already refers to `retriever`, which is now the `HybridRetriever` instance instead of the bare `VectorIndexRetriever`.)

- [ ] **Step 4: Run the full chat test file to verify everything passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_chat.py -v"`
Expected: PASS — the new test plus every pre-existing test in the file (they mock `VectorIndexRetriever` directly and don't set `query_bundle.embedding`, so `HybridRetriever` degrades to vector-only, matching their existing expectations unchanged).

- [ ] **Step 5: Lint**

Run: `ruff check src/paperless_ai/chat.py src/paperless_ai/tests/test_chat.py` and `ruff format src/paperless_ai/chat.py src/paperless_ai/tests/test_chat.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/chat.py src/paperless_ai/tests/test_chat.py
git commit -m "Use HybridRetriever in archive AI chat retrieval"
```

---

## Task 3: End-to-end regression test reproducing the bug report

**Files:**

- Test: `src/paperless_ai/tests/test_retrieval.py` (append a new class)

**Interfaces:**

- Consumes: `HybridRetriever` (Task 1), `documents.search.TantivyBackend`/`reset_backend`, `paperless_ai.indexing.{read_store, load_or_build_index, llm_index_add_or_update_document}`, `paperless.config.AIConfig`, `llama_index.core.retrievers.VectorIndexRetriever`.
- Produces (test-local): `temp_search_index_dir` fixture — isolates `settings.INDEX_DIR` for this file the same way `documents/tests/conftest.py`'s `_search_index` does elsewhere in the codebase.

This test uses a deterministic fake embedding model (distinct from the shared
`mock_embed_model` fixture, which returns the _same_ vector for everything and
so can't demonstrate a vector-search miss) so the "vector search misses this
document" half of the bug report is a guaranteed fact of the test, not a
coincidence of tie-breaking order.

It also needs its own Tantivy index isolation: `TantivyBackend()` with no
`path` falls back to `settings.INDEX_DIR`, which defaults to the real,
shared, non-tmp index location (`paperless/settings/__init__.py`) —
`paperless_ai/tests/conftest.py`'s existing `temp_llm_index_dir` fixture only
isolates the _vector_ store (`LLM_INDEX_DIR`/`LLM_INDEX_LOCK`), not the
Tantivy index. `documents/tests/conftest.py`'s `_search_index` fixture
already does this for Tantivy-touching tests elsewhere in the codebase (temp
`INDEX_DIR` + `reset_backend()` before and after) — add an equivalent local
fixture rather than writing real documents into the shared index directory
and leaking backend state across test runs.

- [ ] **Step 1: Write the test**

Append to `src/paperless_ai/tests/test_retrieval.py`:

```python
from collections.abc import Generator
from pathlib import Path

import pytest_mock
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.retrievers import VectorIndexRetriever
from pytest_django.fixtures import SettingsWrapper

from documents.search import TantivyBackend
from documents.search import reset_backend
from documents.tests.factories import DocumentFactory
from paperless.config import AIConfig
from paperless_ai import indexing


@pytest.fixture
def temp_search_index_dir(
    tmp_path: Path,
    settings: SettingsWrapper,
) -> Generator[Path, None, None]:
    """Isolate the Tantivy index for this test.

    `temp_llm_index_dir` (conftest.py) only isolates the *vector* store
    (LLM_INDEX_DIR); TantivyBackend() with no explicit path falls back to
    settings.INDEX_DIR, which defaults to the real, shared index location.
    Mirrors documents/tests/conftest.py's `_search_index` fixture.
    """
    index_dir = tmp_path / "search-index"
    index_dir.mkdir()
    settings.INDEX_DIR = index_dir
    reset_backend()
    yield index_dir
    reset_backend()


class _DeterministicFakeEmbedding(BaseEmbedding):
    """Unlike the shared mock_embed_model fixture (constant for everything),
    this embeds "noise" documents identically to the query and the target
    document orthogonally, so the vector search's top-k miss of the target
    is a guaranteed fact of the test, not a coincidence of tie-breaking."""

    def _get_query_embedding(self, query: str) -> list[float]:
        return [1.0, 0.0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.0, 1.0] if "Herdwaechter" in text else [1.0, 0.0]

    def get_query_embedding_dim(self) -> int:
        return 2


@pytest.fixture
def deterministic_embed_model(
    mocker: pytest_mock.MockerFixture,
) -> _DeterministicFakeEmbedding:
    fake = _DeterministicFakeEmbedding()
    mocker.patch("paperless_ai.indexing.get_embedding_model", return_value=fake)
    mocker.patch("paperless_ai.embedding.get_embedding_model", return_value=fake)
    return fake


@pytest.mark.django_db
class TestHybridRetrieverIntegration:
    def test_lexical_fallback_finds_document_vector_search_misses(
        self,
        temp_llm_index_dir,
        temp_search_index_dir,
        deterministic_embed_model,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Reproduces #13234: a document containing a rare keyword must be
        found via the lexical fallback even though its embedding is
        deliberately orthogonal to the query (so it can never appear in the
        vector-only top-k, regardless of tie-breaking)."""
        target = DocumentFactory.create(
            content="Rechnung ueber Herdwaechter Model X, invoice details.",
        )
        noise_docs = [
            DocumentFactory.create(content=f"unrelated noise document {i}")
            for i in range(6)
        ]
        all_docs = [*noise_docs, target]
        for doc in all_docs:
            indexing.llm_index_add_or_update_document(doc)

        backend = TantivyBackend()
        backend.open()
        try:
            for doc in all_docs:
                backend.add_or_update(doc)
            mocker.patch("paperless_ai.retrieval.get_backend", return_value=backend)

            with indexing.read_store() as store:
                index = indexing.load_or_build_index(AIConfig(), store)
                vector_retriever = VectorIndexRetriever(
                    index=index,
                    similarity_top_k=5,
                )

                # Sanity check on the premise: pure vector search misses the
                # target because its embedding is orthogonal to the query's.
                vector_only_ids = {
                    node.metadata.get("document_id")
                    for node in vector_retriever.retrieve("Herdwaechter")
                }
                assert str(target.pk) not in vector_only_ids

                retriever = HybridRetriever(
                    vector_retriever=vector_retriever,
                    store=store,
                    document_ids=[doc.pk for doc in all_docs],
                )
                nodes = retriever.retrieve("Herdwaechter")
        finally:
            backend.close()
            reset_backend()

        found_ids = {node.node.metadata.get("document_id") for node in nodes}
        assert str(target.pk) in found_ids
```

Add the missing import at the top of the file (alongside the Task 1 imports):

```python
from paperless_ai.retrieval import HybridRetriever
```

- [ ] **Step 2: Run the test**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_retrieval.py -v"`
Expected: PASS — all Task 1 unit tests plus this integration test (7 total). If the "sanity check on the premise" assertion fails, the test's embeddings aren't actually discriminating as intended — fix the fake embedding before trusting the rest of the test.

- [ ] **Step 3: Lint**

Run: `ruff check src/paperless_ai/tests/test_retrieval.py` and `ruff format src/paperless_ai/tests/test_retrieval.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/paperless_ai/tests/test_retrieval.py
git commit -m "Add end-to-end regression test for archive chat lexical fallback"
```

---

## Final check

- [ ] Run the full `paperless_ai` test suite once more to catch any cross-task interaction:
  ```bash
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai -v"
  ```
  Expected: PASS.
