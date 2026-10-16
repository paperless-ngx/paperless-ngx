# Rust fuzzy matching

`document_fuzzy_match` uses the compiled `paperless_fuzzy_native` extension for
both normalization and similarity. Database queries, IDs, result grouping,
command options, URLs, confirmation, and deletion remain in Python. There is no
Python scoring fallback. No database or document migration is needed.

## Linux installation

The supported application Python range is 3.11–3.14. The extension uses PyO3's
Python 3.11 stable ABI, so a wheel can run on all those versions on a compatible
Linux architecture and glibc. Local development here is pinned to Python
3.12.13; the Docker image targets Python 3.14. Rust 1.89.0 is specified in
`rust-toolchain.toml`; Rust dependencies are fixed by `native/fuzzy/Cargo.lock`.
The build backend is Maturin 1.10.2. Install a C linker/build tools and rustup
before syncing dependencies (for example, `build-essential` on Debian/Ubuntu).
Install rustup using its [official installer](https://rustup.rs/) if it is absent.

From the repository root:

```shell
python -m pip install --user uv==0.12.23
rustup toolchain install 1.89.0 --profile minimal --component rustfmt --component clippy
uv python install 3.12.13
uv sync --frozen --python 3.12.13 --group testing
uv run --no-sync python -c "import paperless_fuzzy_native as f; print(f.process_and_ratio('abc', 'abd', 0))"
```

The final command prints approximately `66.66666666666667`.
`uv sync` builds and installs the local path dependency automatically. An existing
environment can rebuild it with `uv sync --frozen --reinstall-package
paperless-fuzzy-native`. Cargo and Python source changes invalidate its build
cache. Without uv, build a release wheel explicitly:

```shell
python -m pip install maturin==1.10.2
python -m maturin build --release --locked --manifest-path native/fuzzy/Cargo.toml --out dist
python -m pip install dist/paperless_fuzzy_native-*.whl
```

The Dockerfile has a separate Rust compilation stage, then installs its wheel with
the application's Python dependencies. Rust and Cargo are not required in the runtime image.
The Debian-built wheel requires glibc 2.34+; build locally rather than reusing that
wheel on older Linux distributions. Cross-architecture installations need a wheel
built for that architecture. Standard container builds select the target platform.

## Compatibility and Unicode

The oracle is RapidFuzz **3.14.6**, as used at reference commit
`d7a98944001b88567377e3e5bc9a7f4d3d3e1f2b`. The original path called
`rapidfuzz.utils.default_process` then `rapidfuzz.fuzz.ratio` with the score cutoff.
The Rust path implements the same preprocessing and uses Rust RapidFuzz 0.5.0
over Unicode scalar values, returning scores on the same 0–100 scale.

Do not substitute Rust/Python's current `is_alphanumeric`/lowercasing tables:
RapidFuzz's C++ oracle freezes a different Unicode table and uses single-character
lowercasing, not casefolding or context-sensitive lowercase. A checked-in generated
range table reproduces that oracle, independently of the host Python/Rust Unicode
version. Non-alphanumeric characters become spaces; only outer spaces are trimmed.
The generated file records the oracle version and mapping SHA-256.

To regenerate after an explicitly reviewed compatibility-reference change:

```shell
uv run --no-sync python scripts/generate_fuzzy_normalization.py
cargo fmt --manifest-path native/fuzzy/Cargo.toml
uv sync --frozen --reinstall-package paperless-fuzzy-native
```

The generator refuses a different RapidFuzz version. Tests compare every Unicode
scalar in blocks, curated and seeded input pairs, long text, and exact/adjacent
floating-point cutoff values (score tolerance `1e-6`, identical threshold decisions).

## Failure and deletion safety

A missing library, load failure, or incompatible native API gives an actionable
`CommandError` with the reinstall command, before document processing or deletion
confirmation. Native runtime errors become controlled Python/command errors.
Rust panics are caught at the binding boundary, not propagated across the FFI.
Out-of-memory/process kills are not recoverable panic exceptions.

All comparisons finish before any deletion starts. A worker failure aborts the
command without a prompt or partial deletion. Cancellation, the original selection
of a matched pair's second document, and the backup warning are unchanged.
The command supports Linux multiprocessing `fork`, `spawn`, and `forkserver`.

## Validation

Run the compatibility tests and existing command regressions:

```shell
uv run --no-sync pytest src/documents/tests/test_fuzzy_native.py src/documents/tests/test_management_fuzzy.py
cargo fmt --check --manifest-path native/fuzzy/Cargo.toml
export PYO3_PYTHON="$PWD/.venv/bin/python"
export LD_LIBRARY_PATH="$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
cargo test --locked --manifest-path native/fuzzy/Cargo.toml
cargo clippy --locked --manifest-path native/fuzzy/Cargo.toml -- -D warnings
```

Rust unit tests link to Python, so managed Python installs may need the displayed
library path. The extension itself does not need that setting. Backend CI includes
the native source paths, installs the pinned toolchain, and runs Rust checks as
well as Python tests on 3.11–3.14.

Execution tracing is covered by tests asserting the loaded scorer is a compiled
extension and patching Python RapidFuzz preprocessing/scoring to raise while the
command worker still succeeds. Deletion tests inject missing/incompatible libraries
and worker failures and assert no document is deleted or confirmation requested.

## Synthetic runtime and memory comparison

```shell
uv run --no-sync python scripts/benchmark_fuzzy.py
uv run --no-sync python scripts/benchmark_fuzzy.py --documents 24 --length 16384
```

Both engines receive the same deterministic synthetic documents (seed 4004), with
Unicode/punctuation and mutated near-duplicates, every unordered pair, and cutoff 85. Each repeat starts a fresh subprocess per engine, warms one call, then times
normalization plus scoring for all pairs. JSON output records input SHA-256,
versions, every run, elapsed time, process peak RSS in KiB, match count and score
sum. The script verifies equal inputs and results. RSS includes interpreter,
imports, synthetic inputs and results, not just the matching algorithm; startup
and document generation are excluded from elapsed time. This is a single-worker
kernel comparison, not database/CLI or multiprocessing throughput.

Measured locally on Linux x86_64, glibc 2.35, CPython 3.12.13, release Rust build,
three repeats per engine:

| Documents × characters | Pairs | Matches | Reference median (s) | Rust median (s) | Reference RSS (KiB) | Rust RSS (KiB) |
| ---------------------- | ----- | ------- | -------------------- | --------------- | ------------------- | -------------- |
| 64 × 4096              | 2016  | 861     | 0.5450               | 0.7053          | 23936–24064         | 19948–19952    |
| 24 × 16384             | 276   | 120     | 0.8813               | 0.9323          | 25600               | 21448–21452    |

Rust was approximately **29% slower** and **6% slower** respectively, with about
4 MiB lower total process peak RSS on these inputs. No speed improvement is claimed.
Shared-host timing varies; rerun the script for deployment-specific measurements.
