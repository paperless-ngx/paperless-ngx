# PBT-05 Cycle 3: Execution Evidence and RCA

## Scope

- Issue: [#39](https://github.com/0Yaam/paperless-ngx/issues/39)
- Target: `paperless.parsers.registry.ParserRegistry.get_parser_for_file`
- Original implementation commit: `e6844da73e2708b887cb243dbce12fad916aa593`
- Profile: `recorded` (`max_examples=250`, no deadline)
- Seed: `20261008`

The two clean PBT-05 commits contain only the test, workflow, and evidence
changes. The unrelated backend-install and release-drafter commits from the
original PR are excluded.

## Reproduction

```bash
uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --dev --frozen pytest \
  src/paperless/tests/test_parser_selection_pbt.py \
  -k TestPbtParserSelection -n 0 -v --hypothesis-seed=20261008 \
  --hypothesis-show-statistics --cov=paperless.parsers.registry \
  --cov-branch --cov-report=term-missing
```

Coursework CI uploads the full `.artifacts/pbt-05-run.log` in the
`pbt-05-evidence` artifact.

## Recorded Results

The original PR's Linux artifact from run `45539433977` used Python 3.12.16,
pytest 9.1.1, Hypothesis 6.168.5, and coverage.py 7.1.0. It is the source for
the following unedited counts:

| Property                                                                | Passing | Failing | Invalid | Generate time |
| ----------------------------------------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_highest_scoring_eligible_parser_wins`                             |     250 |       0 |      23 |        1.34 s |
| `test_external_parser_wins_tie_with_builtin`                            |     250 |       0 |       0 |        0.51 s |
| `test_remote_parsers_excluded_when_not_allowed`                         |     250 |       0 |      85 |        0.75 s |
| `test_none_returned_when_registry_is_empty`                             |     250 |       0 |       0 |        0.50 s |
| `test_none_returned_when_mime_unsupported_despite_valid_scores`         |     250 |       0 |      77 |        0.83 s |
| `test_none_returned_when_matching_parsers_decline_with_none_score`      |     250 |       0 |      24 |        0.73 s |
| `test_none_returned_when_only_remote_parsers_available_and_not_allowed` |     250 |       0 |      33 |        0.69 s |

The Linux session completed with 7 tests passed in 32.16 seconds. All seven
properties reached 250 passing examples and produced no counterexample.

A second focused run of the clean branch on Python 3.12.15, pytest 9.2.0, and
Hypothesis 6.170.17 also passed all 1,750 generated examples in 2.70 seconds.
Coverage.py executed all 17 executable lines and all 12 branches in
`get_parser_for_file`. The full registry module was 44% covered because parser
discovery and registration are outside the target.

## No-Failure Evidence and RCA

The suite validates these independent selection rules:

1. The highest eligible score wins, including zero and negative scores.
2. External parsers win equal-score ties because they are evaluated first.
3. Parsers using remote services are excluded unless `allow_remote=True`.
4. Empty registries, unsupported MIME types, and parsers returning `None`
   produce no selection.

No production defect was found. The implementation keeps `None` distinct from
integer scores, evaluates external parsers before built-ins, and updates the
winner only for a strictly greater score. Those three decisions explain the
observed tie, negative-score, and decline behavior.

The explicit examples preserve useful minimized mutation checks. Changing the
comparison from `>` to `>=` makes a built-in parser incorrectly replace an
equal-score external parser. Removing the remote-service guard selects the
single explicit `cloud_ocr` parser while `allow_remote=False`. These are
detection examples, not production defects.

## Assessment

- All 1,750 valid generated examples passed in both the Linux artifact and the
  clean focused run.
- The target function has complete statement and branch coverage.
- The invalid counts are rejected generated combinations that do not satisfy
  each property's preconditions; they are not test failures.
- Plugin methods that raise exceptions remain a separate integration risk and
  are outside the selection contract tested here.
