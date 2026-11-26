# PBT-01 Cycle 3: Execution Evidence and RCA

## Scope

- Issue: [#35](https://github.com/0Yaam/paperless-ngx/issues/35)
- Target: `paperless.parsers.utils.post_process_text`
- Base commit: `cb087a99b78f867d320b82b132fe192d6a8d4a05`
- Profile: `recorded` (`max_examples=250`, no deadline)
- Seed: `20261008`

The recorded profile is selected through `HYPOTHESIS_PROFILE=recorded`. The CI job
runs without xdist so the seed, statistics, and log order remain reproducible.

## Reproduction

```bash
uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/paperless/tests/test_parser_utils.py -k TestPostProcessText -n 0 -v \
  --hypothesis-seed=20261008 --hypothesis-show-statistics \
  --cov=paperless.parsers.utils --cov-branch --cov-report=term-missing
```

Coursework CI uploads the complete stdout as the `pbt-01-evidence` artifact. The
artifact contains `.artifacts/pbt-01-run.log`.

## Recorded Results

Focused validation used Python 3.12.15, pytest 9.2.0, Hypothesis 6.170.17, and
coverage.py 7.17.5 on Windows. CI repeats the same property profile and seed on
Linux with the locked dependencies.

| Property                                  | Passing | Failing | Invalid | Generate time |
| ----------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_is_idempotent`                      |     250 |       0 |       0 |        0.12 s |
| `test_removes_nul_characters`             |     250 |       0 |       0 |        0.13 s |
| `test_preserves_internal_line_boundaries` |     250 |       0 |       0 |        0.09 s |

The session completed with 9 tests passed and 15 deselected in 0.58 seconds.
This includes 750 generated examples, the explicit historical counterexample,
and six deterministic regression cases. No current counterexample was found.

Coverage.py recorded every executable line in `post_process_text` (9/9) and both
branches of its input guard (2/2). The complete `paperless.parsers.utils` module
was 24% covered because the focused suite intentionally excludes unrelated PDF
helpers.

## Counterexample and RCA

Cycle 1 found a real idempotence defect and Hypothesis minimized it to:

```python
source = "a\0\0b"
```

The old order collapsed whitespace before replacing NUL bytes. The first call
therefore changed the two NUL bytes into two adjacent spaces and returned
`"a  b"`; the second call collapsed those spaces and returned `"a b"`.

Commit `d3d126321e8e47d14719da0f5decf4b785348553` fixed the root cause by removing
NUL bytes before whitespace normalization. The explicit example remains in the
suite as a regression guard. The recorded Cycle 3 run confirms the fix across
250 generated idempotence inputs and the minimized counterexample.

## Assessment

- Idempotence, NUL removal, and preservation of internal line boundaries all
  passed with zero failures and zero invalid generated examples.
- The target function has complete statement and branch coverage in this suite.
- Residual risk is limited to Unicode categories and input sizes outside the
  bounded Hypothesis strategies; the `stress` profile raises each property to
  500 examples when deeper sampling is required.
