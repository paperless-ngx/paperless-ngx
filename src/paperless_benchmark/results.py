# src/paperless_benchmark/results.py
from __future__ import annotations

import json
import subprocess
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "benchmark_results"


def _current_git_ref() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def append_history(entry: dict[str, Any], *, code_ref: str | None = None) -> None:
    """
    Append one line to benchmark_results/history.jsonl -- a local-only,
    append-only, cross-session record of every `benchmark run`/`profile`
    invocation. Unlike a single overwritten snapshot file, this survives
    across sessions so a benchmarking effort picked back up days later has
    a full timeline instead of only the most recent result.
    """
    RESULTS_DIR.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "code_ref": code_ref or _current_git_ref(),
        **entry,
    }
    with (RESULTS_DIR / "history.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
