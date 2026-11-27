#!/usr/bin/env bash
set -euo pipefail

BASELINE="b29fec117053637428a935d43af16d9e1d65c1fb"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${PBT02_ARTIFACT_DIR:-$REPO_ROOT/.artifacts/pbt-02-cycle-4}"
LOG_FILE="$ARTIFACT_DIR/pbt-02-run.log"
COVERAGE_JSON="$ARTIFACT_DIR/coverage.json"
VERIFICATION_JSON="$ARTIFACT_DIR/verification.json"

cd "$REPO_ROOT"

case "$(uname -s)" in
	Linux | Darwin) ;;
	*)
		echo "PBT-02 clean-machine demo requires Linux, macOS, or WSL2." >&2
		exit 2
		;;
esac

for command_name in git uv; do
	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "Missing prerequisite: $command_name" >&2
		exit 2
	fi
done

if ! git cat-file -e "$BASELINE^{commit}" 2>/dev/null; then
	echo "Baseline $BASELINE is unavailable; fetch the full fork history." >&2
	exit 2
fi

if ! git merge-base --is-ancestor "$BASELINE" HEAD; then
	echo "HEAD is not descended from the pinned PBT-02 baseline." >&2
	exit 2
fi

tracked_paths=(
	"src/documents/search/_query.py"
	"src/documents/tests/search/test_unicode_normalization.py"
)

if ! git diff --quiet "$BASELINE" HEAD -- "${tracked_paths[@]}"; then
	echo "PBT-02 source or tests changed after the pinned baseline." >&2
	echo "Update the report baseline and re-review before demonstrating." >&2
	exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
	echo "Tracked working-tree changes would make the demo non-reproducible." >&2
	exit 2
fi

mkdir -p "$ARTIFACT_DIR"

uv sync --python 3.12 --group testing --frozen

{
	echo "baseline=$BASELINE"
	echo "head=$(git rev-parse HEAD)"
	echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	echo "platform=$(uname -a)"
	echo "uv=$(uv --version)"
	echo "python=$(uv run --python 3.12 --dev --frozen python --version 2>&1)"
} >"$ARTIFACT_DIR/environment.txt"

export HYPOTHESIS_PROFILE=recorded
uv run --python 3.12 --dev --frozen pytest \
	src/documents/tests/search/test_unicode_normalization.py \
	-k TestTheNormalizer -n 0 -v --hypothesis-seed=20261008 \
	--hypothesis-show-statistics --cov=documents.search._query \
	--cov-branch --cov-report=term-missing \
	2>&1 | tee "$LOG_FILE"

uv run --python 3.12 --dev --frozen coverage json -o "$COVERAGE_JSON"

uv run --python 3.12 --dev --frozen python - \
	"$LOG_FILE" "$COVERAGE_JSON" "$VERIFICATION_JSON" <<'PY'
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

log_path, coverage_path, verification_path = map(Path, sys.argv[1:])
log = log_path.read_text(encoding="utf-8", errors="replace")

properties = (
    "test_normalization_is_idempotent",
    "test_normalization_matches_nfc_oracle",
    "test_canonical_equivalents_normalize_equally",
)
statistics = {}
for name in properties:
    marker = f"test_unicode_normalization.py::TestTheNormalizer::{name}:"
    start = log.find(marker)
    if start < 0:
        raise SystemExit(f"Missing Hypothesis statistics for {name}")
    block = log[start : start + 1500]
    match = re.search(
        r"(\d+) passing, (\d+) failing, and (\d+) invalid test cases",
        block,
    )
    if match is None:
        raise SystemExit(f"Missing property counts for {name}")
    counts = tuple(map(int, match.groups()))
    if counts != (250, 0, 0):
        raise SystemExit(f"Unexpected counts for {name}: {counts}")
    statistics[name] = {
        "passing": counts[0],
        "failing": counts[1],
        "invalid": counts[2],
    }

if re.search(r"5 passed, 12 deselected in [0-9.]+s", log) is None:
    raise SystemExit("Focused session summary did not match the acceptance gate")

source_path = Path("src/documents/search/_query.py")
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source)
function = next(
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "normalize_search_text"
)
function_lines = set(range(function.lineno, function.end_lineno + 1))

coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
file_key = next(
    key
    for key in coverage["files"]
    if key.replace("\\", "/").endswith("documents/search/_query.py")
)
file_coverage = coverage["files"][file_key]
executed_lines = set(file_coverage["executed_lines"])
missing_lines = set(file_coverage["missing_lines"])
target_executable = (executed_lines | missing_lines) & function_lines
target_missing = missing_lines & function_lines
target_executed_branches = [
    branch
    for branch in file_coverage.get("executed_branches", [])
    if branch[0] in function_lines
]
target_missing_branches = [
    branch
    for branch in file_coverage.get("missing_branches", [])
    if branch[0] in function_lines
]

if len(target_executable) != 2 or target_missing:
    raise SystemExit(
        f"Target statement coverage mismatch: "
        f"{len(target_executable) - len(target_missing)}/"
        f"{len(target_executable)}",
    )
if target_executed_branches or target_missing_branches:
    raise SystemExit(
        "normalize_search_text unexpectedly contains measured control-flow branches",
    )

result = {
    "session": {"passed": 5, "deselected": 12},
    "properties": statistics,
    "target_coverage": {
        "executable_lines": len(target_executable),
        "missing_lines": len(target_missing),
        "executed_branches": len(target_executed_branches),
        "missing_branches": len(target_missing_branches),
    },
    "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
}
verification_path.write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(result, indent=2))
PY

echo "PBT-02 demo passed. Artifacts: $ARTIFACT_DIR"
