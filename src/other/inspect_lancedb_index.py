#!/usr/bin/env python
"""Inspect the LanceDB vector index: row count, schema, per-column sizes, and disk layout.

Usage (from repo root):
    PAPERLESS_SECRET_KEY=x uv run python inspect_lancedb_index.py [index_path]

Default index_path: data/llm_index (relative to cwd) or the container-testing path.
"""

import sys
from pathlib import Path

import lancedb

INDEX_PATHS = [
    "/tank/users/trenton/projects/container-testing/paperless-ngx/data/llm_index",
    "data/llm_index",
]

path = (
    sys.argv[1]
    if len(sys.argv) > 1
    else next(
        (p for p in INDEX_PATHS if Path(p).exists()),
        None,
    )
)
if path is None or not Path(path).exists():
    print(f"No index found. Pass path as argument or create one at: {INDEX_PATHS[0]}")
    sys.exit(1)

print(f"Index path: {path}")
lance_dir = Path(path) / "documents.lance"

# Disk layout
print("\n--- Disk layout ---")
for subdir in ["data", "_versions", "_transactions", "_indices"]:
    p = lance_dir / subdir
    if p.exists():
        size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        print(f"  {subdir:20s}: {size / 1024 / 1024:.1f} MB")

db = lancedb.connect(path)
tbl = db.open_table("documents")
total_rows = tbl.count_rows()

print("\n--- Table stats ---")
print(f"  Rows: {total_rows}")
print(f"  Schema: {tbl.schema}")

dim = tbl.schema.field("vector").type.list_size
print(
    f"\n  Vector dim: {dim}, float32 raw: {total_rows * dim * 4 / 1024 / 1024:.2f} MB",
)

print("\n--- In-memory column sizes (Arrow buffers) ---")
arrow_table = tbl.search().limit(total_rows).to_arrow()
print(f"  {'TOTAL':20s}: {arrow_table.nbytes / 1024 / 1024:.2f} MB")
for i, field in enumerate(arrow_table.schema):
    col = arrow_table.column(i)
    print(f"  {field.name:20s}: {col.nbytes / 1024 / 1024:.2f} MB")

# Sample node_content to see what's inside
print("\n--- node_content sample (first row, keys only) ---")
import json

sample = json.loads(arrow_table.column("node_content")[0].as_py())
print(f"  Top-level keys: {list(sample.keys())}")
if "_node_content" in sample:
    inner = json.loads(sample["_node_content"])
    print(f"  _node_content keys: {list(inner.keys())}")
    if "metadata" in inner:
        print(f"  metadata keys: {list(inner['metadata'].keys())}")
