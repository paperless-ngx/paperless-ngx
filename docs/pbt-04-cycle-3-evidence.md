# PBT-04 Cycle 3: Execution Evidence and RCA

## Scope

- Issue: [#38](https://github.com/0Yaam/paperless-ngx/issues/38)
- Target: MIME and extension helpers in `documents.parsers`
- Base commit: `c87a8b17f` (PBT-01 and PBT-02 Cycle 3 stacked locally)
- Profile: `recorded` (`max_examples=250`, no deadline)
- Seed: `13`

The CI job preserves the suite's original seed and runs without xdist. It
records the environment, property output, JUnit results, regression output, and
coverage in the `pbt-04-evidence` artifact.

## Reproduction

```bash
uv sync --python 3.12 --group testing --frozen
HYPOTHESIS_PROFILE=recorded uv run --python 3.12 --group testing --frozen \
  pytest src/documents/tests/test_parsers.py \
  -k TestMimeExtensionProperties -n 0 -v --hypothesis-seed=13 \
  --hypothesis-show-statistics --cov=documents.parsers --cov-branch \
  --cov-report=term-missing
```

## Recorded Results

Focused validation used Python 3.12.15, pytest 9.2.0, Hypothesis 6.170.17, and
coverage.py 7.17.5 on Windows. It exercised the production helper functions
with an isolated representative parser registry; CI repeats the run with the
real built-in registry and locked Linux dependencies.

| Property                                                | Passing | Failing | Invalid | Generate time |
| ------------------------------------------------------- | ------: | ------: | ------: | ------------: |
| `test_supported_mime_has_valid_extension[False]`        |       7 |       0 |       0 |        0.06 s |
| `test_supported_mime_has_valid_extension[True]`         |      11 |       0 |       0 |        0.01 s |
| `test_extension_membership_is_case_insensitive`         |     250 |       0 |      11 |        0.38 s |
| `test_registry_extensions_include_defaults_and_aliases` |     250 |       0 |      29 |        1.45 s |

The finite supported-MIME strategies stopped after exhausting their available
values; the two larger generated domains reached all 250 recorded examples.
The session completed with 13 tests passed and 14 deselected in 2.13 seconds.
No production counterexample was found.

The four target helpers have complete focused coverage:

| Helper                          | Executable lines | Missing lines | Covered branches | Missing branches |
| ------------------------------- | ---------------: | ------------: | ---------------: | ---------------: |
| `is_mime_type_supported`        |                2 |             0 |                0 |                0 |
| `get_default_file_extension`    |                8 |             0 |                4 |                0 |
| `is_file_ext_supported`         |                4 |             0 |                2 |                0 |
| `get_supported_file_extensions` |                7 |             0 |                4 |                0 |

The complete `documents.parsers` module was 45% covered because document
conversion and subprocess helpers are outside this suite. Cycle 3 added
`test_parser_without_mapping_uses_mimetypes_fallback` to close the one
previously untested defensive branch in `get_default_file_extension`.

## No-Failure Evidence and RCA

The recorded properties confirm these contracts:

1. Every supported MIME type has a dot-prefixed, whitespace-free default
   extension present in the supported extension set.
2. Extension membership is case-insensitive and rejects empty or malformed
   values.
3. The supported extension set is the union of parser defaults and all
   `mimetypes` aliases.
4. A `mimetypes` fallback does not make an unsupported MIME type supported.

No defect was observed. The implementation derives MIME support from parser
selection, normalizes extension lookups with `lower()`, and builds the extension
set from both parser mappings and aliases. These independent paths explain why
the invariants remained consistent.

As a mutation check, removing `lower()` makes the explicit `.PDF` regression
fail. Omitting parser defaults from the extension union makes the generated
mapping `{"application/x-pbt-a": ".a"}` shrink to a missing `.a` result. These
are detection examples, not production defects.

## Assessment

- All generated and deterministic checks passed.
- The target helper set has complete statement and branch coverage.
- Platform MIME alias tables vary, so the Linux CI artifact is the
  authoritative record for the repository's locked environment.
