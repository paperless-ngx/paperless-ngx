#!/usr/bin/env bash
set -euo pipefail

BASELINE="b29fec117053637428a935d43af16d9e1d65c1fb"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${PBT05_ARTIFACT_DIR:-$REPO_ROOT/.artifacts/pbt-05-cycle-4}"
LOG_FILE="$ARTIFACT_DIR/pbt-05-run.log"
COVERAGE_JSON="$ARTIFACT_DIR/coverage.json"
VERIFICATION_JSON="$ARTIFACT_DIR/verification.json"

cd "$REPO_ROOT"

case "$(uname -s)" in
	Linux | Darwin) ;;
	*)
		echo "PBT-05 clean-machine demo requires Linux, macOS, or WSL2." >&2
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
	echo "HEAD is not descended from the pinned PBT-05 baseline." >&2
	exit 2
fi

tracked_paths=(
	"src/paperless/parsers/registry.py"
	"src/paperless/tests/test_parser_selection_pbt.py"
)

if ! git diff --quiet "$BASELINE" HEAD -- "${tracked_paths[@]}"; then
	echo "PBT-05 source or tests changed after the pinned baseline." >&2
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
	src/paperless/tests/test_parser_selection_pbt.py \
	-k TestPbtParserSelection -n 0 -v \
	--hypothesis-seed=20261008 --hypothesis-show-statistics \
	--cov=paperless.parsers.registry --cov-branch --cov-report=term-missing \
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
    "test_highest_scoring_eligible_parser_wins",
    "test_external_parser_wins_tie_with_builtin",
    "test_remote_parsers_excluded_when_not_allowed",
    "test_none_returned_when_registry_is_empty",
    "test_none_returned_when_mime_unsupported_despite_valid_scores",
    "test_none_returned_when_matching_parsers_decline_with_none_score",
    "test_none_returned_when_only_remote_parsers_available_and_not_allowed",
)
statistics = {}
for name in properties:
    marker = f"test_parser_selection_pbt.py::TestPbtParserSelection::{name}:"
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
    passing, failing, invalid = map(int, match.groups())
    if passing != 250 or failing != 0:
        raise SystemExit(
            f"Unexpected counts for {name}: {(passing, failing, invalid)}",
        )
    statistics[name] = {
        "passing": passing,
        "failing": failing,
        "invalid": invalid,
    }

if re.search(r"7 passed in [0-9.]+s", log) is None:
    raise SystemExit("Focused session summary did not match the acceptance gate")

source_path = Path("src/paperless/parsers/registry.py")
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source)
registry_cls = next(
    node
    for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "ParserRegistry"
)
function = next(
    node
    for node in registry_cls.body
    if isinstance(node, ast.FunctionDef) and node.name == "get_parser_for_file"
)
function_lines = set(range(function.lineno, function.end_lineno + 1))

coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
file_key = next(
    key
    for key in coverage["files"]
    if key.replace("\\", "/").endswith("paperless/parsers/registry.py")
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

if len(target_executable) != 17 or target_missing:
    raise SystemExit(
        f"Target statement coverage mismatch: "
        f"{len(target_executable) - len(target_missing)}/"
        f"{len(target_executable)}",
    )
if len(target_executed_branches) != 12 or target_missing_branches:
    raise SystemExit(
        f"Target branch coverage mismatch: "
        f"{len(target_executed_branches)} executed, "
        f"{len(target_missing_branches)} missing",
    )

result = {
    "session": {"passed": 7, "failed": 0},
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

echo "PBT-05 demo passed. Artifacts: $ARTIFACT_DIR"
