# AGENTS.md

Guidance for autonomous coding agents working in `paperless-ngx`.

## Scope

- Prefer small, focused patches that match nearby code.
- Functional changes should target the `dev` branch.
- Backend code is in `src/`; frontend code is in `src-ui/`.
- Run the smallest relevant checks first, then broaden if needed.

## Setup

### Mise (recommended local workflow)

- Repo includes `.mise.toml` for local tools and tasks.
- Install tools: `mise install`.
- Initial setup: `mise run setup` then `mise run init:db`.
- Optional services: `mise run services:start`.
- Start all dev processes: `mise run dev:all`.

### Backend (repo root unless noted)

1. Copy `paperless.conf.example` to `paperless.conf`.
2. Set `PAPERLESS_DEBUG=true` in `paperless.conf`.
3. Create runtime dirs: `mkdir -p consume media`.
4. Install deps: `uv sync --group dev`.
5. Install hooks: `uv run prek install`.
6. Initialize DB from `src/`:
   - `uv run manage.py migrate`
   - `uv run manage.py createsuperuser`

### Frontend (`src-ui/`)

- Use Node `24.x` and `pnpm`.
- Install deps: `pnpm install`.

## Build, lint, test

### Backend commands

- Start Django server (`src/`): `python3 manage.py runserver`
- Start consumer (`src/`): `python3 manage.py document_consumer`
- Start worker (`src/`): `celery --app paperless worker -l DEBUG`
- Run all backend tests (`src/`): `uv run pytest`
- Run one test file (`src/`): `uv run pytest documents/tests/test_xyz.py -n 0 --no-cov`
- Run one test (`src/`): `uv run pytest documents/tests/test_xyz.py::test_case_name -n 0 --no-cov`
- Run filtered tests (`src/`): `uv run pytest -k "query" -n 0 --no-cov`
- Lint Python: `uv run ruff check src`
- Format Python: `uv run ruff format src`
- Type-check Python: `uv run mypy --show-error-codes --warn-unused-configs src/ | uv run mypy-baseline filter`
- Run repository hooks: `uv run prek run -a`

Backend pytest notes:

- Coverage and xdist are enabled by default via config.
- Use `-n 0 --no-cov` for fast local focused runs.
- Tests default to Django settings module `paperless.settings`.
- Useful built-in markers: `live`, `nginx`, `gotenberg`, `tika`, `greenmail`, `date_parsing`.
- If a test command becomes noisy, add `-q` and optionally `--maxfail=1`.
- For report parity with CI/local debugging, keep `-ra` in ad-hoc invocations.

Backend command patterns:

- Run tests in package: `uv run pytest documents/tests -n 0 --no-cov`
- Run tests by keyword: `uv run pytest -k "consumer and not tika" -n 0 --no-cov`
- Re-run last failures: `uv run pytest --lf -n 0 --no-cov`
- Stop after first fail: `uv run pytest -x -n 0 --no-cov`

### Frontend commands (`src-ui/`)

- Start dev server: `pnpm run start`
- Build (dev): `pnpm run build`
- Build (production): `pnpm run build --configuration=production`
- Lint: `pnpm run lint`
- Run unit tests: `pnpm run test`
- Run one unit spec file: `pnpm exec jest src/app/path/to/file.spec.ts`
- Run one unit test name: `pnpm exec jest src/app/path/to/file.spec.ts -t "test name"`
- Run e2e tests: `pnpm exec playwright test`
- Run one e2e file: `pnpm exec playwright test e2e/path/to/spec.spec.ts`
- Run one e2e test name: `pnpm exec playwright test -g "scenario name"`

Frontend testing notes:

- Unit tests run on Jest (`@angular-builders/jest`).
- E2E tests run on Playwright and launch a local server.
- CI shards frontend tests; local runs are usually unsharded.
- Add `--watch` to Jest only when iterating locally, not for CI-like runs.
- Prefer direct spec-file execution before broad suite runs.

