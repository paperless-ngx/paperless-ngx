# PBT-01 Cycle 4: Final Report and Demo

## A. Objective and Scope

- Issue: [#48](https://github.com/0Yaam/paperless-ngx/issues/48)
- Owner: [@0Yaam](https://github.com/0Yaam)
- Peer reviewer: [@elgthinhnguyen](https://github.com/elgthinhnguyen)
- Target: [`paperless.parsers.utils.post_process_text`](../src/paperless/parsers/utils.py#L114)
- Pinned code baseline: `b29fec117053637428a935d43af16d9e1d65c1fb`
- Cycle 3 source evidence: [PBT-01 execution evidence and RCA](pbt-01-cycle-3-evidence.md)

This report closes the reporting and demo work for PBT-01. It covers the
normalization function only; PDF extraction, parser lifecycle, database writes,
and end-to-end OCR are outside this suite.

The baseline contains the merged PBT-01 implementation and evidence. The Cycle 4
demo script refuses to run if the target or its property suite has changed since
that baseline without a corresponding report update.

## B. Target Contract

`post_process_text` normalizes extracted PDF or OCR text:

1. `None`, an empty string, or a whitespace-only result becomes `None`.
2. NUL bytes are replaced before whitespace collapsing.
3. Horizontal whitespace is collapsed without collapsing line boundaries.
4. Leading whitespace after a line break and trailing padding are removed.
5. Applying the function twice produces the same result as applying it once.

The order in step 2 is essential. Replacing NUL bytes after collapsing whitespace
made the old implementation non-idempotent.

## C. Property Model

The suite binds a named `recorded` profile with 250 examples and no deadline in
[`test_parser_utils.py`](../src/paperless/tests/test_parser_utils.py#L25).

| ID         | Property               | Strategy                                                   | Oracle                                          |
| ---------- | ---------------------- | ---------------------------------------------------------- | ----------------------------------------------- |
| PBT01-INV1 | Idempotence            | `None` or arbitrary Unicode text, plus explicit `"a\0\0b"` | `normalize(normalize(x)) == normalize(x)`       |
| PBT01-INV2 | NUL removal            | Arbitrary Unicode prefix and suffix with an inserted NUL   | Result is `None` or contains no `"\0"`          |
| PBT01-INV3 | Stable line boundaries | NUL-free Unicode text wrapped by `"a\n"` and `"b"`         | The ordered CR/LF runs match the stripped input |

The properties are implemented in
[`TestPostProcessText`](../src/paperless/tests/test_parser_utils.py#L97), alongside
six deterministic examples for spaces, line boundaries, Unicode, `None`, empty
input, and layout-only padding.

## D. Clean-Machine Reproduction

### Prerequisites

- Linux, macOS, or WSL2
- Git
- `uv`
- Network access for the first dependency sync

The repository lock targets Linux and macOS. Native Windows is not an accepted
clean-machine environment for this demonstration; use WSL2 or GitHub Actions.

### Exact Baseline Run

```bash
git clone --branch dev https://github.com/0Yaam/paperless-ngx.git
cd paperless-ngx
git checkout b29fec117053637428a935d43af16d9e1d65c1fb

uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/paperless/tests/test_parser_utils.py -k TestPostProcessText -n 0 -v \
  --hypothesis-seed=20261008 --hypothesis-show-statistics \
  --cov=paperless.parsers.utils --cov-branch --cov-report=term-missing
```

Expected acceptance signals:

- `9 passed, 15 deselected`
- Exactly three property summaries with `250 passing`
- Zero failing and zero invalid examples for all three properties
- A coverage report with branch measurement enabled

### Final Demo Script

On the final `dev` branch:

```bash
bash scripts/demo-pbt-01.sh
```

The script verifies baseline ancestry and target drift, performs the locked
dependency sync, runs the exact focused command, checks the property statistics,
checks target-only statement and branch coverage, and writes reproducible
artifacts under `.artifacts/pbt-01-cycle-4/`. Coursework CI invokes the same
script on a clean Ubuntu runner and uploads the generated directory.

## E. Results and Metrics

The authoritative Linux record is
[Coursework CI run 45759270055](https://github.com/0Yaam/paperless-ngx/actions/runs/45759270055),
job `PBT-01 text normalization`, artifact `pbt-01-evidence`.

Environment: Python 3.12.16, pytest 9.1.1, and Hypothesis 6.168.5.

| Property                                  | Passing | Failing | Invalid | Generate time |
| ----------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_is_idempotent`                      |     250 |       0 |       0 |        0.20 s |
| `test_removes_nul_characters`             |     250 |       0 |       0 |        0.19 s |
| `test_preserves_internal_line_boundaries` |     250 |       0 |       0 |        0.28 s |

The full focused session completed with 9 passed and 15 deselected in 16.14
seconds. Runtime is informational and varies by runner; pass counts and coverage
are the acceptance criteria.

The whole `paperless.parsers.utils` module report was 102 statements, 76 missed,
16 branches, 0 partial branches, and 24% coverage. That module includes unrelated
PDF helpers. Mapping coverage data to `post_process_text` gives the relevant
target result: 9/9 executable lines and 2/2 branches, with no target misses.

The Hypothesis session header may display the plugin's automatic `ci` profile.
The PBT-01 decorators bind the suite-specific settings selected by
`HYPOTHESIS_PROFILE=recorded`; the three 250-example summaries are the
authoritative proof that the recorded settings were applied.

## F. Minimized Counterexample and RCA

Hypothesis reduced the historical idempotence failure to:

```python
source = "a\0\0b"
```

The old implementation collapsed whitespace first and replaced NUL bytes last:

```text
first call:  "a\0\0b" -> "a  b"
second call: "a  b"   -> "a b"
```

The root cause was ordering, not the regular expression itself. Commit
[`d3d126321`](https://github.com/0Yaam/paperless-ngx/commit/d3d126321e8e47d14719da0f5decf4b785348553)
moved NUL replacement before whitespace collapse. The first call now returns
`"a b"`, and the second call returns the same value. The explicit example remains
in the property suite as a permanent regression guard.

## G. Evaluation and Limitations

- No current counterexample was found across 750 generated examples.
- The three properties cover the target contract and all target branches.
- Generated inputs are bounded; the `stress` profile raises each property to 500
  examples when deeper sampling is required.
- The suite does not establish correctness of PDF extraction, OCR tools, parser
  orchestration, or database persistence.
- CI artifacts have a retention period. The committed Cycle 3 evidence and this
  report preserve the durable result after artifact expiry.

## H. Demo and Peer-Review Handoff

### Three-to-Five-Minute Demo

1. Show the pinned baseline and the no-drift check printed by
   `scripts/demo-pbt-01.sh`.
2. Explain the minimized `"a\0\0b"` example and the before/after ordering.
3. Run the script and point out the three 250-example property summaries.
4. Show the generated `verification.json` with 9/9 target lines and 2/2 target
   branches.
5. If the local runner is unavailable, open the CI run above and download
   `pbt-01-evidence`.

### Reviewer Checklist

- [ ] Claims match committed source, tests, and the linked CI artifact.
- [ ] The baseline command works from a fresh checkout.
- [ ] The demo script fails on target drift or missing acceptance signals.
- [ ] Module coverage is not presented as target-only coverage.
- [ ] Scope and residual risks are explicit.
- [ ] Review findings are resolved before approval.

Peer approval is recorded in the pull request linked to issue #48; this report
does not predeclare the review result.

## Traceability

| Claim                                            | Durable evidence                                                                                                 |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Target behavior and fix order                    | [`utils.py`](../src/paperless/parsers/utils.py#L114), commit `d3d126321`                                         |
| Property definitions and explicit counterexample | [`test_parser_utils.py`](../src/paperless/tests/test_parser_utils.py#L97)                                        |
| Deterministic CI wrapper and artifact upload     | [`coursework-ci.yml`](../.github/workflows/coursework-ci.yml#L73), [`demo-pbt-01.sh`](../scripts/demo-pbt-01.sh) |
| Recorded statistics and RCA                      | [Cycle 3 evidence](pbt-01-cycle-3-evidence.md)                                                                   |
| Automated final-demo verification                | [`demo-pbt-01.sh`](../scripts/demo-pbt-01.sh)                                                                    |
