#!/usr/bin/env bash
set -euo pipefail

BASELINE="b29fec117053637428a935d43af16d9e1d65c1fb"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${PBT04_ARTIFACT_DIR:-$REPO_ROOT/.artifacts/pbt-04-cycle-4}"
LOG_FILE="$ARTIFACT_DIR/pbt-04-run.log"
PROPERTIES_XML="$ARTIFACT_DIR/properties.xml"
COVERAGE_JSON="$ARTIFACT_DIR/coverage.json"
VERIFICATION_JSON="$ARTIFACT_DIR/verification.json"

cd "$REPO_ROOT"

case "$(uname -s)" in
	Linux | Darwin) ;;
	*)
		echo "PBT-04 clean-machine demo requires Linux, macOS, or WSL2." >&2
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
	echo "HEAD is not descended from the pinned PBT-04 baseline." >&2
	exit 2
fi

tracked_paths=(
	"src/documents/parsers.py"
	"src/documents/tests/test_parsers.py"
)

if ! git diff --quiet "$BASELINE" HEAD -- "${tracked_paths[@]}"; then
	echo "PBT-04 source or tests changed after the pinned baseline." >&2
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
	echo "python=$(uv run --python 3.12 --group testing --frozen python --version 2>&1)"
} >"$ARTIFACT_DIR/environment.txt"

export HYPOTHESIS_PROFILE=recorded
uv run --python 3.12 --group testing --frozen pytest \
	src/documents/tests/test_parsers.py \
	-k TestMimeExtensionProperties -n 0 -v \
	--hypothesis-seed=13 --hypothesis-show-statistics \
	--cov=documents.parsers --cov-branch --cov-report=term-missing \
	--junitxml="$PROPERTIES_XML" \
	2>&1 | tee "$LOG_FILE"

uv run --python 3.12 --group testing --frozen coverage json -o "$COVERAGE_JSON"

uv run --python 3.12 --group testing --frozen python - \
	"$LOG_FILE" "$COVERAGE_JSON" "$VERIFICATION_JSON" <<'PY'
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

log_path, coverage_path, verification_path = map(Path, sys.argv[1:])
log = log_path.read_text(encoding="utf-8", errors="replace")

finite_properties = (
    "test_supported_mime_has_valid_extension[False]",
    "test_supported_mime_has_valid_extension[True]",
)
full_properties = (
    "test_extension_membership_is_case_insensitive",
    "test_registry_extensions_include_defaults_and_aliases",
)
statistics = {}
for name in (*finite_properties, *full_properties):
    marker = f"test_parsers.py::TestMimeExtensionProperties::{name}:"
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
    if name in finite_properties:
        if passing < 1 or failing != 0:
            raise SystemExit(
                f"Unexpected finite property counts for {name}: "
                f"{(passing, failing, invalid)}",
            )
    elif passing != 250 or failing != 0:
        raise SystemExit(
            f"Unexpected counts for {name}: {(passing, failing, invalid)}",
        )
    statistics[name] = {
        "passing": passing,
        "failing": failing,
        "invalid": invalid,
    }

required_tests = (
    "test_all_builtin_mappings[False]",
    "test_all_builtin_mappings[True]",
    "test_fallback_does_not_imply_mime_support",
    "test_parser_without_mapping_uses_mimetypes_fallback",
)
for name in required_tests:
    if f"TestMimeExtensionProperties::{name} PASSED" not in log:
        raise SystemExit(f"Missing required deterministic pass for {name}")

if re.search(r"13 passed, 14 deselected in [0-9.]+s", log) is None:
    raise SystemExit("Focused session summary did not match the acceptance gate")

expected_targets = {
    "is_mime_type_supported": (2, 0),
    "get_default_file_extension": (8, 4),
    "is_file_ext_supported": (4, 2),
    "get_supported_file_extensions": (7, 4),
}

source_path = Path("src/documents/parsers.py")
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source)
functions = {
    node.name: node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in expected_targets
}
if set(functions) != set(expected_targets):
    raise SystemExit(f"Missing target helpers in {source_path}: {sorted(functions)}")

coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
file_key = next(
    key
    for key in coverage["files"]
    if key.replace("\\", "/").endswith("documents/parsers.py")
)
file_coverage = coverage["files"][file_key]
executed_lines = set(file_coverage["executed_lines"])
missing_lines = set(file_coverage["missing_lines"])
executed_branches = file_coverage.get("executed_branches", [])
missing_branches = file_coverage.get("missing_branches", [])

helper_coverage = {}
total_lines = 0
total_missing_lines = 0
total_branches = 0
total_missing_branches = 0

for name, (expected_lines, expected_branches) in expected_targets.items():
    node = functions[name]
    function_lines = set(range(node.lineno, node.end_lineno + 1))
    target_executable = (executed_lines | missing_lines) & function_lines
    target_missing = missing_lines & function_lines
    target_executed_branches = [
        branch for branch in executed_branches if branch[0] in function_lines
    ]
    target_missing_branches = [
        branch for branch in missing_branches if branch[0] in function_lines
    ]
    if len(target_executable) != expected_lines or target_missing:
        raise SystemExit(
            f"Target statement coverage mismatch for {name}: "
            f"{len(target_executable) - len(target_missing)}/{len(target_executable)}",
        )
    if len(target_executed_branches) != expected_branches or target_missing_branches:
        raise SystemExit(
            f"Target branch coverage mismatch for {name}: "
            f"{len(target_executed_branches)} executed, "
            f"{len(target_missing_branches)} missing",
        )
    helper_coverage[name] = {
        "executable_lines": len(target_executable),
        "missing_lines": len(target_missing),
        "executed_branches": len(target_executed_branches),
        "missing_branches": len(target_missing_branches),
    }
    total_lines += len(target_executable)
    total_missing_lines += len(target_missing)
    total_branches += len(target_executed_branches)
    total_missing_branches += len(target_missing_branches)

result = {
    "session": {"passed": 13, "deselected": 14, "failed": 0},
    "properties": statistics,
    "target_helpers": helper_coverage,
    "target_coverage": {
        "executable_lines": total_lines,
        "missing_lines": total_missing_lines,
        "executed_branches": total_branches,
        "missing_branches": total_missing_branches,
    },
    "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
}
verification_path.write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(result, indent=2))
PY

echo "PBT-04 demo passed. Artifacts: $ARTIFACT_DIR"
