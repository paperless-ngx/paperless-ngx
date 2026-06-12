#!/usr/bin/env python3
"""Head-to-head benchmark: PaperlessLanceVectorStore vs PaperlessSqliteVecVectorStore.

Run from src/ with:
    uv run python bench_vector_store.py [OPTIONS]

Phase 1 (skipped if bench_data.pkl already exists): generate fake documents with
Faker and embed chunks via Ollama; save to disk for reuse.
Phase 2: benchmark both stores against identical data and print a comparison table.

Requires both classes to coexist in paperless_ai.vector_store (Task 3 Phase A).
After Phase B replaces the file, the Lance import fails gracefully and only the
sqlite-vec half runs.
"""
from __future__ import annotations

import argparse
import pickle
import statistics
import tempfile
import time
import uuid
from pathlib import Path
from typing import TypedDict

import httpx
from faker import Faker
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)

try:
    from paperless_ai.vector_store import PaperlessLanceVectorStore

    _LANCE_OK = True
except ImportError:
    _LANCE_OK = False

from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DEFAULT_OLLAMA_URL = "http://192.168.1.87:11434"
DEFAULT_EMBED_MODEL = "qwen3-embedding:4b"
DEFAULT_DATA_FILE = "bench_data.pkl"
DEFAULT_N_DOCS = 2000
DEFAULT_CHUNKS_PER_DOC = 3
DEFAULT_QUERY_ITERS = 50
_BATCH = 32


def _embed(texts: list[str], url: str, model: str) -> list[list[float]]:
    r = httpx.post(
        f"{url}/api/embed",
        json={"model": model, "input": texts},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def warm_up(url: str, model: str) -> int:
    """Fire one embed call to load the model into GPU; return embedding dim."""
    print(f"Warming up {model}...", end=" ", flush=True)
    dim = len(_embed(["warm"], url, model)[0])
    print(f"dim={dim}")
    return dim


def generate_and_save(
    n_docs: int,
    chunks_per_doc: int,
    url: str,
    model: str,
    out: str,
) -> list[dict]:
    fake = Faker()
    Faker.seed(42)
    print(f"Generating {n_docs} docs ({chunks_per_doc} chunks each)...")
    docs = []
    for i in range(n_docs):
        body = "\n\n".join(fake.paragraph(nb_sentences=8) for _ in range(3))
        clen = max(1, len(body) // chunks_per_doc)
        chunks = []
        for j in range(chunks_per_doc):
            s = j * clen
            e = s + clen if j < chunks_per_doc - 1 else len(body)
            chunks.append({"node_id": str(uuid.uuid4()), "text": body[s:e], "embedding": None})
        docs.append({
            "doc_id": str(i + 1),
            "title": fake.catch_phrase(),
            "modified": fake.date_time_this_decade().isoformat(),
            "chunks": chunks,
        })

    all_texts = [c["text"] for d in docs for c in d["chunks"]]
    print(f"Embedding {len(all_texts)} chunks in batches of {_BATCH}...")
    embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), _BATCH):
        embeddings.extend(_embed(all_texts[i : i + _BATCH], url, model))
        print(f"  {min(i + _BATCH, len(all_texts))}/{len(all_texts)}", end="\r", flush=True)
    print()

    idx = 0
    for d in docs:
        for c in d["chunks"]:
            c["embedding"] = embeddings[idx]
            idx += 1

    with open(out, "wb") as f:
        pickle.dump(docs, f)
    print(f"Saved to {out}")
    return docs


def _build_nodes(docs: list[dict]) -> list[TextNode]:
    nodes = []
    for d in docs:
        for c in d["chunks"]:
            n = TextNode(
                id_=c["node_id"],
                text=c["text"],
                metadata={"document_id": d["doc_id"], "modified": d["modified"]},
            )
            n.relationships = {}
            n.embedding = c["embedding"]
            nodes.append(n)
    return nodes


def _in_filter(ids: list[str]) -> MetadataFilters:
    return MetadataFilters(
        filters=[MetadataFilter(key="document_id", operator=FilterOperator.IN, value=ids)]
    )


def _dir_bytes(path: str) -> int:
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())


def _sqlite_bytes(uri: str) -> int:
    p = Path(uri) / "llmindex.db"
    return p.stat().st_size if p.exists() else 0


