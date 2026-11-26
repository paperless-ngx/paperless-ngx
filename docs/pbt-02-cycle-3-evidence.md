# PBT-02 Cycle 3: Execution Evidence and RCA

## Scope

- Issue: [#36](https://github.com/0Yaam/paperless-ngx/issues/36)
- Target: `documents.search._query.normalize_search_text`
- Base commit: `7683c9be6` (PBT-01 Cycle 3 stacked locally)
- Profile: `recorded` (`max_examples=250`, no deadline)
- Seed: `20261008`

The recorded profile is applied only to the PBT-02 properties. CI disables xdist
for this job so statistics and log ordering are deterministic.

## Reproduction

```bash
uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/documents/tests/search/test_unicode_normalization.py \
  -k TestTheNormalizer -n 0 -v --hypothesis-seed=20261008 \
  --hypothesis-show-statistics --cov=documents.search._query \
  --cov-branch --cov-report=term-missing
```

Coursework CI uploads `.artifacts/pbt-02-run.log` in the `pbt-02-evidence`
artifact.

## Recorded Results

Focused validation used Python 3.12.15, pytest 9.2.0, Hypothesis 6.170.17, and
coverage.py 7.17.5 on Windows. CI repeats the recorded profile against the
locked Linux environment.

| Property                                       | Passing | Failing | Invalid | Generate time |
| ---------------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_normalization_is_idempotent`             |     250 |       0 |       0 |        2.11 s |
| `test_normalization_matches_nfc_oracle`        |     250 |       0 |       0 |        0.27 s |
| `test_canonical_equivalents_normalize_equally` |     250 |       0 |       0 |        2.34 s |

The session completed with 5 tests passed and 12 deselected in 7.09 seconds.
It exercised 750 generated examples, one explicit decomposed-kana example, and
two deterministic regressions. No production counterexample was found.

Coverage.py executed both executable lines in `normalize_search_text` (2/2).
The function has no control-flow branches. The complete `_query` module was 1%
covered because parsing, field registration, and Tantivy integration are
outside this focused target.

## No-Failure Evidence and RCA

The strongest boundary example is the decomposed sequence:

```python
source = "か\u3099"
expected = "が"
```

The recorded run confirms that composed and decomposed spellings normalize to
the same NFC value, normalization is idempotent, and the result matches Python's
Unicode NFC oracle for every generated input.

No defect is present in the target. Its implementation delegates directly to
`unicodedata.normalize("NFC", text)`, so the relevant failure mode would be
removing or changing the NFC form. As a mutation check, replacing the function
with an identity operation makes the explicit example fail with decomposed
`"か\u3099"` instead of composed `"が"`. This is detection evidence for the
suite, not a production defect.

## Assessment

- All three properties passed with no failures or rejected generated examples.
- The focused suite covers every executable line in the target.
- Residual risk lies in search indexing and query integration, which are
  covered by the separate `TestEitherSpellingFindsEither` and
  `TestEverySearchableFieldIsNormalized` integration tests.
