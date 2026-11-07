# Guidance for AI agents

Read [CONTRIBUTING.md](CONTRIBUTING.md) before working on this repository, especially [Use of AI Tools](CONTRIBUTING.md#use-of-ai-tools). These contribution rules apply to all agent-assisted work.

## Contribution boundaries

- Do not open or submit pull requests, including "on behalf of" a human. The project does not accept PRs from AI agents. Prepare local changes for a human to review, verify, and submit personally.
- The project does not accept PRs that are entirely or mostly AI-derived. Human submission and disclosure do not override this rule.
- AI-generated content must be clearly disclosed as described in the contributing guidelines. When handing work back to a human, identify what was generated or changed with AI assistance so they can disclose it accurately.
- Trust matters. Encourage first-time contributors to discuss their proposed change before preparing a PR, especially for large changes or changes involving AI-generated code. New features and enhancements should almost always target an existing feature request with community interest and discussion.
- The project prefers thoughtful, well-described ideas to AI-generated pull requests. Help contributors describe their problem, use case, desired behavior, and who would benefit. An implementation is not required for a valuable contribution, and a flawed implementation can obscure a useful idea before it receives proper discussion.
- AI tools have lowered the effort needed to produce a PR, but reviewing and maintaining it still requires substantial work. Encourage discussion of the idea before investing in implementation and review.
- Issue reports must describe observed behavior, reproduction steps, and relevant logs. Do not add speculative root causes, code analysis, or proposed fixes to agent-generated reports.

## Working on changes

- Read the relevant code, tests, and documentation before editing. Paperless-ngx is complex: trace interactions between affected components rather than assuming a change is isolated.
- Keep changes focused on the requested work and follow existing patterns. Avoid unrelated refactoring, formatting, dependency updates, or generated-file changes.
- Consider effects on permissions, document processing, background tasks, storage, and the API when those areas are involved.
- Add or update meaningful tests for behavior changes and regressions. Do not weaken tests or checks to make a change pass.
- Update user or developer documentation when behavior or setup changes.
- Keep credentials and private documents out of commits, fixtures, logs, and examples.

## Repository and validation

- `src/`: Django back end.
- `src-ui/`: Angular front end, managed with `pnpm`.
- `docs/`: Documentation.
- `docker/` and `scripts/`: Deployment and development tooling.
- Base functional changes on `dev`; documentation-only changes may target `main`.

Follow [the development documentation](docs/development.md) for environment setup and testing. Common checks after setup are:

- Back end: run `uv run pytest` from `src/` (use a test path to focus on the affected area).
- Front end: run `pnpm test` and `pnpm lint` from `src-ui/`.
- Formatting and other pre-commit checks: run `uv run prek run --files <changed-files>` from the repository root.

When handing work back, summarize the changes, the checks actually run and their results, and any remaining uncertainty. Clearly state when a check could not be run; do not claim verification that did not happen. The human contributor must understand and independently verify the contribution before submitting it.