def run_bench(
    store,
    nodes: list[TextNode],
    docs: list[dict],
    q_iters: int,
    is_lance: bool,
) -> dict:
    doc_ids = [d["doc_id"] for d in docs]
    filter_ids = doc_ids[: max(1, len(doc_ids) // 5)]
    q_vecs = [nodes[i * 10 % len(nodes)].embedding for i in range(q_iters)]
    by_doc: dict[str, list[TextNode]] = {}
    for n in nodes:
        by_doc.setdefault(n.metadata["document_id"], []).append(n)
    uri = store._uri  # noqa: SLF001

    # insert
    t0 = time.perf_counter()
    store.add(list(nodes))
    r: dict = {"insert": time.perf_counter() - t0}

    # query plain
    times = []
    for emb in q_vecs:
        t0 = time.perf_counter()
        store.query(VectorStoreQuery(query_embedding=emb, similarity_top_k=10))
        times.append(time.perf_counter() - t0)
    r["qp50"] = statistics.median(times)
    r["qp95"] = sorted(times)[int(len(times) * 0.95)]

    # query filtered
    times = []
    flt = _in_filter(filter_ids)
    for emb in q_vecs:
        t0 = time.perf_counter()
        store.query(VectorStoreQuery(query_embedding=emb, similarity_top_k=10, filters=flt))
        times.append(time.perf_counter() - t0)
    r["qfp50"] = statistics.median(times)
    r["qfp95"] = sorted(times)[int(len(times) * 0.95)]

    # get_modified_times
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        store.get_modified_times()
        times.append(time.perf_counter() - t0)
    r["gmt_p50"] = statistics.median(times)

    # upsert (fresh node IDs, same embeddings)
    times = []
    for doc in docs[:q_iters]:
        orig = by_doc.get(doc["doc_id"], [])
        if not orig:
            continue
        fresh = []
        for o in orig:
            fn = TextNode(
                id_=str(uuid.uuid4()),
                text=o.text,
                metadata=o.metadata.copy(),
            )
            fn.relationships = {}
            fn.embedding = o.embedding
            fresh.append(fn)
        t0 = time.perf_counter()
        store.upsert_document(doc["doc_id"], fresh)
        times.append(time.perf_counter() - t0)
    r["up50"] = statistics.median(times) if times else 0.0
    r["up95"] = sorted(times)[int(len(times) * 0.95)] if times else 0.0

    r["size_pre"] = _dir_bytes(uri) if is_lance else _sqlite_bytes(uri)

    # compact
    t0 = time.perf_counter()
    if is_lance:
        store.compact(retention_seconds=0)
    else:
        store.compact(force=True)
    r["compact"] = time.perf_counter() - t0

    r["size_post"] = _dir_bytes(uri) if is_lance else _sqlite_bytes(uri)
    return r


def _pct(lv: float | None, sv: float) -> str:
    if lv is None or lv == 0:
        return "N/A"
    p = (sv - lv) / lv * 100
    return f"{'+' if p > 0 else ''}{p:.0f}%"


def print_results(nodes: list[TextNode], q_iters: int, lance: dict | None, sq: dict) -> None:
    W = 30
    n, dim = len(nodes), len(nodes[0].embedding)
    print(f"\n=== Vector Store Benchmark ===")
    print(f"Nodes: {n} | Dim: {dim} | Query iters: {q_iters}\n")
    lh = "LanceDB" if lance else "LanceDB (N/A)"
    print(f"{'Operation':<{W}} {lh:<22} {'sqlite-vec':<22} {'Delta'}")
    print("-" * (W + 66))

    def _s(v: float) -> str:
        return f"{v:.3f}s"

    def _ms(v: float) -> str:
        return f"{v * 1000:.1f}ms"

    def _mb(v: float) -> str:
        return f"{v / 1e6:.1f} MB"

    def row(label: str, lv: float | None, sv: float, fmt) -> None:
        ls = fmt(lv) if lv is not None else "N/A"
        print(f"{label:<{W}} {ls:<22} {fmt(sv):<22} {_pct(lv, sv)}")

    def row2(label: str, lv1: float | None, lv2: float | None, sv1: float, sv2: float) -> None:
        def ms_pair(a: float, b: float) -> str:
            return f"{_ms(a)} / {_ms(b)}"
        ls = ms_pair(lv1, lv2) if lv1 is not None else "N/A"
        print(f"{label:<{W}} {ls:<22} {ms_pair(sv1, sv2):<22} {_pct(lv1, sv1)}")

    L = lance
    row(f"insert ({n} nodes)", L["insert"] if L else None, sq["insert"], _s)
    row2("query plain p50/p95",
         L["qp50"] if L else None, L["qp95"] if L else None, sq["qp50"], sq["qp95"])
    row2("query filtered p50/p95",
         L["qfp50"] if L else None, L["qfp95"] if L else None, sq["qfp50"], sq["qfp95"])
    row("get_modified_times p50", L["gmt_p50"] if L else None, sq["gmt_p50"], _ms)
    row2("upsert p50/p95",
         L["up50"] if L else None, L["up95"] if L else None, sq["up50"], sq["up95"])
    row("compact", L["compact"] if L else None, sq["compact"], _s)
    row("file size pre-compact", L["size_pre"] if L else None, sq["size_pre"], _mb)
    row("file size post-compact", L["size_post"] if L else None, sq["size_post"], _mb)


def main() -> None:
    ap = argparse.ArgumentParser(description="Vector store head-to-head benchmark")
    ap.add_argument("--n-docs", type=int, default=DEFAULT_N_DOCS)
    ap.add_argument("--chunks-per-doc", type=int, default=DEFAULT_CHUNKS_PER_DOC)
    ap.add_argument("--data-file", default=DEFAULT_DATA_FILE)
    ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    ap.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    ap.add_argument("--query-iters", type=int, default=DEFAULT_QUERY_ITERS)
    args = ap.parse_args()

    warm_up(args.ollama_url, args.embed_model)

    data_path = Path(args.data_file)
    if args.regenerate or not data_path.exists():
        docs = generate_and_save(
            args.n_docs, args.chunks_per_doc, args.ollama_url, args.embed_model, args.data_file
        )
    else:
        print(f"Loading {args.data_file}...")
        with open(data_path, "rb") as f:
            docs = pickle.load(f)
        print(f"Loaded {len(docs)} docs ({sum(len(d['chunks']) for d in docs)} nodes)")

    all_nodes = _build_nodes(docs)

    lance_r = None
    if _LANCE_OK:
        print("\nBenchmarking LanceDB...")
        with tempfile.TemporaryDirectory() as d:
            store = PaperlessLanceVectorStore(uri=d)
            lance_r = run_bench(store, all_nodes, docs, args.query_iters, is_lance=True)
    else:
        print("Skipping LanceDB (PaperlessLanceVectorStore not importable).")

    print("\nBenchmarking sqlite-vec...")
    with tempfile.TemporaryDirectory() as d:
        store = PaperlessSqliteVecVectorStore(uri=d)
        sqlite_r = run_bench(store, all_nodes, docs, args.query_iters, is_lance=False)

    print_results(all_nodes, args.query_iters, lance_r, sqlite_r)


if __name__ == "__main__":
    main()
