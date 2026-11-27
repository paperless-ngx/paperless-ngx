# PBT-02 Cycle 4: Final Report and Demo

## A. Objective and Scope

- Issue: [#49](https://github.com/0Yaam/paperless-ngx/issues/49)
- Owner: [@elgthinhnguyen](https://github.com/elgthinhnguyen)
- Peer reviewer: [@0Yaam](https://github.com/0Yaam)
- Target: [`documents.search._query.normalize_search_text`](../src/documents/search/_query.py#L62)
- Pinned code baseline: `b29fec117053637428a935d43af16d9e1d65c1fb`
- Cycle 3 source evidence: [PBT-02 execution evidence and RCA](pbt-02-cycle-3-evidence.md)

This report closes the reporting and demo work for PBT-02. It covers the pure
Unicode normalization function and the properties that define its contract.
Search parsing, indexing, database models, and field integration have separate
tests and are outside the focused command.

The baseline contains the merged PBT-02 implementation and evidence. The Cycle 4
demo script refuses to run if the target or its property suite has changed since
that baseline without a corresponding report update.

## B. Target Contract

`normalize_search_text` returns the NFC form of its input. Both indexed values and
queries use the same normalization so canonically equivalent spellings generate
the same codepoint sequence before bigram analysis.

NFC is deliberate. The target does not use NFKC compatibility folding. For
example, halfwidth katakana `"\uff8a\uff9f\uff9d"` remains halfwidth under NFC;
changing that spelling would be a search-product decision rather than an
encoding normalization.

The target contract is:

1. Normalization is idempotent.
2. The result equals Python's `unicodedata.normalize("NFC", text)` oracle.
3. Canonically equivalent NFC and NFD inputs normalize to the same result.

## C. Property Model

The suite binds a named `recorded` profile with 250 examples and no deadline in
[`test_unicode_normalization.py`](../src/documents/tests/search/test_unicode_normalization.py#L38).

| ID         | Property              | Strategy                                                | Oracle                                          |
| ---------- | --------------------- | ------------------------------------------------------- | ----------------------------------------------- |
| PBT02-INV1 | Idempotence           | Arbitrary Unicode text                                  | `normalize(normalize(x)) == normalize(x)`       |
| PBT02-INV2 | NFC oracle            | Arbitrary Unicode text plus explicit `"\u304b\u3099"`   | Result equals `unicodedata.normalize("NFC", x)` |
| PBT02-INV3 | Canonical equivalence | Arbitrary Unicode text prefixed with a precomposed kana | NFC and NFD forms normalize equally             |

Two deterministic examples additionally prove that decomposed kana composes and
that halfwidth katakana remains unchanged.

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
  src/documents/tests/search/test_unicode_normalization.py \
  -k TestTheNormalizer -n 0 -v --hypothesis-seed=20261008 \
  --hypothesis-show-statistics --cov=documents.search._query \
  --cov-branch --cov-report=term-missing
```

Expected acceptance signals:

- `5 passed, 12 deselected`
- Exactly three property summaries with `250 passing`
- Zero failing and zero invalid examples for all three properties
- A coverage report with branch measurement enabled

### Final Demo Script

On the final `dev` branch:

```bash
bash scripts/demo-pbt-02.sh
```

The script verifies baseline ancestry and target drift, performs the locked
dependency sync, runs the exact focused command, checks the property statistics,
checks target-only coverage, and writes reproducible artifacts under
`.artifacts/pbt-02-cycle-4/`. Coursework CI invokes the same script on a clean
Ubuntu runner and uploads the generated directory.

## E. Results and Metrics

The authoritative Linux record is
[Coursework CI run 45760498459](https://github.com/0Yaam/paperless-ngx/actions/runs/45760498459),
job `PBT-02 Unicode search normalization`, artifact `pbt-02-evidence`.

Environment: Python 3.12.16, pytest 9.1.1, and Hypothesis 6.168.5.

| Property                                       | Passing | Failing | Invalid | Generate time |
| ---------------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_normalization_is_idempotent`             |     250 |       0 |       0 |        0.26 s |
| `test_normalization_matches_nfc_oracle`        |     250 |       0 |       0 |        0.44 s |
| `test_canonical_equivalents_normalize_equally` |     250 |       0 |       0 |        0.26 s |

The full focused session completed with 5 passed and 12 deselected in 34.20
seconds. Runtime is informational and varies by runner; pass counts and coverage
are the acceptance criteria.

The whole `documents.search._query` module report was 227 statements, 163
missed, 82 branches, 0 partial branches, and 21% coverage. The module contains
the complete query parser. Mapping coverage data to `normalize_search_text`
gives the relevant target result: 2/2 executable lines, no control-flow branches,
and no target misses.

The Hypothesis session header may display the plugin's automatic `ci` profile.
The PBT-02 decorators bind the suite-specific settings selected by
`HYPOTHESIS_PROFILE=recorded`; the three 250-example summaries are the
authoritative proof that the recorded settings were applied.

## F. No-Failure Analysis

No production counterexample was found across 750 generated examples. The
implementation delegates directly to the standard library NFC operation, and
all generated inputs matched that oracle.

The explicit decomposed-kana example still demonstrates detection strength. An
identity-function mutation would return `"\u304b\u3099"` instead of the NFC
result `"\u304c"` and fail `test_normalization_matches_nfc_oracle`. This is
mutation evidence, not a production defect or RCA.

## G. Evaluation and Limitations

- The three properties completely cover the two executable target lines.
- The target has no control-flow branches.
- Generated inputs are bounded; the `stress` profile raises each property to 500
  examples when deeper sampling is required.
- The focused command excludes
  [`TestEitherSpellingFindsEither`](../src/documents/tests/search/test_unicode_normalization.py#L115)
  and
  [`TestEverySearchableFieldIsNormalized`](../src/documents/tests/search/test_unicode_normalization.py#L157).
  Those integration tests separately cover query/index and searchable-field
  behavior.
- The suite proves canonical Unicode normalization, not compatibility folding,
  language-aware equivalence, tokenization, ranking, or database behavior.
- CI artifacts have a retention period. The committed Cycle 3 evidence and this
  report preserve the durable result after artifact expiry.

## H. Demo and Peer-Review Handoff

### Three-to-Five-Minute Demo

1. Show the pinned baseline and the no-drift check printed by
   `scripts/demo-pbt-02.sh`.
2. Explain NFC versus NFKC using `"\u304b\u3099"` and
   `"\uff8a\uff9f\uff9d"`.
3. Run the script and point out the three 250-example property summaries.
4. Show `verification.json` with 2/2 target lines and zero missing branches.
5. If the local runner is unavailable, open the CI run above and download
   `pbt-02-evidence`.

### Reviewer Checklist

- [ ] Claims match committed source, tests, and the linked CI artifact.
- [ ] The baseline command works from a fresh checkout.
- [ ] The demo script fails on target drift or missing acceptance signals.
- [ ] Module coverage is not presented as target-only coverage.
- [ ] NFC is not described as NFKC compatibility folding.
- [ ] Scope and residual risks are explicit.
- [ ] Review findings are resolved before approval.

Peer approval is recorded in the pull request linked to issue #49; this report
does not predeclare the review result.

## Traceability

| Claim                                        | Durable evidence                                                                                                  |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Target NFC contract                          | [`_query.py`](../src/documents/search/_query.py#L62)                                                              |
| Property definitions and explicit example    | [`test_unicode_normalization.py`](../src/documents/tests/search/test_unicode_normalization.py#L63)                |
| Query-side normalization                     | [`_backend.py`](../src/documents/search/_backend.py#L457)                                                         |
| Indexed content/title normalization          | [`_backend.py`](../src/documents/search/_backend.py#L509)                                                         |
| Filename and related searchable fields       | [`_backend.py`](../src/documents/search/_backend.py#L533)                                                         |
| Deterministic CI wrapper and artifact upload | [`coursework-ci.yml`](../.github/workflows/coursework-ci.yml#L102), [`demo-pbt-02.sh`](../scripts/demo-pbt-02.sh) |
| Recorded statistics and no-failure analysis  | [Cycle 3 evidence](pbt-02-cycle-3-evidence.md)                                                                    |
| Automated final-demo verification            | [`demo-pbt-02.sh`](../scripts/demo-pbt-02.sh)                                                                     |