Frontend command patterns:

- Run one Jest file in-band: `pnpm exec jest src/app/x/y.spec.ts --runInBand`
- Run one Playwright project: `pnpm exec playwright test --project=chromium`
- Open Playwright UI mode: `pnpm exec playwright test --ui`

### Documentation

- Build docs: `uv run mkdocs build --config-file mkdocs.yml`
- Serve docs: `uv run mkdocs serve`

Mise task equivalents:

- Backend setup: `mise run setup:backend`
- Frontend setup: `mise run setup:frontend`
- DB init: `mise run init:db`
- Backend processes: `mise run dev:backend:web`, `mise run dev:backend:consumer`, `mise run dev:backend:worker`
- Frontend dev server: `mise run dev:frontend`
- Lint: `mise run lint:backend`, `mise run lint:frontend`
- Tests: `mise run test:backend`, `mise run test:frontend`
- Hooks/docs: `mise run check:hooks`, `mise run docs:build`, `mise run docs:serve`

## Style guide

### General

- Follow existing architecture and file layout in touched modules.
- Keep diffs minimal; avoid unrelated refactors.
- Do not add license headers unless a file already uses them.

### Formatting

- Python formatting is authoritative through Ruff formatter.
- Python line length is effectively 88 (`ruff` config).
- Root `.editorconfig`: LF endings, UTF-8, final newline, trim trailing whitespace.
- Root `.editorconfig`: Python uses 4-space indents.
- Root `.editorconfig`: many non-Python files default to tabs; preserve file-local style.
- Frontend `.editorconfig`: 2-space indents and single quotes for TypeScript.
- Tests can exceed line-length limits when clarity improves.

### Imports

- Python imports must satisfy Ruff isort rules.
- Python import style enforces single-line imports (`force-single-line = true`).
- Remove unused imports.
- Frontend imports are organized by Prettier plugin in pre-commit hooks.

### Types

- Python mypy rules are strict: do not add untyped defs in production code.
- Avoid incomplete annotations and implicit `Any` generics.
- Do not introduce new mypy baseline violations.
- In TypeScript, add explicit types at public/API boundaries when inference is unclear.

### Naming

- Python: `snake_case` for funcs/vars/modules.
- Python: `PascalCase` for classes.
- Python: `UPPER_SNAKE_CASE` for constants.
- Angular component selectors: element type, `pngx` prefix, `kebab-case`.
- Angular directive selectors: attribute type, `pngx` prefix, `camelCase`.

### Error handling

- Raise specific exceptions; avoid broad `except Exception` unless required.
- Keep existing logging and error-propagation behavior unless intentionally changing it.
- Custom document parser extensions should raise `documents.parsers.ParseError` on parse failures.
- Add/update tests for bug fixes and behavior changes.

## CI-aligned minimum checks

- Backend-only change:
  - Focused pytest run for touched behavior.
  - `uv run ruff check src`.
- Frontend-only change:
  - Focused Jest/Playwright run.
  - `pnpm run lint`.
- Mixed or risky changes: run broader suites before finishing.
- Prefer `uv run prek run -a` when practical to mirror CI lint hooks.

## Working directory map

- Repo root: `uv sync`, `uv run prek`, docs commands, global lint checks.
- `src/`: `manage.py`, `pytest`, Django/Celery runtime commands.
- `src-ui/`: Angular build/lint/test commands, Jest, Playwright.
- If a command fails unexpectedly, verify current directory first.

## Cursor/Copilot rules status

- No `.cursorrules` file found.
- No files found in `.cursor/rules/`.
- No `.github/copilot-instructions.md` found.
- If these files appear later, treat them as higher-priority instructions and update this guide.

## Suggested agent workflow

1. Determine backend vs frontend scope.
2. Edit only relevant files in `src/` and/or `src-ui/`.
3. Run single-test or targeted checks first.
4. Run broader validation based on risk.
5. Keep changes reviewable and document non-obvious decisions.
